# 阶段 12：事件时间线、Worker 运维与受控重试

## 完成内容

- 增加 `CaseEventTimelineProjection`，将 Case opened/recovered、Analysis started/completed/failed、Proposal、人工审批、QMS task 和归档事件投影为按时间排序的结构化时间线；支持 `case_id`、`trace_id` 过滤并按 `event_id` 幂等。
- 增加 Worker 指标：处理量、失败量、Pending/DLQ 数量、平均延迟、错误类型和脱敏错误摘要；增加 Analysis 工具调用、知识检索次数、估算 Token 和估算成本指标。
- 扩展 QMS Delivery 记录，保留创建/更新时间、错误类型和错误时间；提供只读 Pending、Processed、DLQ 查询。
- 增加带 `X-Operator-Id` 的 DLQ 受控重试。重试保留原始 Approval Event ID，记录操作者、前后状态、请求时间和 attempts；未经操作者身份拒绝执行。
- 增加运维 API：Case 时间线、Worker 状态、投递状态、Analysis 指标、Retry Audit 和 DLQ 重试。
- 增加 WebUI“运维”页，展示 Worker 健康度、Pending/DLQ 消息和授权重试入口；Case 页面可直接打开事件时间线；页面仅展示结构化摘要，不展示模型思维链。
- 增加结构化日志查询说明：`docs/operations/structured-logging.md`。
- 增加 `scripts/run_phase12_demo.py`，模拟知识检索超时导致 DLQ，人工授权后恢复 QMS task，并输出最终 Analysis 状态与因果时间线。

## 演示

```powershell
uv run python scripts/run_phase12_demo.py
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
cd web
npm run dev
```

打开“运维”页可查看 Worker、投递状态和授权重试；Case 页的“查看事件时间线”会打开只读投影。CLI 演示中，原始 Approval Event 会先进入 `DLQ`，再由 `phase12-human-operator` 授权重试为 `PROCESSED`，Case 的 Analysis 状态保持原有结构化状态。

## 验证结果

```text
uv run pytest -q
uv run ruff check backend/src backend/tests simulator scripts
uv run mypy
npm run build                            (web/)
uv run python scripts/run_phase12_demo.py
```

## 当前边界

时间线、指标和 Delivery Projection 当前为内存实现；生产环境替换为事件表、指标系统和持久化消费 Inbox 时，需要保持 Event ID 幂等、原始事件不可变、错误脱敏和授权重试审计语义。
