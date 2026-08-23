# 阶段 11：光照漂移与证据不足安全停止

## 完成内容

- 增加固定种子 `ILLUMINATION_DRIFT` 场景：异常分数和 NG 率整体抬升，缺陷区域分布扩散，不复用 Fixture Offset 的根因假设。
- 增加 `IlluminationDriftCaseDetector`，以分数、NG 率和多区域分布组合规则打开独立 Case。
- 增加光照维护技术手册，Agent 检索亮度、光源角度、曝光、增益和基准件校准步骤，输出光照/曝光漂移假设与对应 Proposal。
- 增加 `INSUFFICIENT_EVIDENCE` 场景：样本量不足且混用模型版本；指标窗口产生 `INSUFFICIENT_SAMPLE_COUNT` 和 `MIXED_MODEL_VERSIONS` 警告。
- 增加 `check_data_quality` 只读工具。数据质量被阻断时，Agent 返回 `INSUFFICIENT_EVIDENCE`，终止原因包含 `DATA_QUALITY_BLOCKED`，不输出根因假设、不生成行动 Proposal，并明确列出需要补充的信息。
- 增加 API 演示入口：`POST /api/v1/demo/illumination-drift` 与 `POST /api/v1/demo/insufficient-evidence`；Analysis Runs 页面数据包含摘要、终止原因、证据级别和所需信息。
- 增加 `scripts/run_phase11_demo.py` 与阶段 11 固定种子、检测器和 Agent 安全性测试。

## 演示

```powershell
uv run python scripts/run_phase11_demo.py
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
```

调用两个演示接口后，对比 `/api/v1/analysis/runs`：光照漂移应为 `COMPLETED` 并包含光照 Proposal；证据不足应为 `INSUFFICIENT_EVIDENCE`，没有 hypotheses/proposal，并列出统一模型版本和至少 500 条检测记录等补充信息。

## 验证结果

```text
uv run pytest -q
uv run pytest backend/tests/unit/test_phase11_scenarios.py -q
uv run ruff check backend/src backend/tests simulator scripts
uv run python scripts/run_phase11_demo.py
```

## 当前边界

当前场景和指标窗口仍是可重复的内存演示数据；生产接入时需将数据质量阈值、缺失字段规则和光照参数采集接入真实检测数据源，并保留 `DATA_QUALITY_BLOCKED` 的安全停止语义。
