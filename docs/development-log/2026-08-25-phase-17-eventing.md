# Phase 17 开发日志：可靠事件流与独立 Worker seam

日期：2026-08-25  
状态：已完成（InMemory 可靠语义可运行，Redis Streams 适配器和 Compose 依赖已接入）

## 目标

将“发布、消费、去重、ACK、重试、DLQ、积压恢复”从各业务 Worker 中抽离，形成一个可替换的可靠事件模块；业务 handler 不再重复 Redis 细节。

## 改动内容

### 事件端口与深模块

- `backend/src/quality_case_agent/application/ports/event_bus.py`
  - `EventEnvelope`：版本化事件 ID/type/occurred_at/payload/stream。
  - `EventBus`：`publish`、`read`、`ack`、`retry`、`pending_count`、`oldest_pending_age_seconds`。
  - `InboxStore`、`OutboxStore` 和统一 `ConsumeResult`。
- `backend/src/quality_case_agent/application/eventing/consumer.py`
  - `ReliableEventConsumer.run_once()` 统一执行 Inbox 检查、handler、成功标记、ACK、重试和 DLQ。
  - `PermanentEventError` 立即进入 DLQ；普通错误按最大尝试次数处理。
  - Inbox 标记发生在业务 handler 成功之后，避免“先去重、后副作用”导致丢事件。
- `backend/src/quality_case_agent/application/eventing/publisher.py`
  - `OutboxPublisher` 只发布未标记的已提交 Outbox 行，成功后记录 `published_at`。

### Adapter 实现

- `backend/src/quality_case_agent/adapters/redis_streams/in_memory.py`
  - 用于单测/本地开发的可见性超时、pending、指数退避和 DLQ 模拟。
  - `InMemoryInboxStore` 保证业务副作用幂等。
  - `InMemoryOutboxStore` 模拟事务提交后的待发布记录。
- `backend/src/quality_case_agent/adapters/redis_streams/client.py`
  - `RedisStreamsEventBus` 映射 `XADD`、Consumer Group、`XREADGROUP`、`XACK`、`XPENDING`。
  - 每次读取先用 `XAUTOCLAIM` 认领超过可见性超时的 pending，再读取新消息，覆盖 Worker 崩溃恢复。
  - 超过最大次数的事件写入 `<stream>:dlq`；未达到上限的事件保留 pending，交由下一次 claim/recovery 继续消费。

### Worker 入口和运行依赖

- `backend/src/quality_case_agent/entrypoints/workers/outbox.py`
- `backend/src/quality_case_agent/entrypoints/workers/event_consumer.py`
  - 只暴露通用 `run_once`，Metrics/Case Detection/Investigation/QMS/Archive Worker 可复用同一语义。
- `docker-compose.yml`
  - 增加 PostgreSQL、Redis 7、MinIO 服务及健康检查/持久化卷。
- `backend/migrations/0003_phase16_persistence.sql`
- `backend/migrations/0004_phase17_eventing.sql`
  - 记录 Outbox/Inbox 表和未发布索引的部署形状。

## 实现方法与设计取舍

1. 事件消费采用“至少一次投递 + Inbox 幂等”，不宣称 Redis 能提供 exactly-once；真实副作用由业务唯一键保护。
2. Handler 只接收 `EventEnvelope`，因此可以在不改业务代码的情况下从 InMemory 切到 Redis Streams。
3. 可见性超时是 Adapter 行为；消费者只处理失败分类和最大尝试次数，避免每个 Worker 自己实现恢复逻辑。
4. Outbox 先落库后发布，解决 API 在数据库提交成功但进程在 publish 前退出时的事件丢失。

## 量化验证

执行：

```text
uv run pytest -q backend/tests/integration/test_phase17_eventing.py
```

结果：`4 passed`。

| 指标 | 结果 |
| --- | ---: |
| 重复 Outbox 发布新增事件 | 0 |
| Inbox 防重复业务调用 | 通过 |
| 暂时错误恢复成功率 | 100%（故障注入 1 次后恢复） |
| 永久错误 DLQ 分类率 | 100% |
| 已处理事件 pending 数 | 0 |

## 遗留项

- Redis 集成测试和 kill/restart 演练需要启动 Compose 服务；下一阶段将把消费结果、积压、延迟和失败分类接入 Prometheus/Trace。
- API 当前仍保留同步 Demo pipeline；生产 Worker 入口应按固定周期调用同一 `run_once`，让 `XAUTOCLAIM` 和积压指标持续生效。
