# 2026-08-23：Phase 7 人工审批与外部任务边界

## 完成范围

- 提供待审批 Proposal 查询、批准/拒绝/要求重新分析接口；
- 记录操作者、决策时间、原因和版本，形成 Approval Audit；
- 仅在批准后创建幂等 Mock QMS 任务；
- 将外部任务状态回传至 Case，并支持重新分析回调。

## 验证证据

```powershell
uv run pytest backend/tests/unit/test_phase7_approval.py backend/tests/integration/test_phase7_approval_api.py
uv run python scripts/run_phase5_7_demo.py
```

重复审批和重复投递不会创建重复外部任务；`REQUEST_REANALYSIS` 只创建新的 Analysis Run，不绕过人工边界。
