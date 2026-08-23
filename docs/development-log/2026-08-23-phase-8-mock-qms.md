# 阶段 8：Mock QMS 集成与任务闭环

## 完成内容

- 保留 `QmsClient` Port，并增加 HTTP Adapter；Agent 应用层不依赖 FastAPI 或 QMS SDK。
- 新增独立 Mock QMS REST API：任务创建、按 Proposal 查询、任务列表、任务状态更新和简单任务页。
- 新增 QMS Integration Worker：只处理 `quality.investigation.approved.v1`，按
  `event_id + consumer_group` 幂等，区分临时失败与永久失败，支持 Pending 重试和 DLQ。
- `MockQmsAdapter` 以 `proposal_id` 作为外部任务幂等键，Case 保存任务 ID、URI、状态和外部系统。
- 本地 API 的批准接口经过 Worker 自动创建任务，并暴露 QMS 任务与投递状态查询。
- WebUI 增加 QMS 任务页和外部任务链接。
- 补充 `qms.task.created.v1` 契约、JSON Schema、Golden Example、Worker/API/HTTP Adapter 测试。

## 本地演示

```powershell
uv run python scripts/run_phase8_demo.py
uv run uvicorn quality_case_agent.entrypoints.mock_qms.app:app --port 8001
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
cd web
npm run dev
```

主 API 批准 Proposal 后，打开 WebUI 的“QMS 任务”页即可查看任务状态和 Mock QMS 链接。

## 仍保留的边界

当前投递状态和 Mock QMS 数据是内存实现，用于离线验收；生产替换点是
`QmsDeliveryStore`、`QmsClient` 和真实消息中间件 Consumer Group。QMS 写操作仍只由
Integration Worker 负责，Investigation Agent 本身没有外部系统写权限。
