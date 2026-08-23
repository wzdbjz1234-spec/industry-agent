"""EfficientAD 重构包（src 布局）。

包结构（REFACTOR_PLAN.md 第 3 节）：
- efficientad.model         模型结构、权重加载、预测与评分
- efficientad.training      完整训练、蒸馏、预训练、校准与辅助脚本
- efficientad.application   面向业务的应用能力（ROI、图像流水线）
"""

__version__ = "0.1.0"
