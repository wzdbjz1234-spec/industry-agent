# 2026-08-23：Phase 3 Agent 调查

## 目标

依据设计文档 Phase 3、开发计划 Task 05 和 Task 06，建立一条不依赖外部服务的离线调查链路：

```text
Fixture Offset Case
→ 受控只读 Snapshot/指标工具
→ 文档与已验证案例知识检索
→ provider-neutral LLM Tool Calling
→ 有界调查循环
→ Evidence + Analysis + Proposal + Trace
```

## 实现

- 增加纯标准库知识领域对象：版本化文档、Chunk、检索查询、检索命中和入库回执；
- 增加 `KnowledgeBase`、`EmbeddingProvider` 和 `LLMClient` Port；
- 增加内存知识库 Adapter：Markdown 段落切 Chunk、SHA-256 重复上传检测、ACTIVE/SUPERSEDED、有效时间和适用范围过滤、确定性词法检索；
- 增加知识入库/检索 Application Service，将 Pydantic 契约映射到 Port；
- 增加 `ReadOnlyInvestigationTools`，仅开放 `get_case_snapshot`、`compare_quality_metrics` 和 `search_knowledge_base`；工具参数经过 allowlist 和类型校验，不提供任意 SQL、Python 或 QMS 写操作；
- 增加确定性的 `DeterministicInvestigationLLM`，实现 provider-neutral Tool Calling 决策替身；
- 增加 `InvestigationAgent` 和 `AgentLimits`，实现有限轮次、工具失败和检索预算控制；Trace 只保存工具参数、结果摘要和证据 ID，不保存模型完整思维链；
- 增加 `Evidence`、`Hypothesis`、`InvestigationAnalysis`、`Proposal`、`AgentTrace` 的 Pydantic 契约，支持 JSON 序列化；
- 增加 `scripts/run_phase3_demo.py`，复用 Phase 2 Fixture Offset 场景，离线输出 A 级当前事实、B 级技术文档、C 级历史案例，以及待人工审批 Proposal；
- 增加契约、知识库、Agent 单元和端到端测试；
- 在 `pyproject.toml`/`uv.lock` 中加入 Ruff 和 mypy 开发依赖，并配置 `backend/src` 为 mypy 搜索路径。

## 关键设计决定

### 1. 内存知识库保留未来 pgvector 的替换边界

当前检索使用可复现的词法重叠评分，结果按分数、文档 ID 和 Chunk ID 稳定排序。知识库只作为受控工具出现，Agent 不直接接触存储实现。未来接入 Embedding/pgvector 时只替换 Adapter 和 Embedding Provider。

### 2. 历史案例是 C 级证据

`VERIFIED_CASE` 结果会形成 C 级 Evidence，能够支持候选假设，但不会直接转换为当前 Case 的根因置信度。Analysis 仍要求 A 级 Snapshot 证据，并在输出中保留待验证测量项。

### 3. Agent 只有 Proposal 权限

Agent 只能生成 `PENDING_APPROVAL` Proposal。当前实现没有 QMS 写工具、数据库写工具或任意代码执行工具，外部副作用留给后续人工审批和 QMS Adapter 阶段。

### 4. 确定性优先于真实模型

离线 Adapter 根据已完成工具集合选择固定调查顺序：Snapshot → 指标对比 → 知识检索 → 结构化输出。固定 Case、Seed 和有效日期会产生稳定的 Analysis、Proposal 和 Trace，方便契约测试和 Agent Eval。

## 验证

```powershell
uv run pytest
uv run ruff check backend/src backend/tests simulator scripts
uv run mypy
uv run python scripts/run_phase3_demo.py
```

结果：

- `16 passed`；
- Ruff：`All checks passed!`；
- mypy：`Success: no issues found in 67 source files`；
- Phase 3 Demo：Fixture Offset Case 成功生成 `COMPLETED` Analysis、A/B/C Evidence、`PENDING_APPROVAL` Proposal 和 8 条结构化 Trace 事件。

## 当前限制

- 知识库仍是进程内内存实现，没有 PostgreSQL/pgvector、对象存储或真实 Embedding；
- 文档解析只支持简单文本/Markdown 段落，尚未实现 PDF 解析、上传 API、页面和文件持久化；
- LLM Adapter 是确定性测试替身，不代表真实 Provider 的上下文、Tool Calling 或成本/时延行为；
- Agent 当前只实现 Snapshot、指标摘要和知识检索三个只读工具，代表性样本、图片分析、事件 Worker、Analysis Run 持久化和 Outbox 留待后续阶段；
- Proposal 尚未接入人工审批、Mock QMS 或真实任务创建；
- 运行脚本需通过 `uv run` 使用项目环境，尚未提供安装后可直接执行的独立 CLI 入口。
