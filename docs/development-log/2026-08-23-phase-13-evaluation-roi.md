# 阶段 13：Agent Eval 与 ROI 看板

## 完成内容

- 增加版本化 Eval 数据集 `evaluation/datasets/phase13.json`，包含 Fixture Offset、Illumination Drift、Insufficient Evidence 三个固定种子场景。
- Eval Runner 为每个场景创建独立容器，隐藏真值只由评估器在 Agent 输出后判断，不进入 Snapshot、工具参数或 Prompt。
- 评估输出包含 Schema 通过率、必需工具覆盖率、证据引用覆盖率、适用性、拒答正确率、禁止结论违规数、工具调用数、检索数、Token、成本和延迟。
- 记录模型配置、Prompt 版本、工具版本、数据集版本和运行指纹；支持两组配置矩阵对比与 JSON 报告导出。
- 增加参数化 ROI Calculator，所有金额明确标记为 `ILLUSTRATIVE` / “示例测算”，不声称真实客户收益。
- 增加 API：`/api/v1/evaluation/dataset`、`/evaluation/run`、`/evaluation/matrix`、`/evaluation/reports`、`/roi/calculate`。
- WebUI 增加“评估与 ROI”页面，可运行两组配置、定位失败 Case，并调整每天 Case 数量查看示例回收周期。
- 增加 Eval/ROI Pydantic 合约、JSON Schema、Golden Examples、单元测试和 `scripts/run_phase13_eval.py`。
- 容器验收发现 wheel 安装布局下数据集路径错误；增加环境变量、源码目录、工作目录和 `/app/evaluation` 的多布局解析，并补充路径回归测试。

## 演示

```powershell
uv run python scripts/run_phase13_eval.py
docker compose build api
docker compose up -d
```

容器 API 的评测矩阵和 WebUI 评估页均返回两组配置、3/3 通过；ROI 返回 `ILLUSTRATIVE` 和免责声明。

报告导出到 `artifacts/evaluation/phase13-report.json`。Dashboard 中 `Measured` 区域只展示固定 Eval 实测指标，`Illustrative` 区域只展示参数化业务金额。

## 验证结果

```text
uv run pytest backend/tests/unit/test_phase13_evaluation.py -q
uv run python scripts/run_phase13_eval.py
```

## 当前边界

当前 Eval Runs 和报告导出为本地内存/JSON 实现，保留未来写入 PostgreSQL Eval Runs 的 application seam；Prompt v1/v2 使用同一离线确定性模型，配置元数据和结果矩阵仍完整保存，真实模型对比需替换 LLM Adapter。
