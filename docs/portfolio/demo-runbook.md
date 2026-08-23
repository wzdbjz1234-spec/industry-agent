# 作品集 Demo Runbook

## 60 秒 Fast Replay

```powershell
uv sync --dev
uv run python scripts/run_fast_demo.py
```

展示 `quality.case.opened.v1`、Analysis 状态、Evidence/Proposal 和人工审批入口。

## 3–5 分钟完整闭环

```powershell
docker compose up --build
uv run python scripts/seed_demo.py
```

打开 `http://localhost:5173`，依次展示：Case 调查 → Evidence/Proposal → 人工审批 → QMS 任务 → 结果回传 → 案例库；最后执行：

```powershell
uv run python scripts/run_phase10_demo.py
```

证明第二个相似 Case 只把第一条已验证经验作为 C 级上下文使用。

## 故障恢复

```powershell
uv run python scripts/run_phase12_demo.py
```

展示超时进入 DLQ、原始 Event ID 保留、人工授权重试、Retry Audit 和最终 QMS task 状态。

## Eval 与 ROI

```powershell
uv run python scripts/run_phase13_eval.py
```

打开 WebUI“评估与 ROI”页，区分 Measured 系统指标和 Illustrative 金额测算。
