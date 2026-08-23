# 阶段 9：人工结论与知识闭环

## 完成内容

- 为 `qms.task.result-submitted.v1` 增加版本化结果契约、JSON Schema 和 Golden Example。
- Mock QMS 增加结果填写页面和 JSON 提交接口，返回 HMAC 签名结果。
- Webhook 增加 HMAC 校验、时间窗校验和事件重放保护。
- 新增 `CaseClosureService`，串联 QMS Confirmation、完整 JSON Archive 和可信案例索引。
- 归档内容包含 Snapshot、Investigation/Trace、审批事件、批准 Proposal、QMS 任务和人工结论。
- 支持按日期目录、Case ID、Revision 生成不可覆盖归档 URI。
- 仅 `VERIFIED_EFFECTIVE` 且根因和措施完整的结果进入可信案例索引。
- 主 API 增加 QMS 结果 Webhook、Case 详情、归档读取和案例库查询接口。
- WebUI 增加 Case 外部任务状态、QMS 结果入口和已验证案例库页面。

## 演示

```powershell
uv run python scripts/run_phase9_demo.py
uv run uvicorn quality_case_agent.entrypoints.mock_qms.app:app --port 8001
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
cd web
npm run dev
```

独立 Mock QMS 的“填写结果”接口会生成签名结果；主 API 接收时通过
`POST /api/v1/integrations/qms/task-results` 和 `X-QMS-Signature` 完成确认及归档。

## 当前边界

本阶段使用内存 Archive Store、可信案例 Index 和 Proposal/Analysis Run Store，验证业务规则和幂等语义。
生产替换点分别是 MinIO/S3、pgvector、PostgreSQL 事务和消息 Consumer Group。
