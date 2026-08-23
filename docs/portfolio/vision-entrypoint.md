# EfficientAD 连续视觉输入入口

项目新增了一个连续视觉处理深模块，入口位于：

- `quality_case_agent.application.vision.VisionStreamWorker`：有界队列和后台处理线程；
- `quality_case_agent.adapters.vision.EfficientADImagePipelineAdapter`：调用 `efficientad-package` 提供的 `ImagePipeline`；
- `quality_case_agent.adapters.vision.AnomlibVisionAdapter`：把 anomlib 的 `predict`/`infer`/`detect` 或 callable 结果归一化；
- `quality_case_agent.application.vision.VisionProcessingService`：统一转成既有 `inspection.result.batch.v1`，写入 Inspection/Metric/Case 链路并记录事件。

## HTTP 接口

```text
GET  /api/v1/vision/schemes
GET  /api/v1/vision/status
POST /api/v1/vision/frames
GET  /api/v1/vision/jobs/{job_id}
GET  /api/v1/vision/events
POST /api/v1/vision/anomlib/detections
```

`/vision/frames` 是持续图像入口：请求携带 `image_path` 或 `image_base64` 二选一，返回队列任务；Worker 完成后会把结果写入现有检测摄入管道。NG 图像产生 `quality.vision.fault.v1`，滚动窗口 NG 率显著上升/下降产生 `quality.vision.ng-rate-fluctuation.v1`。

`/vision/anomlib/detections` 是 anomlib 保留入口。anomlib 的任意视觉方案只需输出 `score/anomaly_score`、`threshold`、可选 `is_ng`、缺陷类型和版本元数据，即可作为项目输入，不要求项目直接依赖 anomlib 包。

## 启用 EfficientAD

EfficientAD 运行时是可选依赖。使用仓库提供的模型和 ROI：

```powershell
$env:QUALITY_VISION_EFFICIENTAD_MODEL_DIR = "C:\projects\intelligent-agent\efficientad-package\output\30\trainings\mvtec_ad\111"
$env:QUALITY_VISION_EFFICIENTAD_ROI = "1418,564,173,196"
$env:QUALITY_VISION_EFFICIENTAD_THRESHOLD = "0.2"
$env:QUALITY_VISION_EFFICIENTAD_DEVICE = "cpu"
```

API 进程必须使用已安装 `efficientad-package` 依赖的 Python 环境；没有配置模型目录时，API 仍可使用 anomlib 归一化输入接口，`efficientad` 不会被伪装成已启用。

## 连续目录演示

直接使用 `efficientad-package/.venv` 的 Python，并将两个源码目录加入 `PYTHONPATH`：

```powershell
$env:PYTHONPATH = "C:\projects\intelligent-agent\backend\src;C:\projects\intelligent-agent;C:\projects\intelligent-agent\efficientad-package\src;C:\projects\intelligent-agent\.venv\Lib\site-packages"
& C:\projects\intelligent-agent\efficientad-package\.venv\Scripts\python.exe scripts/run_vision_stream.py --max-images 5 --interval-ms 100
```

当前默认使用 `mydataset/my_product_raw` 中的 1920×1200 图片；`data/111/test` 中的是 168×171 的裁剪图，不适合 `roi30` 的原图坐标。

## anomlib 代码接入

```python
from quality_case_agent.adapters.vision import AnomlibVisionAdapter

adapter = AnomlibVisionAdapter.from_import_path(
    "anomlib.some_scheme:Detector",
    scheme_name="some-scheme",
    model_version="anomlib-model-v3",
    threshold=0.5,
)
container.vision_registry.register("anomlib:some-scheme", adapter)
```

生产环境应将当前内存 Worker、事件 Store 和 Inspection Store 替换为已有 Redis/PostgreSQL/事件端口；本地实现用于可审计的离线验收。
