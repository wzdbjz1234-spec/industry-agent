# 阶段 12：结构化日志与运维查询

所有 Worker 和 Analysis 运维记录都使用低基数结构化字段；错误只保留错误类型和脱敏摘要，不记录完整模型思维链、Prompt 或敏感凭据。

## 推荐字段

| 字段 | 用途 |
| --- | --- |
| `occurred_at` | 事件或处理完成时间，统一 UTC |
| `event_id` / `case_id` / `trace_id` | 关联一次消息、Case 和 Analysis Run |
| `worker` / `consumer_group` | 定位处理者和消费组 |
| `status` / `state` | `PROCESSED`、`PENDING`、`DLQ`、`INSUFFICIENT_EVIDENCE` 等结构化状态 |
| `attempts` / `duration_ms` | 重试次数和处理延迟 |
| `error_type` / `error` | 错误类别和脱敏摘要 |
| `tool_call_count` / `retrieval_call_count` | Agent 工具调用和检索次数 |
| `estimated_tokens` / `estimated_cost_cny` | 离线成本估算，不代表供应商账单 |

## API 查询

```text
GET /api/v1/cases/{case_id}/timeline
GET /api/v1/operations/timeline?case_id={case_id}
GET /api/v1/operations/workers
GET /api/v1/operations/delivery
GET /api/v1/operations/analysis-metrics
GET /api/v1/operations/retry-audit
```

受控恢复必须携带 `X-Operator-Id`：

```text
POST /api/v1/operations/retry-dlq/{event_id}
X-Operator-Id: quality-operator
```

查询结果将业务拒绝（例如 `QmsPermanentError`、无效 Proposal）与系统失败（例如超时、连接错误）通过 `error_type` 和 Worker 状态区分；DLQ 重试只改变投递状态，原始 Approval Event ID 不变。
