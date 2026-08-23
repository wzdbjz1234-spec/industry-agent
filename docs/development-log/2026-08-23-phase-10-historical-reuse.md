# 阶段 10：历史经验复用

## 完成内容

- 归档成功后，将满足 `CONFIRMED + VERIFIED_EFFECTIVE` 条件的案例摘要写入与技术文档共用的知识检索端口。
- 历史案例索引摘要保存产品、工位、异常家族、日期、根因代码、归档 Revision 和完整 JSON `archive_uri`。
- 检索支持 `VERIFIED_CASE` 类型，以及产品、工位、异常家族和日期 Metadata 过滤；不适用产品不会因向量/词法相似而返回。
- 历史案例在 Agent 输出中固定标记为 `evidence_class=C`、`applicability=CONTEXTUAL`，引用指向完整归档 URI。
- Agent 输出明确写入“历史案例不能证明当前根因”的 Claim 和 Limitation；只有当前 A 级事实与技术文档 B 级依据仍可形成行动 Proposal。
- 增加 `GET /api/v1/case-library/{case_id}` 及 `/archive` 别名，用摘要回查完整不可变归档。
- 增加第二次 Fixture Offset 回放入口和 `scripts/run_phase10_demo.py`，展示第一次人工验证经验被第二个 Case 复用。
- 修复检测器重放时同一 Snapshot 的新 Case 外壳覆盖已归档生命周期状态的问题。

## 演示

```powershell
uv run python scripts/run_phase10_demo.py
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
cd web
npm run dev
```

浏览器先通过 API/Mock QMS 完成第一个 Case 的人工确认，再调用：

```text
POST /api/v1/demo/fixture-offset/repeat
```

第二个 Case 的 Analysis 会包含 `VERIFIED_CASE` C 级证据，并可由 `reference` 或案例库页面跳转回第一个 Case 的完整归档。

## 验证结果

```text
uv run pytest -q                         35 passed
uv run ruff check backend/src backend/tests simulator scripts
uv run mypy
npm run build                            (web/)
uv run python scripts/generate_schemas.py
uv run python scripts/verify_package_structure.py
uv run python scripts/run_phase10_demo.py
```

## 当前边界

知识库、归档和案例索引仍是内存实现；生产环境替换为 PostgreSQL/pgvector/MinIO 时，需要保持相同的可信案例元数据过滤、归档 URI 引用和幂等语义。
