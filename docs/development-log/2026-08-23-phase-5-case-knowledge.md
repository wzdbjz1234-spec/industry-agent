# 2026-08-23：Phase 5 Case 与知识入库

## 完成范围

- 建立文档解析、上传元数据和内容哈希幂等边界；
- 支持 ACTIVE/SUPERSEDED 文档状态及生效范围过滤；
- 提供确定性 Embedding、混合检索和 pgvector Port；
- 提供代表性样本只读工具，并将知识引用纳入调查证据链。

## 验证证据

```powershell
uv run pytest backend/tests/unit/test_phase5_knowledge.py backend/tests/integration/test_phase5_knowledge_api.py
uv run python scripts/run_phase5_7_demo.py
```

离线实现保留 PostgreSQL/pgvector、Redis Streams、MinIO 的替换端口；当前验收使用确定性适配器，不伪装成真实基础设施。
