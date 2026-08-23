# 面试讲解稿

1. 高频检测结果不会逐件调用 LLM；普通程序先聚合指标并创建值得调查的 Quality Case。
2. Snapshot 冻结当前事实，Agent 只能使用 allowlist 只读工具，输出 A/B/C Evidence 和 Proposal。
3. Proposal 必须经过人工批准，QMS Worker 以消费组幂等方式创建外部任务；失败消息进入 Pending/DLQ。
4. QMS 结果通过签名 Webhook 回传，只有验证有效的 Case 才进入可信历史索引；历史结果永远是 C 级上下文，不证明当前根因。
5. 证据不足场景显式安全停止，光照漂移场景使用独立检测规则和维护手册，避免 Fixture Offset 假设污染。
6. Eval 使用固定种子、隐藏真值和两组配置对比；ROI 只做可调参数的示例测算，不声称真实工厂收益。

重点追问的设计权衡：离线确定性 Adapter 换取可重复验收；真实 PostgreSQL/Redis/MinIO/模型通过 Port 替换；Agent 不拥有 QMS 写权限。
