# 数据真实性、限制与非目标

- 不包含任何企业内部生产数据、保密文档或真实 QMS 记录。
- 产线、批次、设备、技术手册、历史案例和 QMS 数据均为合成数据；检测结果来自固定种子 Replay。
- 当前 Docker Compose 默认使用确定性内存 Adapter，不宣称具备生产级 PostgreSQL/Redis/MinIO 持久化能力。
- 当前 Prompt v1/v2 Eval 使用同一确定性 LLM Adapter，真实模型 Provider 对比需替换 Adapter。
- ROI 中所有金额均为参数化示例测算，不代表真实客户收益。
- EfficientAD 包保持独立；本项目主演示强调事件驱动业务闭环，而不是特定视觉模型。
