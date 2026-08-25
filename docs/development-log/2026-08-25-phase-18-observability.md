# Phase 18 开发日志：标准可观测性与运行 SLO

日期：2026-08-25  
状态：已完成（Trace/Prometheus/告警/看板最小闭环）

## 目标

让一个 `case_id`/`analysis_run_id` 能关联到 API、Case pipeline、Agent 工具调用和 Worker 结果；同时让运维通过 Prometheus/Grafana 观察积压、延迟、失败和 Agent 质量，而不是只看进程内存快照。

## 改动内容

### Trace 端口和实现

- `backend/src/quality_case_agent/application/ports/telemetry.py`
  - 定义 `Telemetry`/`TelemetryOperation`，调用点只使用 `operation()`、`set_attribute()`、`succeed()`、`fail()`。
- `backend/src/quality_case_agent/adapters/observability/otel.py`
  - `OtelTelemetry` 使用 OpenTelemetry tracer，统一错误状态和事件记录。
  - `InMemoryTelemetry` 用于测试，支持嵌套 span 继承同一 trace ID。
  - `sanitize_attributes()` 丢弃 prompt/token/document/image 等敏感字段，并脱敏 `api_key=` 等值。
- API 的 vision→metrics→case→investigation 同步流水线包在 `quality.case.pipeline` span 中。

### Prometheus 指标

- `backend/src/quality_case_agent/adapters/observability/prometheus.py`
  - 暴露 worker 处理总数/时延、Stream backlog/最老消息年龄、Outbox 未发布数。
  - 暴露 Agent 分析状态、时延、工具调用、检索调用、Token、成本、abstention。
  - 暴露 QMS delivery 指标预留。
  - labels 只使用 worker/status/provider/model/tool/stream/consumer_group 等低基数值，不写 case_id、图片 URI 或文档正文。
- `application/observability/service.py`
  - WorkerMetricsRegistry/AnalysisMetricsRegistry 增加可选 exporter seam，保留既有 operations API，同时将记录同步到 Prometheus。
- `backend/src/quality_case_agent/entrypoints/api/app.py`
  - 新增 `GET /metrics`，返回 Prometheus text exposition 格式。

### 运行平台配置

- `observability/prometheus.yml`
- `observability/alert-rules.yml`
  - backlog、DLQ、Agent abstention 三类基础告警。
- `observability/otel-collector.yml`
  - OTLP receiver + batch processor 最小配置。
- `observability/grafana/provisioning/datasources/prometheus.yml`
- `observability/grafana/dashboards/quality-case-operations.json`
- `observability/grafana/dashboards/agent-quality.json`
  - Worker/积压/延迟/分析状态/成本面板。
- `docker-compose.yml`
  - 增加 Prometheus 9090 和 Grafana 3000 服务。

## 实现方法与设计取舍

1. 业务时间线 `CaseEventTimelineProjection` 继续保留，它是面向用户的审计投影；Prometheus/Trace 只承载运行信号，避免混淆两种数据用途。
2. OpenTelemetry SDK 未配置 exporter 时仍可在本地安全运行；生产通过 OTLP 环境变量接入 Collector。
3. Metrics labels 严格使用低基数维度，具体 Case/分析内容通过 timeline 和结构化日志查询，不进入时序数据库。
4. 只记录模型/provider/version、工具名、参数 schema 和统计 Token/成本，不记录完整思维链、企业文档正文或图片内容。

## 量化验证

执行：

```text
uv run pytest -q backend/tests/unit/test_phase18_observability.py
uv run pytest -q backend/tests/integration/test_phase12_operations_api.py backend/tests/unit/test_phase12_operations.py
```

结果：`3 passed` + `3 passed`。

| 指标 | 结果 |
| --- | ---: |
| 嵌套 span trace 传播 | 通过，同一 trace ID |
| 敏感字段落盘/导出 | 0（测试断言） |
| Prometheus 指标端点 | HTTP 200，text exposition |
| 高基数 `case_id` 出现在指标标签 | 0 |
| 既有 operations API 回归 | 3 passed |

## 遗留项

- OTel Collector 当前使用 debug exporter，生产需替换为 Jaeger/Tempo 等后端并设置采样/保留策略。
- 真实 Redis backlog、Agent token 和 QMS delivery 需要 Phase 17 Worker 完全启用后持续上报；本阶段已完成指标接口和采集骨架。
