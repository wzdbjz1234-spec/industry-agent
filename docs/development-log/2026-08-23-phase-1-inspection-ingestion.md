# 阶段 1：检测结果接入

## 完成内容

- 建立 `inspection.result.batch.v1` 输入契约和 JSON Schema/Golden Example。
- 增加 Normal、Fixture Offset、Illumination Drift、Insufficient Evidence 固定种子 Replay。
- 通过 Detector Adapter 将外部结果映射为领域对象，Inspection Store 以批次 ID 和结果 ID 实现幂等接入。
- 保留图像 URI、异常分数、阈值、缺陷区域、批次和模型版本等可追溯字段。
- 在 API Demo、Fast Replay、指标 Worker 和 Case 检测之间打通真实入口到结构化输出。

## 验收命令

```powershell
uv run pytest backend/tests/unit/test_phase2_pipeline.py -q
uv run python scripts/run_fast_demo.py
```

## 边界

当前输入是固定种子合成 Replay；生产相机/检测器接入时只需实现同一 Detector Adapter 和批次契约，不把企业图像或保密数据放入仓库。
