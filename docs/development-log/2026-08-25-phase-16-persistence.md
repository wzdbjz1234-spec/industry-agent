# Phase 16 开发日志：真实持久化与运行配置

日期：2026-08-25  
状态：已完成（可在 SQLite/ PostgreSQL URL 上运行；MinIO 适配器已就绪）

## 目标

把 Inspection、Metric、Case/Snapshot、Analysis Run 和 Outbox/Inbox 的持久化从进程内存提升为可重启恢复的适配器，同时不破坏原有 InMemory 测试 seam。

## 改动内容

### 新增应用端口和事务边界

- `backend/src/quality_case_agent/application/ports/object_store.py`
  - 定义 `ObjectStore`：`put`、`get`、`exists`、`presigned_get_url`。
  - 业务层只依赖对象 key/bytes，不依赖 MinIO SDK。
- `backend/src/quality_case_agent/application/persistence/transaction.py`
  - 提供 provider-neutral 的事务上下文，为 Case/Snapshot/Outbox 原子写入预留深模块接口。

### 新增 SQLAlchemy 持久化适配器

- `backend/src/quality_case_agent/adapters/postgres/repositories.py`
  - `SqlAlchemyPersistence` 根据 URL 建立 Engine 并自动建表。
  - `SqlAlchemyInspectionStore`：批次唯一键、结果唯一键、重复批次幂等、时间确定性排序。
  - `SqlAlchemyMetricsStore`：按窗口和维度 upsert。
  - `SqlAlchemyQualityCaseStore`：Snapshot hash 不可变、状态字段合并、事件幂等。
  - `SqlAlchemyAnalysisRunStore`：Analysis Run 按 idempotency key 恢复，输出按 run ID 不可变。
  - `SqlAlchemyOutboxStore`：Outbox 未发布查询、发布标记、Inbox 去重记录。
  - 数据保存在 JSON snapshot 中，数据库只承载索引/幂等键/时间字段；同一映射可使用 `sqlite:///...` 做 CI，也可使用 `postgresql+psycopg://...` 做生产部署。
- `backend/src/quality_case_agent/adapters/minio/object_store.py`
  - `MinioObjectStore` 封装 bucket 初始化、读写、存在性检查和预签名 URL。
  - `InMemoryObjectStore` 用于离线测试，并提供 SHA-256 校验辅助。

### 新增运行配置和装配入口

- `backend/src/quality_case_agent/config.py`
  - `RuntimeSettings` 支持 `demo`、`test`、`production` 三种显式模式。
  - production 模式缺少 `QUALITY_DATABASE_URL` 时立即失败，避免静默降级为内存模式。
- `backend/src/quality_case_agent/bootstrap.py`
  - `build_persistent_resources()` 统一创建数据库、各持久化 Store 和 Outbox Store。

### 依赖

在 `pyproject.toml`/`uv.lock` 加入 SQLAlchemy、psycopg、Redis、MinIO、Prometheus Client 和 OpenTelemetry API/SDK，为后续两个阶段提供真实运行时依赖。

## 实现方法与设计取舍

1. 领域对象仍由 `domain` 定义，Repository 只在 adapter 层做 JSON ↔ domain 映射；SQLAlchemy Session 没有泄漏到 application port。
2. Snapshot 使用已有 canonical hash 复算校验，任何改变 observations 的更新都会被拒绝。
3. InMemory Adapter 不删除，作为快速单测实现；SQLite 仅作为本地/CI 的可重复数据库，生产通过 PostgreSQL URL 切换。
4. Outbox/Inbox 表先由 Phase 16 建立，真正的发布、claim、重试由 Phase 17 的事件模块负责。

## 量化验证

执行：

```text
uv run pytest -q backend/tests/integration/test_phase16_persistence.py
```

结果：`5 passed`。

覆盖指标：

| 指标 | 结果 |
| --- | ---: |
| 新适配器实例重启读取 Inspection/Metric | 通过 |
| 重复批次新增记录数 | 0 |
| Snapshot 不可变性拒绝率 | 100%（测试覆盖） |
| Case Event 重复写入副作用 | 0 |
| ObjectStore 写入后读取字节哈希 | 通过 |

## 遗留项

- Demo 默认仍保持 InMemory，避免本地启动强依赖外部服务；设置 `QUALITY_RUNTIME_MODE=production` 后，API composition root 会自动装配 SQLAlchemy Inspection/Metric/Case/Analysis/Outbox/Inbox 资源。
- MinIO 集成测试需要可用的 MinIO 服务，当前以 InMemory 契约测试覆盖 SDK 之外的行为。
