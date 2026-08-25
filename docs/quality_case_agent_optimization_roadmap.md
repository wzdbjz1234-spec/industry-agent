# Quality Case Investigation Agent 分阶段优化路线

> 文档状态：Proposed  
> 基线日期：2026-08-24  
> 适用范围：现有 Phase 00–15 之后的生产化与试点优化  
> 目标读者：后端、Agent、视觉算法、平台运维、质量业务负责人

## 1. 结论与总目标

当前项目已经完成可复现的离线闭环：检测结果进入 Quality Case，Agent 围绕冻结 Snapshot 调用只读工具形成 Evidence、Hypothesis 和 Proposal，人工批准后进入 Mock QMS，验证结果再沉淀为可信案例。

下一阶段不应优先增加多 Agent、更多模型供应商或更复杂的前端，而应把项目从“功能完整的内存 Demo”推进为“可恢复、可观测、可量化的单工位影子试点”。

建议采用以下北极星目标：

> 在不越过人工授权边界的前提下，持续缩短从质量异常发生到首个可执行调查建议的时间，并通过现场反馈证明建议质量。

整个优化周期分为 Phase 16–22：

| 阶段 | 建议周期 | 核心结果 | 进入下一阶段的门槛 |
| --- | ---: | --- | --- |
| Phase 16 | 2–3 周 | 数据和业务状态真实持久化 | 重启后 Case、Analysis、Proposal、QMS 投递状态不丢失 |
| Phase 17 | 2–3 周 | 真实事件流和独立 Worker | Worker 崩溃、重复投递和消息积压可恢复 |
| Phase 18 | 1–2 周 | 端到端可观测性 | 一个 `case_id` 可串起完整处理链路并触发告警 |
| Phase 19 | 3–4 周 | 模型与数据健康监控 | 能区分工艺异常、模型漂移和数据质量问题 |
| Phase 20 | 3–4 周 | 通用证据驱动调查 | Agent 不再依赖两类硬编码假设和 Proposal |
| Phase 21 | 3–4 周 | 真实系统影子接入与安全控制 | 真实 QMS 沙箱可幂等投递，越权和伪造回调被阻断 |
| Phase 22 | 4 周以上 | 可量化试点与发布门禁 | 真实回放和影子流量达到预先约定的质量、可靠性和成本门槛 |

Phase 16–18 是生产事实面，Phase 19–20 是诊断质量，Phase 21–22 是现场价值。前三个阶段没有完成前，不建议开始多 Agent 或自动控制设备。

---

## 2. 当前基线与主要差距

### 2.1 已经具备的能力

- 模块化单体结构，`contracts`、`domain`、`application`、`adapters`、`entrypoints` 依赖方向清晰；
- 不可变 Quality Case Snapshot 和结构化事件契约；
- 有界 Agent 循环、工具白名单、轮次和检索预算；
- A/B/C 证据等级、证据不足安全停止；
- Proposal 人工审批和 Mock QMS 幂等投递；
- DLQ 运维入口、时间线和本地 Worker 指标；
- 已验证案例归档和历史经验复用；
- 固定种子场景、Agent Eval、ROI 示例看板；
- 连续视觉入口以及 EfficientAD、anomlib Adapter seam。

### 2.2 当前不能按生产能力宣传的部分

- `docker-compose.yml` 只有 API 和 Web，没有 PostgreSQL、Redis、MinIO 和独立 Worker；
- Composition Root 默认装配 `InMemory*` Adapter，重启会丢失状态；
- `adapters/postgres/`、`adapters/redis_streams/`、`adapters/minio/` 主要还是占位结构；
- Worker 指标、Analysis 指标和 Case 时间线保存在进程内，没有 Prometheus 或 Trace 后端；
- Case 检测主要依赖固定 NG Rate、score 和区域阈值；
- Agent 虽然选择工具，但最终假设、置信度和 Proposal 大量按 `FIXTURE_OFFSET`、`ILLUMINATION_DRIFT` 在代码中组装；
- Eval 只有少量合成场景，不能代表真实未知问题；
- QMS、设备数据、换线记录、环境数据和身份系统都没有真实接入。

### 2.3 设计约束

后续应继续保持模块化单体。生产进程可以独立启动，但共享同一代码库和领域模型。

接口设计遵循以下规则：

1. **保留真正变化的 seam。** PostgreSQL/InMemory、Redis/InMemory、HTTP QMS/Mock QMS 都有生产和测试两个 Adapter，属于真实 seam。
2. **接口作为测试面。** 集成测试应通过应用模块接口验证行为，不直接断言内部 SQL 或 Redis key。
3. **深模块优先。** 例如消息消费模块应把 claim、ack、重试、DLQ、幂等和指标隐藏在小接口后面，避免每个 Worker 重复处理。
4. **普通程序决定安全规则。** Agent 只能生成候选判断和 Proposal，幂等、权限、审批、投递和补偿必须由确定性模块执行。
5. **不为展示技术栈拆微服务。** 当容量、团队所有权或故障隔离出现真实需要时再拆分部署。

---

## 3. 目标包结构

以下是 Phase 22 完成后的建议增量结构。没有列出的现有目录保持不变。

```text
quality-case-agent/
├── backend/
│   ├── migrations/
│   │   ├── 0003_persistent_case_pipeline.sql
│   │   ├── 0004_outbox_inbox.sql
│   │   ├── 0005_monitoring_baselines.sql
│   │   ├── 0006_runbooks_and_feedback.sql
│   │   └── 0007_audit_and_identity.sql
│   └── src/quality_case_agent/
│       ├── contracts/
│       │   ├── monitoring.py
│       │   ├── runbook.py
│       │   ├── feedback.py
│       │   └── identity.py
│       ├── domain/
│       │   ├── monitoring/
│       │   │   ├── models.py
│       │   │   ├── baseline.py
│       │   │   ├── drift.py
│       │   │   └── policies.py
│       │   ├── runbook/
│       │   │   ├── models.py
│       │   │   └── validation.py
│       │   └── feedback/
│       │       ├── models.py
│       │       └── metrics.py
│       ├── application/
│       │   ├── persistence/
│       │   │   └── transaction.py
│       │   ├── eventing/
│       │   │   ├── publisher.py
│       │   │   ├── consumer.py
│       │   │   └── recovery.py
│       │   ├── monitoring/
│       │   │   ├── service.py
│       │   │   └── labeling.py
│       │   ├── investigation/
│       │   │   ├── planner.py
│       │   │   ├── synthesizer.py
│       │   │   ├── grounding.py
│       │   │   ├── policy.py
│       │   │   └── tool_registry.py
│       │   ├── feedback/
│       │   │   ├── service.py
│       │   │   └── dataset_builder.py
│       │   └── ports/
│       │       ├── event_bus.py
│       │       ├── object_store.py
│       │       ├── monitoring.py
│       │       ├── telemetry.py
│       │       ├── equipment.py
│       │       ├── change_log.py
│       │       └── identity.py
│       ├── adapters/
│       │   ├── postgres/
│       │   │   ├── models.py
│       │   │   ├── repositories.py
│       │   │   └── transaction.py
│       │   ├── redis_streams/
│       │   │   ├── publisher.py
│       │   │   ├── consumer.py
│       │   │   └── recovery.py
│       │   ├── minio/
│       │   │   └── object_store.py
│       │   ├── observability/
│       │   │   ├── otel.py
│       │   │   └── prometheus.py
│       │   ├── equipment/
│       │   │   ├── mock.py
│       │   │   └── http.py
│       │   ├── change_log/
│       │   │   ├── mock.py
│       │   │   └── http.py
│       │   ├── identity/
│       │   │   └── oidc.py
│       │   └── qms/
│       │       ├── mock.py
│       │       └── http.py
│       └── entrypoints/
│           ├── api/
│           ├── workers/
│           │   ├── metrics.py
│           │   ├── case_detection.py
│           │   ├── outbox.py
│           │   ├── investigation.py
│           │   ├── qms.py
│           │   └── archival.py
│           └── cli/
│               ├── replay.py
│               └── evaluate.py
├── observability/
│   ├── prometheus.yml
│   ├── alert-rules.yml
│   ├── otel-collector.yml
│   └── grafana/
│       ├── dashboards/
│       └── provisioning/
├── evaluation/
│   ├── datasets/
│   │   ├── synthetic/
│   │   ├── historical_replay/
│   │   └── adversarial/
│   ├── baselines/
│   └── reports/
├── knowledge_base/
│   └── runbooks/
│       ├── fixture-positioning.v1.yaml
│       ├── illumination.v1.yaml
│       └── generic-insufficient-evidence.v1.yaml
└── web/src/features/
    ├── model_health/
    ├── agent_traces/
    ├── feedback/
    └── pilot_metrics/
```

新增目录是建议结构，不要求一次性创建。每个阶段只增加当期实际使用的模块和 Adapter。

---

## 4. Phase 16：真实持久化与运行配置

### 4.1 阶段目标

将 Inspection、Metric、Case、Snapshot、Analysis、Proposal、QMS Delivery、Archive 和知识索引从进程内存迁移到真实持久化实现，同时保留 InMemory Adapter 作为快速测试实现。

### 4.2 加入的功能

- PostgreSQL 持久化核心业务实体；
- pgvector 持久化技术文档和可信案例向量；
- MinIO 保存代表性图片、归档 JSON 和大对象；
- 数据库迁移和启动期 schema 检查；
- `demo`、`test`、`production` 三种显式运行配置；
- 事务内创建 Case、冻结 Snapshot 和写 Outbox；
- Snapshot 版本不可覆盖，事件和外部投递使用唯一幂等键。

### 4.3 如何实现

1. 在 `application/ports/` 保留业务语义接口，不暴露 SQLAlchemy Session。
2. 新建事务模块，使“保存 Case + Snapshot + Outbox”成为一个原子用例。
3. `adapters/postgres/` 实现现有 Store 接口，统一处理领域对象和数据库记录映射。
4. `adapters/minio/object_store.py` 实现 `ObjectStore`，接口只包含 `put`、`get`、`exists` 和签名读取地址，不向调用方暴露 MinIO SDK。
5. `bootstrap.py` 根据显式配置装配 Adapter；测试默认 InMemory，集成环境和生产环境装配 PostgreSQL/MinIO。
6. API 启动失败时明确报告迁移版本、数据库连接和对象存储健康状态，禁止静默降级到内存模式。

### 4.4 包和文件改动

新增：

```text
backend/src/quality_case_agent/application/ports/object_store.py
backend/src/quality_case_agent/application/persistence/transaction.py
backend/src/quality_case_agent/adapters/postgres/models.py
backend/src/quality_case_agent/adapters/postgres/repositories.py
backend/src/quality_case_agent/adapters/postgres/transaction.py
backend/src/quality_case_agent/adapters/minio/object_store.py
backend/migrations/0003_persistent_case_pipeline.sql
backend/tests/integration/test_postgres_repositories.py
backend/tests/integration/test_transactional_case_opening.py
backend/tests/integration/test_minio_object_store.py
```

修改：

```text
backend/src/quality_case_agent/config.py
backend/src/quality_case_agent/bootstrap.py
backend/src/quality_case_agent/entrypoints/api/app.py
docker-compose.yml
.env.example
pyproject.toml
```

### 4.5 量化测评

| 指标 | 计算方式 | 初始验收门槛 |
| --- | --- | ---: |
| 重启恢复率 | 重启后可读取实体数 / 重启前实体数 | 100% |
| Snapshot 不可变性 | 被拒绝的覆盖更新数 / 覆盖更新尝试数 | 100% |
| 批量接入幂等率 | 重复批次未产生新记录数 / 重复批次记录数 | 100% |
| Case 事务一致率 | 同时存在 Case、Snapshot、Outbox 的 Case 数 / 新建 Case 数 | 100% |
| 数据库写入 p95 | Inspection Batch 提交到事务提交的 p95 | 先测基线；本地 100 条批次建议小于 500 ms |
| 对象完整率 | 下载后哈希一致对象数 / 上传对象数 | 100% |

### 4.6 阶段验收

- 运行迁移后可以从空数据库完成全链路；
- API 和 Worker 重启后仍能查看原 Case、Analysis 和 QMS Delivery；
- 数据库不可用时健康检查失败，不切换到 InMemory；
- InMemory 与 PostgreSQL Adapter 通过同一组接口行为测试。

---

## 5. Phase 17：可靠事件流与独立 Worker

### 5.1 阶段目标

把当前同步调用和内存事件模拟改为真实 Outbox + Redis Streams 消费链路，让每个 Worker 拥有独立生命周期和恢复能力。

### 5.2 加入的功能

- Transactional Outbox 发布；
- Redis Streams Consumer Group；
- Inbox 幂等和业务结果幂等；
- Pending 消息认领、超时恢复和 DLQ；
- 指数退避、最大尝试次数和错误分类；
- 独立 Metrics、Case Detector、Investigation、QMS、Archive Worker；
- 队列积压、最老消息年龄和消费延迟查询。

### 5.3 如何实现

定义一个深的事件消费模块，将以下行为隐藏在统一接口后面：

```python
class EventConsumer(Protocol):
    def run_once(self, handler: EventHandler, *, limit: int) -> ConsumeResult: ...
```

`run_once` 内部负责 schema 校验、claim、Inbox 检查、Handler 调用、ack、重试、DLQ 和指标记录。业务 Worker 只提供 Handler，不重复实现 Redis 细节。

Outbox Publisher 只发布已提交事务中的事件；发布成功后记录时间和 Stream ID。Redis 重复投递不能导致重复 Analysis 或重复 QMS 任务。

### 5.4 包和文件改动

新增：

```text
backend/src/quality_case_agent/application/ports/event_bus.py
backend/src/quality_case_agent/application/eventing/publisher.py
backend/src/quality_case_agent/application/eventing/consumer.py
backend/src/quality_case_agent/application/eventing/recovery.py
backend/src/quality_case_agent/adapters/redis_streams/publisher.py
backend/src/quality_case_agent/adapters/redis_streams/consumer.py
backend/src/quality_case_agent/adapters/redis_streams/recovery.py
backend/src/quality_case_agent/entrypoints/workers/metrics.py
backend/src/quality_case_agent/entrypoints/workers/case_detection.py
backend/src/quality_case_agent/entrypoints/workers/outbox.py
backend/src/quality_case_agent/entrypoints/workers/qms.py
backend/src/quality_case_agent/entrypoints/workers/archival.py
backend/migrations/0004_outbox_inbox.sql
backend/tests/integration/test_redis_delivery_semantics.py
backend/tests/integration/test_worker_crash_recovery.py
backend/tests/integration/test_outbox_recovery.py
```

修改 `docker-compose.yml`，增加 PostgreSQL、Redis、MinIO 和独立 Worker 进程。所有进程可以继续复用同一个 API 镜像。

### 5.5 量化测评

| 指标 | 计算方式 | 初始验收门槛 |
| --- | --- | ---: |
| 事件丢失率 | 未到达终态事件数 / 已提交 Outbox 事件数 | 0% |
| 重复有效副作用率 | 重复 Analysis 或 QMS 任务数 / 重复投递事件数 | 0% |
| 恢复成功率 | 崩溃后由其他 Consumer 完成的 Pending 数 / 可恢复 Pending 数 | 100% |
| DLQ 分类准确率 | 正确区分永久/暂时错误数 / 故障注入总数 | 100% |
| 端到端事件延迟 p95 | Outbox `occurred_at` 到 Handler 完成时间 | 先测基线；本地建议小于 5 秒 |
| 最老积压年龄 | 当前时间减去最老未处理事件时间 | 正常流量下小于 2 个处理周期 |

### 5.6 故障演练

必须自动化覆盖：

1. Outbox 已提交但 Publisher 在 publish 前退出；
2. Redis 已投递但 Consumer 在保存结果前退出；
3. Handler 保存结果后、ack 前退出；
4. Redis 短暂不可用；
5. QMS 返回 429、500、超时和永久 4xx；
6. 同一事件被投递 10 次。

---

## 6. Phase 18：标准可观测性与运行 SLO

### 6.1 阶段目标

把当前进程内时间线和计数器升级为标准日志、指标和 Trace，使开发者和运维人员能从一个 `case_id` 定位整条链路。

### 6.2 加入的功能

- OpenTelemetry Trace 和 W3C Trace Context；
- Prometheus 指标端点；
- Grafana 运维看板和 Alertmanager 规则；
- API、数据库、Redis、Agent、工具、检索、QMS 的 span；
- Agent 时延、Token、成本、工具失败和检索质量指标；
- Phoenix、MLflow 或 Langfuse 三选一作为 Agent Trace/Eval 查看层；
- 日志脱敏、采样和保留策略。

### 6.3 如何实现

新增 `Telemetry` port，生产 Adapter 使用 OpenTelemetry，测试 Adapter 记录可断言的 span。业务模块通过上下文管理器记录操作结果：

```python
with telemetry.operation("investigation.run", case_id=case_id) as operation:
    result = investigation.analyze(...)
    operation.succeed(status=result.status)
```

不要让每个调用点自行拼接 span 属性。`Telemetry` 模块应统一低基数字段、错误分类、脱敏和采样。

禁止记录模型完整思维链、密钥、未经脱敏的企业文档和图片内容。可以记录 Prompt 版本、模型版本、工具名称、参数 schema 哈希、检索文档 ID、Token、成本和结构化结果状态。

### 6.4 包和文件改动

```text
backend/src/quality_case_agent/application/ports/telemetry.py
backend/src/quality_case_agent/adapters/observability/otel.py
backend/src/quality_case_agent/adapters/observability/prometheus.py
backend/tests/unit/test_telemetry_contract.py
backend/tests/integration/test_trace_propagation.py
observability/prometheus.yml
observability/alert-rules.yml
observability/otel-collector.yml
observability/grafana/provisioning/
observability/grafana/dashboards/quality-case-operations.json
observability/grafana/dashboards/agent-quality.json
```

现有 `application/observability/service.py` 保留业务时间线投影，但不再承担通用指标后端职责。

### 6.5 必须暴露的指标

#### 系统与消息

- `inspection_batches_total{status}`
- `quality_cases_opened_total{station,product}`，高基数值不得进入 label；
- `worker_events_total{worker,status,error_category}`
- `worker_event_duration_seconds{worker}`
- `stream_backlog_count{stream,consumer_group}`
- `stream_oldest_pending_age_seconds{stream,consumer_group}`
- `outbox_unpublished_count`

#### Agent

- `analysis_runs_total{status,provider,model}`
- `analysis_duration_seconds{provider,model}`
- `analysis_tool_calls_total{tool,status}`
- `analysis_retrieval_calls_total{status}`
- `analysis_tokens_total{provider,model,direction}`
- `analysis_cost_cny_total{provider,model}`
- `analysis_abstention_total{reason}`

#### QMS

- `qms_delivery_total{status,error_category}`
- `qms_delivery_attempts`
- `qms_delivery_duration_seconds`

### 6.6 量化测评和告警门槛

| SLI | 建议初始 SLO | 告警条件 |
| --- | ---: | --- |
| Case 事件处理成功率 | 99.5%/日 | 10 分钟窗口低于 98% |
| Investigation 成功或安全停止率 | 99%/日 | FAILED 比例连续 15 分钟高于 5% |
| QMS 最终投递成功率 | 99.5%/日 | DLQ 新增或最老 Pending 超过 10 分钟 |
| Trace 完整率 | 至少 99% | 缺失根 span 或关键阶段 span 高于 1% |
| 指标新鲜度 | 小于 2 个采集周期 | 超过 2 个周期无新样本 |

这些是初始工程门槛，应在获得真实流量后根据基线修订。

---

## 7. Phase 19：模型、数据和 Case 检测监控

### 7.1 阶段目标

将“固定阈值触发 Case”升级为按产品、工位和模型版本校准的监控模块，并明确区分：

- 真实工艺异常；
- 相机、光照或设备状态变化；
- 模型或输入分布漂移；
- 数据缺失、版本混合和延迟；
- 单点异常与持续过程异常。

### 7.2 加入的功能

- 事件时间、watermark 和迟到数据处理；
- `product_id + station_id + detector_version` 分片基线；
- NG Rate、score 均值/p95、区域分布和样本量动态基线；
- EWMA/CUSUM 过程变化检测；
- score 分布 PSI 或 KS 检测；
- 可选的图像 Embedding 漂移；
- 模型版本、阈值和校准数据版本追踪；
- Case 去重、合并、抑制和冷却窗口；
- 延迟人工标签和复核结果回流；
- Model Health WebUI。

### 7.3 如何实现

`domain/monitoring/` 只包含统计状态和确定性策略，不依赖 NumPy 以外的重型运行时。复杂算法可放在 Adapter 或内部实现中，但对外保持小接口：

```python
class MonitoringPolicy(Protocol):
    def evaluate(self, window: MonitoringWindow, baseline: Baseline) -> MonitoringDecision: ...
```

`MonitoringDecision` 至少返回：异常类型、严重度、统计量、阈值、基线版本、数据质量警告和是否建议打开/合并 Case。

先实现可解释的 EWMA/CUSUM 和 PSI/KS，再根据真实数据决定是否增加 Embedding MMD、在线模型或深度时序模型。

### 7.4 包和文件改动

```text
backend/src/quality_case_agent/contracts/monitoring.py
backend/src/quality_case_agent/domain/monitoring/models.py
backend/src/quality_case_agent/domain/monitoring/baseline.py
backend/src/quality_case_agent/domain/monitoring/drift.py
backend/src/quality_case_agent/domain/monitoring/policies.py
backend/src/quality_case_agent/application/monitoring/service.py
backend/src/quality_case_agent/application/monitoring/labeling.py
backend/src/quality_case_agent/application/ports/monitoring.py
backend/src/quality_case_agent/adapters/postgres/monitoring.py
backend/migrations/0005_monitoring_baselines.sql
backend/tests/unit/test_monitoring_policies.py
backend/tests/integration/test_monitoring_pipeline.py
simulator/scenarios/model_drift/
simulator/scenarios/upstream_data_loss/
simulator/scenarios/process_shift/
web/src/features/model_health/
```

### 7.5 量化测评

离线回放必须同时统计事件级和时间级结果：

| 指标 | 定义 |
| --- | --- |
| Case Precision | 正确打开的 Case / 打开的全部 Case |
| Case Recall | 被检测到的真实异常事件 / 全部真实异常事件 |
| False Cases per 1k | 无真实异常的 Case 数 / 检测批次数 × 1000 |
| Detection Delay | 真实异常开始到 Case 打开的时间 |
| Merge Precision | 应合并且被合并的窗口 / 所有被合并窗口 |
| Drift Detection Recall | 被识别的模型/数据漂移 / 全部漂移场景 |
| Data Quality Block Recall | 正确触发安全阻断的数据质量问题 / 全部阻断场景 |
| Calibration Error | 预测异常概率与实际发生率的差异；没有概率输出时不计算 |

建议初始门槛：

- 数据质量阻断 Recall 不低于 95%；
- 合成和历史回放上的 Case Recall 不低于 90%；
- 在 Recall 达标前提下，False Cases per 1k 相比当前固定阈值降低至少 30%；
- Detection Delay p95 不超过业务配置的两个统计窗口；
- 同一持续异常在冷却窗口内只形成一个活动 Case。

门槛必须按产品和工位切片报告，不能只看总体平均。

---

## 8. Phase 20：通用证据驱动 Investigation

### 8.1 阶段目标

移除 `InvestigationAgent._build_output()` 中按两个 trigger family 固定生成假设、置信度和行动步骤的逻辑，使 Agent 能围绕未知 Case 生成受约束的候选判断，同时继续保留证据、权限和安全停止规则。

### 8.2 加入的功能

- 版本化 Runbook；
- 通用 Tool Registry 和每个工具的参数 schema；
- 调查计划、工具执行、结果综合三个内部阶段；
- LLM 返回结构化 Hypothesis Draft 和 Proposal Draft；
- 应用侧 Evidence Grounding Validator；
- 反证、缺失证据和适用范围检查；
- Prompt、Runbook、Toolset、模型和检索索引版本记录；
- 设备状态、环境数据、换线/维护记录和模型元数据只读工具；
- 对检索、引用、拒答和行动可执行性的独立评测。

### 8.3 如何实现

调查模块保持一个外部接口：

```python
class InvestigationModule:
    def investigate(self, request: InvestigationRequest) -> InvestigationResult: ...
```

内部可以有 Planner、Tool Executor、Synthesizer 和 Grounding Validator，但这些属于内部 seam，不暴露给入口或其他模块。

建议执行顺序：

1. 加载不可变 Snapshot 和 Investigation Policy；
2. 执行数据质量检查；
3. LLM 选择只读工具；
4. 工具返回结构化 Observation 和 Evidence ID；
5. LLM 生成结构化 Draft，不直接成为最终结果；
6. Grounding Validator 校验所有 claim、证据引用、B 级规范适用性和 C 级历史案例限制；
7. Policy 根据风险决定生成 Proposal、要求补充证据或安全停止；
8. 保存完整 Trace、版本和验证结果。

Runbook 用 YAML 或 JSON 表示，但必须经过 Pydantic 契约验证。Runbook 可以定义候选问题、所需证据、适用范围和低风险检查步骤，不能包含任意 Python、Shell 或 SQL。

### 8.4 包和文件改动

```text
backend/src/quality_case_agent/contracts/runbook.py
backend/src/quality_case_agent/domain/runbook/models.py
backend/src/quality_case_agent/domain/runbook/validation.py
backend/src/quality_case_agent/application/investigation/planner.py
backend/src/quality_case_agent/application/investigation/synthesizer.py
backend/src/quality_case_agent/application/investigation/grounding.py
backend/src/quality_case_agent/application/investigation/policy.py
backend/src/quality_case_agent/application/investigation/tool_registry.py
backend/src/quality_case_agent/application/ports/equipment.py
backend/src/quality_case_agent/application/ports/change_log.py
backend/src/quality_case_agent/adapters/equipment/mock.py
backend/src/quality_case_agent/adapters/equipment/http.py
backend/src/quality_case_agent/adapters/change_log/mock.py
backend/src/quality_case_agent/adapters/change_log/http.py
knowledge_base/runbooks/*.yaml
backend/tests/unit/test_grounding_validator.py
backend/tests/unit/test_runbook_validation.py
backend/tests/agent_evals/
evaluation/datasets/adversarial/
```

原 `application/investigation/agent.py` 逐步收缩为循环和预算控制，不再负责拼装特定业务假设。

### 8.5 量化测评

| 指标 | 定义 | 建议发布门槛 |
| --- | --- | ---: |
| Output Schema Pass Rate | 通过输出契约的运行数 / 全部运行数 | 100% |
| Evidence Reference Precision | 实际支持 claim 的引用数 / 全部引用数 | 至少 95% |
| Unsupported Assertion Rate | 没有 A/B 证据支持的确定性断言数 / 全部断言数 | 不高于 1% |
| Required Tool Coverage | 正确调用必需工具的 Case / 有必需工具的 Case | 至少 90% |
| Retrieval Recall@5 | Top 5 中包含必需知识的 Case / 全部需要检索的 Case | 至少 90% |
| Top-3 Hypothesis Recall | 真值出现在前三候选的 Case / 有已知真值 Case | 至少 80% |
| Abstention Recall | 证据不足时正确停止数 / 全部证据不足 Case | 至少 95% |
| Historical Case Misuse Rate | 把 C 级历史经验当当前根因证明的 Case / 命中历史案例 Case | 0% |
| Proposal Executability | 质量工程师评分达到可执行的 Proposal / 被评分 Proposal | 先建基线；试点前建议至少 80% |

评测集建议至少包含：

- 30 个固定合成场景；
- 100 个脱敏历史回放 Case；
- 20 个提示注入、错误文档、过期规范和相似历史案例干扰场景；
- 每个关键场景至少运行 3 个固定种子或固定模型版本重复试验。

---

## 9. Phase 21：真实 QMS 影子接入、身份与审计

### 9.1 阶段目标

接入一个真实 QMS/MES 沙箱或影子接口，建立身份、权限、签名、审计和补偿语义，但不允许 Agent 直接产生生产副作用。

### 9.2 加入的功能

- OIDC/OAuth2 登录和操作者身份；
- 角色与权限策略：Viewer、Quality Engineer、Approver、Operator、Admin；
- Proposal 创建、修改、批准、拒绝和重试审计；
- 真实 QMS HTTP Adapter；
- 幂等键、超时、限流、重试和熔断；
- Webhook 时间戳、签名和重放保护；
- Shadow、Sandbox、Production 三种 QMS 模式；
- Append-only 审计事件和导出；
- Secret 管理和敏感字段脱敏。

### 9.3 如何实现

`QmsClient` 继续作为外部系统 seam。`QmsIntegrationModule` 拥有幂等、状态转换、错误分类和补偿规则，HTTP Adapter 只处理协议转换。

权限检查放在应用用例入口，不能只依赖前端隐藏按钮。Approval Event 必须记录：

- `actor_id`、角色和组织；
- Proposal 原版本和批准版本；
- 决策时间、理由和修改内容；
- `correlation_id`、`causation_id`、`trace_id`；
- 策略版本和身份声明摘要。

影子模式只生成“本应发送”的任务和差异报告，不调用真实写接口。完成影子验证后，才允许切换到 Sandbox。

### 9.4 包和文件改动

```text
backend/src/quality_case_agent/contracts/identity.py
backend/src/quality_case_agent/application/ports/identity.py
backend/src/quality_case_agent/application/identity/policy.py
backend/src/quality_case_agent/adapters/identity/oidc.py
backend/src/quality_case_agent/adapters/qms/http.py
backend/migrations/0007_audit_and_identity.sql
backend/tests/contracts/test_qms_http_contract.py
backend/tests/integration/test_qms_shadow_mode.py
backend/tests/integration/test_authorization.py
backend/tests/integration/test_webhook_security.py
web/src/features/identity/
web/src/features/audit/
```

### 9.5 量化测评

| 指标 | 初始验收门槛 |
| --- | ---: |
| 未授权写操作阻断率 | 100% |
| 伪造或过期 Webhook 阻断率 | 100% |
| QMS 幂等有效率 | 100%，重复批准不产生第二个有效任务 |
| 审计完整率 | 100%，所有状态变化都有 actor、时间和关联 ID |
| Shadow 差异率 | 本地预期任务与 QMS 沙箱任务字段不一致率低于 1% |
| QMS 最终成功率 | 排除永久业务拒绝后至少 99.5% |
| Secret 泄漏扫描 | 日志、Trace、错误响应中发现 0 个有效 Secret |

---

## 10. Phase 22：评测平台、影子试点与发布门禁

### 10.1 阶段目标

把软件测试、Agent Eval、模型监控和业务反馈汇合为一套发布门禁，用真实影子流量回答“是否更快、是否更准、是否更安全”。

### 10.2 加入的功能

- 数据集版本、场景版本和评测配置版本；
- Production Trace 采样进入候选评测集；
- 人工标注建议的接受、修改、拒绝和实际结果；
- Baseline 与 Candidate 对比；
- 按产品、工位、异常类型、模型和 Runbook 切片；
- 可靠性、诊断质量、业务效率和成本四类发布门禁；
- 试点看板和每周评审报告；
- 自动回滚到上一 Agent/Runbook/检测策略版本。

### 10.3 包和文件改动

```text
backend/src/quality_case_agent/contracts/feedback.py
backend/src/quality_case_agent/domain/feedback/models.py
backend/src/quality_case_agent/domain/feedback/metrics.py
backend/src/quality_case_agent/application/feedback/service.py
backend/src/quality_case_agent/application/feedback/dataset_builder.py
backend/migrations/0006_runbooks_and_feedback.sql
backend/tests/integration/test_feedback_capture.py
backend/tests/agent_evals/test_release_gates.py
evaluation/datasets/historical_replay/
evaluation/baselines/
evaluation/reports/
web/src/features/feedback/
web/src/features/pilot_metrics/
```

### 10.4 核心量化指标

#### 可靠性

```text
Event Success Rate
= 到达终态的事件数 / 已提交事件数

Duplicate Effective Action Rate
= 重复有效副作用数 / 重复投递事件数
```

#### 调查质量

```text
Evidence Coverage
= 有有效 A/B 证据引用的候选假设数 / 全部候选假设数

Action Acceptance Rate
= 未修改批准的 Proposal 数 / 被人工决策的 Proposal 数

Modified Acceptance Rate
= 修改后批准的 Proposal 数 / 被人工决策的 Proposal 数

Abstention Precision
= 确实证据不足的安全停止数 / 全部安全停止数
```

#### 业务效率

```text
Time to First Analysis
= analysis.completed_at - case.opened_at

Time to Approved Task
= approval.completed_at - case.opened_at

Manual Triage Time Saved
= 基线人工分诊时长 - Agent 辅助后的人工操作时长

Case Closure Lead Time
= case.closed_at - case.opened_at
```

#### 成本

```text
Cost per Completed Analysis
= 模型 + Embedding + 检索 + 基础设施分摊成本 / 完成的 Analysis 数

Cost per Accepted Proposal
= Agent 总成本 / 未修改或修改后批准的 Proposal 数
```

### 10.5 试点设计

建议采用三步验证：

1. **历史回放。** 至少 100 个已关闭 Case，比较当前人工结论、旧策略和新策略。
2. **影子运行。** 至少 2 周或 30 个有效 Case；系统生成建议但不写真实 QMS。
3. **受控 Sandbox。** 只对人工批准的低风险 Proposal 写入 QMS 沙箱。

每个阶段必须预先冻结数据集和成功门槛，结果出来后不能为了通过而改分母。

### 10.6 建议发布门禁

Candidate 必须同时满足：

- 所有软件、契约和集成测试通过；
- Event Success Rate 不低于 99.5%；
- Duplicate Effective Action Rate 为 0；
- Unsupported Assertion Rate 不高于 1%；
- Abstention Recall 不低于 95%；
- 相比 Baseline，Time to First Analysis p50 至少改善 30%，且 p95 不恶化；
- Action Acceptance Rate 不低于 Baseline；
- 单 Case 成本没有超过预设预算；
- 任一安全红线失败时禁止发布，即使综合得分更高。

这些门槛是建议起点。获得首批真实基线后，应由质量业务和平台负责人共同修订。

---

## 11. 跨阶段测试策略

### 11.1 测试分层

| 测试层 | 测试面 | 重点 |
| --- | --- | --- |
| Domain Unit | 领域模块接口 | 指标、状态机、漂移、策略和证据规则 |
| Adapter Contract | Port interface | InMemory 与生产 Adapter 行为一致 |
| Integration | PostgreSQL、Redis、MinIO、HTTP | 事务、幂等、恢复、签名和协议 |
| Vertical E2E | 从 Inspection 到归档 | 主链路、人工审批和知识闭环 |
| Agent Eval | Snapshot + 文档 + 工具集 | Grounding、检索、假设、拒答和 Proposal |
| Resilience | 故障注入 | 崩溃、重复、超时、断网、积压和恢复 |
| Load | 稳定负载与突发流量 | 吞吐、p95/p99、资源和队列年龄 |
| Security | 身份、输入和输出 | 越权、提示注入、Secret、Webhook 重放 |

### 11.2 Replace，不叠加脆弱测试

当 PostgreSQL Adapter 和深的事件消费模块落地后，应把断言内部字典或 Redis key 的旧测试替换为接口行为测试。测试应在实现重构后保持稳定。

例如消息可靠性测试只关心：

- 相同事件是否只产生一个有效结果；
- 暂时故障是否进入 Pending 并最终恢复；
- 永久故障是否进入 DLQ；
- 原始事件和审计记录是否保持不变。

不应关心内部函数调用次数或具体 Redis 命令顺序。

---

## 12. 实施依赖与并行关系

```text
Phase 16 真实持久化
└── Phase 17 可靠事件流
    ├── Phase 18 标准可观测性
    │   ├── Phase 19 模型/数据监控
    │   └── Phase 20 通用 Investigation
    └── Phase 21 QMS/身份/审计

Phase 19 + Phase 20 + Phase 21
└── Phase 22 影子试点与发布门禁
```

可并行项：

- Phase 18 的指标字典可以和 Phase 17 后半段并行；
- Phase 19 的离线算法实验可以在 Phase 16–17 期间用现有回放数据进行；
- Phase 20 的 Runbook 契约和 Eval 数据集可以提前编写；
- Phase 21 的 QMS 契约调研和身份模型可以提前，但真实写入必须等待 Phase 17。

不可并行跳过项：

- 没有 Phase 16–18，不进入真实影子流量；
- 没有 Phase 20 的 Grounding 门禁，不放宽 Agent 场景范围；
- 没有 Phase 21 的身份和审计，不连接真实 QMS 写接口；
- 没有 Phase 22 的现场反馈，不宣传真实 ROI。

---

## 13. 每阶段交付模板

每个阶段 PR 或交付记录至少包含：

1. 阶段目标和不做事项；
2. 新增或修改的模块、interface、seam 和 Adapter；
3. 数据库迁移和协议版本影响；
4. 新增指标、Trace 和告警；
5. 测试命令与结果；
6. 故障或安全演练结果；
7. Baseline、Candidate 和量化指标；
8. 已知限制和回滚方法；
9. 对应 ADR 和开发日志。

建议新增 ADR：

```text
docs/adr/001-postgres-transaction-and-outbox.md
docs/adr/002-redis-stream-delivery-semantics.md
docs/adr/003-opentelemetry-and-agent-trace.md
docs/adr/004-monitoring-baseline-policy.md
docs/adr/005-runbook-and-grounding-policy.md
docs/adr/006-qms-shadow-and-authorization.md
docs/adr/007-pilot-release-gates.md
```

---

## 14. 近期第一批可执行任务

如果立即开始修改，建议按以下顺序拆分首批任务：

1. 定义 production 配置，不允许数据库失败时降级到 InMemory；
2. 为 Quality Case、Analysis Run、Proposal、QMS Delivery 建表和迁移；
3. 编写 PostgreSQL Adapter contract tests；
4. 实现 Case + Snapshot + Outbox 原子事务；
5. 将 `build_demo_container()` 拆成 demo 和 production 两个 Composition Root；
6. 在 Compose 中加入 PostgreSQL、Redis、MinIO 和健康检查；
7. 实现 Outbox Publisher 和一个 Investigation Consumer Group；
8. 完成一次“保存后崩溃、重启、重新认领、无重复 Analysis”的自动化演练；
9. 再扩展其他 Worker，避免同时改完整链路导致无法定位问题。

第一批任务完成后，项目的性质才会从“离线作品集”开始转向“可试点系统”。

---

## 15. 参考开源实践

- [Anomalib](https://anomalib.readthedocs.io/en/stable/)：视觉异常模型、阈值、指标和部署；
- [FiftyOne](https://docs.voxel51.com/) 与 [CVAT QA](https://docs.cvat.ai/docs/qa-analytics/)：hard-case、标签质量和逐样本分析；
- [Apache StreamPipes](https://streampipes.apache.org/)：工业数据连接、流处理和在线分析；
- [ThingsBoard](https://thingsboard.io/docs/user-guide/)：遥测、规则、告警和运维看板；
- [Robusta](https://github.com/robusta-dev/robusta) 与 [K8sGPT](https://github.com/k8sgpt-ai/k8sgpt)：规则/分析器先发现事实，再进行告警富化；
- [HolmesGPT](https://github.com/HolmesGPT/holmesgpt)：事件或定时触发、受限工具取证和调查型 Agent；
- [Evidently](https://docs.evidentlyai.com/introduction)：数据质量、漂移和评测；
- [Phoenix](https://arize.com/docs/phoenix/)、[MLflow Tracing](https://mlflow.org/docs/latest/genai/tracing)、[Langfuse](https://langfuse.com/docs/observability/best-practices)：Agent Trace、评测、实验和生产反馈。

这些项目应作为不同层的参考或依赖候选，而不是要求当前项目重新实现它们的全部能力。
