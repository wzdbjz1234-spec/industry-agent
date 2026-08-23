# 2026-08-23：Phase 6 Agent 调查闭环

## 完成范围

- 固定 `case_id + snapshot_id` 的调查输入和权限边界；
- 实现单 Agent 的 Analysis Run、checkpoint、trace 和生命周期事件；
- 仅允许 Snapshot、指标、代表性样本与知识检索等只读工具；
- 形成 Proposal，并为人工决策保留可审计的证据引用。

## 验证证据

```powershell
uv run pytest backend/tests/unit/test_phase6_agent.py backend/tests/integration/test_phase6_analysis_api.py
uv run python scripts/run_phase5_7_demo.py
```

重复 Case-opened 事件只产生一个 Analysis Run；Agent 不直接写 QMS，也不接触隐藏真值。
