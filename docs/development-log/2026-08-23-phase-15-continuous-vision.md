# 阶段 15：EfficientAD 连续视觉入口

## 完成内容

- 使用 `efficientad-package` 提供的 `ImagePipeline` 增加 `EfficientADImagePipelineAdapter`，模型、ROI、阈值和设备均可配置，重依赖只在真正启用时加载。
- 增加 `VisionStreamWorker` 有界队列和后台线程，持续处理来自文件路径或 Base64 的图像，并返回可查询的 Job 状态。
- 将视觉预测统一转换为既有 `inspection.result.batch.v1`，继续进入 Inspection、Metric 和 Quality Case 链路；视觉层不复制业务闭环。
- 增加 `VisionSchemeRegistry` 和 `AnomlibVisionAdapter`，为 anomlib 的 `predict`、`infer`、`detect` 或 callable 方案保留稳定输入接口。
- NG 图像记录 `quality.vision.fault.v1`；按工厂/产线/工位维护滚动窗口，显著上升或下降记录 `quality.vision.ng-rate-fluctuation.v1`。
- 增加视觉契约、JSON Schema、Golden Example、API 集成测试、目录连续处理脚本和运行说明。

## API 入口

```text
GET  /api/v1/vision/schemes
GET  /api/v1/vision/status
POST /api/v1/vision/frames
GET  /api/v1/vision/jobs/{job_id}
GET  /api/v1/vision/events
POST /api/v1/vision/anomlib/detections
```

`/vision/frames` 接收 `image_path` 或 `image_base64` 二选一，异步排队；`/vision/anomlib/detections` 接收 anomlib 已完成的归一化结果，不要求主应用直接依赖 anomlib。

## 真实冒烟

使用仓库提供的 `efficientad-package/.venv`、`output/30/trainings/mvtec_ad/111` 模型和 `mydataset/my_product_raw` 原图完成真实推理：

- EfficientAD 得分约为 `0.2345`，阈值 `0.2`，判定为 NG；
- Heatmap 形状为 `(196, 173)`，与 `roi30` 的 `width,height` 一致；
- 连续目录脚本可完成提交、推理、事件记录和 Job 汇总。

`efficientad-package/data/111/test` 是 168×171 的裁剪图，不能直接套用 `roi30` 原图坐标；演示默认使用 1920×1200 的 `my_product_raw` 图片。

## 验证结果

```text
uv run pytest                         51 passed
uv run ruff check backend scripts     All checks passed
uv run mypy backend/src               Success: no issues found in 102 source files
```

Docker Compose 重建后 API/Web 均为运行态；Docker API 健康检查通过，anomlib HTTP 输入返回 `accepted_count=1`、`is_ng=true`，并产生视觉故障事件。真实 EfficientAD 连续脚本使用提供包环境处理 1 张原图，返回 `completed_count=1`、`failed_count=0`、`ng_count=1`，Job 状态为 `COMPLETED`。

## 边界

当前 Worker、事件 Store 和 Inspection Store 是可审计的内存实现，生产替换点仍是已有 Redis/PostgreSQL/事件端口。Docker API 默认不捆绑 EfficientAD 的大型可选依赖和模型文件；需要真实 EfficientAD 时，应使用提供包的运行环境并配置模型目录，或在部署层挂载专用视觉运行时。
