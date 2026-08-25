# Phase 19 开发日志：模型、数据和 Case 检测监控

日期：2026-08-25  
状态：已完成（确定性监控策略、基线持久化、API 与 Model Health WebUI）

## 阶段目标

把“固定阈值触发 Case”旁边补上一层模型/数据健康监控，明确区分工艺变化、模型/输入漂移和数据质量阻断；监控结果可以被复现、持久化和审计。

## 改动内容

### 领域模块：小接口、深实现

- `backend/src/quality_case_agent/domain/monitoring/models.py`
  - `MonitoringWindow`：窗口指标、模型版本、分数直方图、watermark、迟到计数、数据质量警告。
  - `Baseline`：按 `factory_id + line_id + station_id + product_id + model_version` 分片的不可变基线。
  - `DriftSignal` 与 `MonitoringDecision`：统一返回状态、严重度、信号统计量、阈值、基线版本和 `OPEN_CASE/MERGE_CASE/BLOCK` 动作。
- `domain/monitoring/baseline.py`
  - 聚合 NG rate、score mean/std、p95 和 score histogram，混合模型窗口不会写入基线。
- `domain/monitoring/drift.py`
  - 纯 Python 实现 EWMA z-score、单侧 CUSUM、PSI 和直方图 KS distance，不引入重型运行时。
- `domain/monitoring/policies.py`
  - `MonitoringPolicy` 是外部 seam；`DefaultMonitoringPolicy` 负责数据质量优先阻断、工艺变化 Case、模型漂移告警和缺少基线提示。

### 应用模块

- `backend/src/quality_case_agent/application/monitoring/service.py`
  - 从 Inspection facts 构建固定窗口和 10-bin score histogram。
  - 处理 watermark/允许迟到时间，输出 `LATE_DATA`。
  - 生成、保存和读取分片基线；用同一维度/模型版本评估窗口。
  - 在 cooldown 内将持续异常从 `OPEN_CASE` 转为 `MERGE_CASE`，正常窗口释放活动 Case key。
- `backend/src/quality_case_agent/application/ports/monitoring.py`
  - 只暴露 `save/get/list` 三个基线操作，InMemory/SQLAlchemy 两个 Adapter 共用同一接口。

### 持久化与协议

- `backend/src/quality_case_agent/adapters/in_memory/monitoring.py`
  - 测试和 Demo 的基线 Adapter。
- `backend/src/quality_case_agent/adapters/postgres/monitoring.py`
  - SQLAlchemy/PostgreSQL-ready 基线 Adapter，支持重启后读取。
- `backend/migrations/0005_monitoring_baselines.sql`
  - 新增 `monitoring_baselines` 表及维度/模型索引。
- `backend/src/quality_case_agent/contracts/monitoring.py`
  - 版本化 `MonitoringDecisionContract`/`MonitoringReportContract`，禁止把内部实现对象直接暴露给 API。

### API、指标与 WebUI

- `backend/src/quality_case_agent/entrypoints/api/app.py`
  - `POST /api/v1/monitoring/baseline`
  - `GET /api/v1/monitoring/health`
  - production runtime 自动使用 Phase 16 持久化基线 Adapter。
- `backend/src/quality_case_agent/adapters/observability/prometheus.py`
  - 新增 `monitoring_decisions_total`、`monitoring_drift_score`、`monitoring_data_quality_blocks_total`。
- `web/src/api/client.ts`
  - 新增监控报告和建立基线客户端方法。
- `web/src/features/model_health/ModelHealth.tsx`
  - 新增 Model Health 页面：建立基线、刷新窗口、展示工艺变化/模型漂移/数据质量阻断和信号统计。
- `web/src/App.tsx`
  - 增加“模型健康度”导航入口。
- `simulator/scenarios/model_drift/`、`upstream_data_loss/`、`process_shift/`
  - 增加三类回放场景说明，作为后续真实数据生成器的固定命名。

## 实现方法与设计取舍

1. 监控模块的 Interface 只需要 `evaluate(window, baseline)`；统计细节隐藏在领域 Implementation 中，便于替换阈值或算法而不改 API/Worker 调用方。
2. 只用对齐直方图计算 PSI/KS，当前不依赖 NumPy/SciPy；当真实数据量和标签条件成熟后，再评估 Embedding MMD 等 Adapter。
3. 数据质量优先级高于漂移信号：混合模型版本、样本不足、迟到数据会返回 `BLOCK`，不会误开工艺 Case。
4. `OPEN_CASE` 只代表监控建议，当前 Case/人工审批安全边界不变；连续窗口只返回 `MERGE_CASE`，避免同一异常风暴产生重复 Case。
5. 监控指标使用低基数标签；具体窗口、维度和模型版本通过 API 报告与持久化基线查询，不写入 Prometheus label。

## 量化验证

执行：

```text
uv run pytest -q backend/tests/unit/test_monitoring_policies.py backend/tests/integration/test_monitoring_pipeline.py backend/tests/integration/test_phase19_monitoring_api.py
```

结果：`8 passed`（4 个策略测试、3 个 Pipeline/持久化测试、1 个 API 测试）。

| 指标 | 结果 |
| --- | ---: |
| 正常窗口误报 | 0（策略测试） |
| 工艺变化识别 | EWMA/CUSUM 均可解释，返回 `OPEN_CASE` |
| 模型/输入漂移识别 | PSI + KS 返回 `MODEL_DRIFT`，不打开工艺 Case |
| 数据质量阻断 | 混合模型/迟到数据返回 `DATA_QUALITY_BLOCK` |
| 冷却窗口去重 | 首窗口 `OPEN_CASE`，后续窗口 `MERGE_CASE` |
| 基线重启恢复 | SQLite 关闭/重开后版本和统计量一致 |
| API 契约 | `/baseline`、`/health` 返回 schema `1.0` |
| WebUI 构建 | `npm run build` 通过 |

全量回归：`73 passed`；`ruff` 和 `mypy` 均通过；`web` 执行 `npm run build` 通过。

## 后续边界

- 真实标签回流、Calibration Error、Embedding MMD 和历史 Case Recall 需要 Phase 20/现场数据后再启用；当前阶段先保证可解释的统计信号和数据质量安全阻断。
- 现有固定 Case Detector 仍保持兼容；Phase 20 再决定是否让监控 `OPEN_CASE` 事件成为统一 Case Detector 输入。
