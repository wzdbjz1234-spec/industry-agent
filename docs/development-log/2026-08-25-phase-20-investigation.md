# Phase 20 开发日志：通用证据驱动调查

日期：2026-08-25

## 目标

把 `InvestigationAgent` 从按 `trigger_family` 拼接固定假设，收缩为通用的
Runbook 驱动调查模块。模型只负责受限决策，最终 Hypothesis/Proposal 必须经过应用侧证据校验和安全策略。

## 本次改动

### 1. 建立 InvestigationModule seam

- 新增 `InvestigationRequest` 和 `InvestigationModule.investigate()` 外部接口。
- `InvestigationService` 改为依赖该接口；兼容保留 `InvestigationAgent.analyze()` 作为旧调用入口。
- `InvestigationAgent` 只保留有界循环、工具白名单、检索预算、失败预算和 Trace 组装。

### 2. Runbook 和 Planner

- 新增严格的 `RunbookContract`、不可执行的 domain value objects 和校验转换。
- 新增 `knowledge_base/runbooks/*.json`：夹具偏移、光照漂移和通用兜底三份版本化 Runbook。
- `RunbookRegistry` 对 JSON 做 Pydantic `extra=forbid` 校验；文件缺失时使用同等安全的内置兜底。
- `InvestigationPlanner` 根据 Snapshot 数据质量和可用工具生成 required tool plan 及知识检索 query。

### 3. Synthesizer、Grounding、Policy

- `InvestigationSynthesizer` 从 Observation + Runbook 生成结构化 Evidence、Hypothesis 和 Proposal。
- `EvidenceGroundingValidator` 拒绝未知证据引用、C 级历史案例支撑当前假设、缺少 A/B 依据的 Proposal。
- `InvestigationSafetyPolicy` 在数据质量警告或 Grounding 失败时强制停止并返回补数要求。
- 输出新增 `runbook_id/version`、`toolset_version`、`prompt_version`、`model_version`、`retrieval_index_version`。

### 4. 只读外部事实工具

- 新增 `EquipmentPort`、`ChangeLogPort` 及 Mock/HTTP 适配器。
- `ReadOnlyInvestigationTools` 支持可选的设备状态和变更记录查询；未注入适配器时不会出现在 allowlist。
- HTTP 适配器只做协议转换，不包含任何写操作或任意代码执行能力。

### 5. 评测资产

- 新增 Runbook 合同、注册表、Grounding Validator 和对抗数据集测试。
- 新增 `evaluation/datasets/adversarial/phase20_grounding_cases.jsonl`，覆盖历史案例滥用、缺少适用规范、矛盾证据和合法 Proposal。

## 实现方法与关键不变量

```text
Snapshot -> RunbookRegistry -> Planner -> allowlisted ToolRegistry
         -> structured Observations -> Synthesizer -> Grounding Validator -> Policy
```

- Runbook 是数据，不是脚本：不允许 Python、Shell、SQL 或任意工具名绕过注册表。
- C 级历史案例只能生成上下文证据，不能加入 Hypothesis 的支持证据集合。
- Proposal 同时要求本次 Case 的 A 级事实和适用 B 级规范；否则返回无 Proposal 的安全结果。
- 所有外部工具仍然是只读操作；QMS 写入仍只存在于人工批准后的既有流程。

## 量化验证

| 检查 | 结果 |
| --- | --- |
| Output Schema | 所有 Agent 输出通过 Pydantic 契约 |
| Grounding 单元测试 | 合法 A/B、未知引用、C 级误用均覆盖 |
| Runbook 安全校验 | 未知字段和 `python` 字段被拒绝 |
| 历史复用回归 | C 级 evidence 保持 CONTEXTUAL，限制语句保留 |
| 全量后端测试 | 79 passed |
| Ruff | passed |
| Mypy | 150 个源码文件无错误 |

## 已知边界与下一步

- 当前确定性 LLM 仍是离线替身，真实模型接入后需要实现结构化 Draft 解析和字段级拒答评测。
- 设备/变更工具已建立 seam，但默认 Demo 未接入真实 HTTP Endpoint；Phase 21 再做影子 QMS、身份和审计。
- 当前对抗数据集是评测骨架，需补充脱敏历史回放和固定模型多次重复运行，计算路线图中的 Recall、Precision 和 Abstention 门槛。
