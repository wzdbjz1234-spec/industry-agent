# efficientad 独立包

EfficientAD 工业缺陷检测重构包（`efficientad.model` / `efficientad.training` /
`efficientad.application`）的独立分发目录。

本目录是自包含的：包源码 + 生产模型权重 + MVTec 格式数据集 + ORB 模板，
布局与主仓库一致，可脱离仓库独立安装/部署。

```text
efficientad-package/
├── pyproject.toml
├── README.md
├── src/efficientad/        # 包源码（model / training / application）
│   ├── resources/           # 内置 EfficientAD teacher_small 权重
├── data/                   # MVTec AD 格式数据集
│   ├── 111/                #   模型30 的产品数据（train + test）
│   └── 222/                #   模型31 的产品数据
├── output/                 # 训练产物（final 权重 + norm_params.json）
│   ├── 30/trainings/mvtec_ad/111/
│   ├── 31/trainings/mvtec_ad/222/
│   ├── batch=4/trainings/mvtec_ad/my_product/
│   └── verytiny-batch=4/trainings/mvtec_ad/my_product/
├── templates/              # ORB ROI 模板
└── dist/                   # 构建好的 wheel
```

## 安装

```powershell
# 方式一：源码安装（开发）
pip install -e .

# 方式二：安装构建好的 wheel
pip install dist\efficientad-0.1.0-py3-none-any.whl

# 方式三：直接使用（不安装）
set PYTHONPATH=%cd%\src
```

依赖（自动安装）：`numpy`、`torch`、`torchvision`、`opencv-python`、`pillow`、
`tqdm`、`tifffile`、`matplotlib`、`scikit-learn`。

## 训练

`efficientad-package` 已包含 `EfficientAD-main` 的完整训练实现，不需要再从
仓库外导入 `common.py` 或执行 `EfficientAD-main/efficientad3.py`。默认会自动
使用包内置的 `teacher_small.pth`，并根据 CUDA 是否可用选择 GPU/CPU。

MVTec 格式数据集的目录应为：

```text
<dataset>/<subdataset>/train/good/*.png
<dataset>/<subdataset>/test/good/*.png
<dataset>/<subdataset>/test/<defect>/*.png
```

例如使用当前仓库已经裁剪好的 ROI 数据训练两个模型：

```powershell
cd C:\projects\efficientAD\efficientad-package
$env:PYTHONPATH = "$PWD\src"

python -m efficientad.training.efficientad3 `
  --dataset C:\projects\efficientAD\mydataset `
  --subdataset retrained_roi30 `
  --name ROI-30 `
  --output_dir .\output\retrained_roi30 `
  --train_steps 70000 --batch-size 16 --num-workers 4 --mask-config none

python -m efficientad.training.efficientad3 `
  --dataset C:\projects\efficientAD\mydataset `
  --subdataset retrained_roi31 `
  --name ROI-31 `
  --output_dir .\output\retrained_roi31 `
  --train_steps 70000 --batch-size 16 --num-workers 4 --mask-config none
```

其中 `--subdataset` 只表示输入数据目录，`--name`（也可写成
`--product-name`）才是用户自定义的检测目标/模型名称。例如上面的两个模型
会分别写入 `trainings/mvtec_ad/ROI-30/` 和 `trainings/mvtec_ad/ROI-31/`。
如果不传 `--name`，程序会使用 `--subdataset` 作为兼容性回退，不会自动使用
`bottle`。旧版上游脚本生成的 `output/.../mvtec_ad/bottle/` 目录不会被自动删除，
如果 UI 仍显示它，那是历史模型目录，重新训练并选择新名称即可区分。

也可以在安装后使用控制台命令：

```powershell
efficientad-train --help
```

训练产物会写入 `<output_dir>/trainings/mvtec_ad/<name>/`，包括
`teacher_final.pth`、`student_final.pth`、`autoencoder_final.pth`、
`norm_params.json`、损失曲线、测试热力图和最终 AUC。训练过程仍然是显式写盘行为；
推理流水线本身不会自动保存。

## 图形界面（单图 → 两个模型目录 → 两个 ROI → 检测）

```powershell
# 方式一：免安装启动器（推荐，本目录下直接运行）
python run_ui.py
python run_ui.py `
  --image C:\projects\efficientAD\mydataset\my_product_raw\test\broken\001K8_0031.png `
  --model30 .\output\30\trainings\mvtec_ad\111 `
  --model31 .\output\31\trainings\mvtec_ad\222

# 方式二：双击 run_ui.bat

# 方式三：模块形式（需已安装包或设置 PYTHONPATH=src）
python -m efficientad.application.ui

# 方式四：安装包后的控制台脚本
pip install dist\efficientad-0.1.0-py3-none-any.whl
efficientad-ui
```

> 注意：不要直接运行 `python src\efficientad\application\ui\app.py`——
> 那样 `src/` 不在模块搜索路径中，会报 `ModuleNotFoundError: No module named 'efficientad'`。
> 请使用上面的启动器或模块形式。

## 快速开始（使用本包自带的数据与模型）

```python
from efficientad.application import ImagePipeline, FixedROIProcessor
from efficientad.model import ModelArtifacts, ModelRunner

# 1. 模型加载（source_dir 默认解析到本包根，即 output/ 所在目录）
artifacts = ModelArtifacts.from_output('30', product='111')  # 或 source_dir='.'
runner = ModelRunner.load(artifacts, device='cpu', teacher_free=True)

# 2. 流水线：ROI 裁剪 + 掩膜 + 推理（纯内存，无副作用）
pipeline = ImagePipeline(
    roi=FixedROIProcessor((1418, 564, 173, 196)),
    model=runner,
    threshold=0.2,
)
result = pipeline.process('data/111/test/broken/001K8_0031.png')

result.loss        # 原始异常差异图有效区均值
result.score       # 归一化异常分数（与阈值比较）
result.heatmap     # 归一化热力图 (H,W) float32
result.is_anomaly  # score >= threshold
```

界面默认使用本包的两个固定 ROI 配置：

```text
roi_configs/roi30.json
roi_configs/roi31.json
```

也可以在界面中分别选择其他 ROI JSON。两个模型目录分别选择
`student_final.pth`、`autoencoder_final.pth` 和 `norm_params.json` 所在的目录，
不要求目录名是 `my_product`。

检测完成后，界面会同时显示：原图上的两个 ROI 框和热力图、ROI-30 裁剪热力图、
ROI-31 裁剪热力图、每个 ROI 的 loss/score/threshold/判定，以及整体判定。

检测页还提供：

- 模型目录完整性检查（Student / AE / Norm）；
- 热力图透明度调节；
- 整体判定策略：任一 ROI 异常、两个 ROI 都异常、最高相对阈值。

ORB 模板仍可由应用包 API 使用，但新的双 ROI UI 使用固定 ROI 配置：

```python
from efficientad.application import ORBROIProcessor
processor = ORBROIProcessor('my_template')  # 模板在 templates/my_template/
```

## 归一化参数校准（数据在 data/）

```powershell
python -m efficientad.training.calibration --model 30 --product 111 `
  --source-dir . --train-dir data\111\train
```

模型产物布局与主仓库一致：`<source_dir>/output/<id>/trainings/mvtec_ad/<product>/`。

## 主要 API

| 模块 | 能力 |
|---|---|
| `efficientad.model.ModelArtifacts` | 模型产物（权重/norm 路径）定位 |
| `efficientad.model.ModelRunner` | 加载 + 预测：`predict` / `predict_batch` / `maps_tensor` |
| `efficientad.model.scoring` | 评分纯函数（loss/score/heatmap 定义） |
| `efficientad.application.roi` | `FixedROIProcessor` / `ORBROIProcessor`，失败抛明确异常 |
| `efficientad.application.imagepipeline` | `ImagePipeline.process(image)`，无副作用 |
| `efficientad.training.efficientad3` | 完整 EfficientAD teacher/student/AE 训练与测试 |
| `efficientad.training.calibration` | 归一化参数显式校准 |
| `efficientad.training.distill_teacher` | Teacher 蒸馏 |
| `efficientad.training.pretraining` | PDN 预训练 |
| `efficientad.training.inference` | 独立批量推理脚本 |
| `efficientad.training.visualize_features` | 特征差异可视化 |

## 约定

- 输入图像：`Path | str | PIL.Image | numpy.ndarray`；NumPy 数组为 **BGR**。
- 热力图尺寸 = ROI 裁剪图尺寸（非整幅原图）。
- `loss` = 归一化前原始差异图在有效区域内的均值；`score` = 归一化图最大值。
- 掩膜坐标相对 ROI 左上角。
- `source_dir` / `templates_dir` 均可显式指定；默认智能解析到本包根。

## 与主仓库的关系

本目录是 `src/efficientad` 的独立快照 + 生产数据/模型，用于脱离仓库分发/部署。
主仓库的重构进度见 `REFACTOR_PLAN.md` 与 `DEVLOG.md`。
