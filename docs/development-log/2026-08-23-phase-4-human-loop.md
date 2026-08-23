# 2026-08-23：Phase 4 人工闭环

## 目标

依据设计文档 Phase 4 和开发计划 Task 07～09，建立离线可验证的人工闭环：

```text
InvestigationAnalysis
→ Proposal 人工审批
→ Mock QMS 任务
→ 签名结果 Webhook
→ Case Confirmation
→ JSON Archive
→ VERIFIED_EFFECTIVE 可信案例索引
```

## 本次实现

- 增加 `APPROVE`、`APPROVE_WITH_CHANGES`、`REJECT`、`REQUEST_REANALYSIS` 决策契约；
- 驳回和重新分析强制填写意见；
- 实现 Proposal 版本审计、人工修改后批准、`decision_id` 幂等；
- 实现 `quality.investigation.approved.v1`、`rejected.v1` 和 `reanalysis.requested.v1` 事件；
- 扩展 Quality Case 状态：审批等待、QMS 待创建、QMS 处理中、确认和归档；
- 实现 Mock QMS Adapter，按 `proposal_id` 幂等创建任务；
- 实现 HMAC 签名 QMS 结果 Webhook，支持签名校验和事件重放保护；
- 实现人工根因、措施、验证结果和 Agent 评价契约；
- 实现完整 Case JSON 归档，按日期目录、Case ID 和 revision 生成不可覆盖 URI；
- 只有 `VERIFIED_EFFECTIVE` 且根因/措施完整的 Case 才进入可信案例索引；
- 增加 Phase 4 离线 Demo、审批单测和端到端闭环测试。

## 关键设计决定

### 1. Agent 不拥有 QMS 写权限

Agent 只输出 `PENDING_APPROVAL` Proposal。只有人工批准事件能够进入 QMS Integration Service；QMS Adapter 对 Agent 不可见。

### 2. 审批修改保留原版本

`APPROVE_WITH_CHANGES` 不覆盖 Agent 原始 Proposal，而是创建 `proposal_id:v2`，保留原始 Proposal、批准人、意见和决策 ID。

### 3. 所有 Case 都归档，只有可信 Case 进入索引

人工结论即使是 `INCONCLUSIVE` 也可以保存完整审计 JSON，但不会进入 Agent 的 `VERIFIED_CASE` 检索集合。

### 4. 本阶段使用内存 Adapter

PostgreSQL、Redis、MinIO 和 Mock QMS REST API 尚未接入，因此使用 Port + 内存 Adapter 验证状态流转、签名、幂等和归档规则。

## 验证

```powershell
uv run pytest
uv run python scripts/run_phase4_demo.py
uv run ruff check backend/src backend/tests simulator scripts
uv run mypy
```

实际验证结果：

- `19 passed`；
- Ruff 检查与格式检查通过；
- mypy：`Success: no issues found in 78 source files`；
- 重复批准事件只创建一个 QMS 任务；
- 重复 Webhook 和归档不会产生重复对象；
- Case 最终为 `ARCHIVED`，可信案例索引数量为 1。

## 当前限制

- 尚未实现真实 Proposal API、审批 WebUI 和用户身份认证；
- Mock QMS 仍为内存 Adapter，尚未提供独立 REST 服务、Consumer Group、重试和 DLQ；
- 归档使用内存对象存储，后续替换为 MinIO；
- 可信案例索引使用内存记录，后续替换为 pgvector/Embedding Adapter；
- 当前归档只接收单个 Analysis Output，尚未持久化多次人工重新分析的完整 Analysis Run 集合；
- `get_representative_samples`、图片归档和真实现场数据仍留待后续阶段。
