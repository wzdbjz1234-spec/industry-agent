# Aegis IQ——工业视觉异常调查与质量闭环智能体平台

> 面向 Agent 开发 / AI 应用开发岗位的个人作品集与简历素材。

## 一、项目名称

**推荐名称：** Aegis IQ——工业视觉异常调查与质量闭环智能体平台

**英文名称：** Aegis IQ — Industrial Visual Anomaly Investigation & Quality Case Agent

其他可选名称：

- 工业视觉异常检测与质量调查 Agent 平台
- 工业质量事件智能调查与决策辅助系统
- Quality Case Investigation Agent
- 面向工业质检的多模态异常调查智能体
- 基于 EfficientAD 与 DeepSeek 的工业异常分析平台

## 二、一页简历可直接粘贴版

### Aegis IQ——工业视觉异常调查与质量闭环智能体平台

**项目类型：** 个人项目 / 独立设计与开发  
**项目角色：** Agent 开发、AI 应用后端开发、前端可视化、系统架构设计  
**项目时间：** `[根据实际情况填写]`

**技术栈：** Python 3.12、FastAPI、Pydantic v2、DeepSeek-V4-Flash、OpenAI-compatible API、Agent Tool Calling、RAG、EfficientAD、PyTorch、OpenCV、React、TypeScript、Vite、Docker Compose、JSON Schema、AsyncAPI、Pytest、Mypy、Ruff、Playwright

**项目简介：**

面向工业视觉质检场景设计并实现异常调查 Agent 平台，将 EfficientAD 等视觉模型产生的连续检测结果聚合为可追踪的质量事件，通过 DeepSeek 大模型调用只读分析工具、检索技术手册和历史案例，生成带证据引用的异常分析及排查建议；经人工审批后创建 QMS 调查任务，形成“异常检测—Agent 调研—人工决策—任务执行—结果归档—案例复用”的完整质量闭环。

**项目职责与技术亮点：**

- 设计并实现工业质量事件端到端处理链路，将图像输入、模型推理、异常指标聚合、Quality Case 创建、Agent 调研、人工审批、QMS 任务和案例归档整合为统一工作流。

- 集成真实 `DeepSeek-V4-Flash` 模型，通过 OpenAI-compatible `/chat/completions` 接口实现 Provider Adapter，并保留确定性离线模型用于无 API Key 环境下的开发、测试和回归验收。

- 自研有边界的单 Agent 调研循环，将模型输出约束为 `TOOL_CALL / FINAL / STOP` 三类结构化 JSON 决策，由应用层负责参数校验、工具白名单检查、循环次数限制、超时处理和异常降级，降低模型越权与失控风险。

- 为 Agent 提供现场快照、统计指标、异常样本、技术手册和历史案例等只读工具；Agent 不直接持有数据库、QMS 或外部系统写权限，所有外部操作必须经过人工审批。

- 设计 A/B/C 三级证据体系，区分当前检测快照、版本化技术文档和历史验证案例，要求分析结论显式关联 Evidence ID；当证据不足时触发安全停止，避免模型强行生成根因结论。

- 构建 RAG 知识检索模块，支持技术手册上传、PDF/文本解析、内容哈希幂等、文档版本管理、适用范围过滤和证据片段引用，并将人工验证后的历史 Case 作为经验性知识参与后续检索。

- 接入 EfficientAD 工业异常检测流程，支持模型目录、ROI、异常阈值和运行设备配置；实现图像路径/Base64 输入、有界异步队列、Job 状态查询、NG 事件发布及滚动窗口 NG 率波动监测。

- 抽象统一视觉检测协议，将 EfficientAD 和 anomlib 风格输出归一化为版本化 `InspectionResultBatch`，支持按检测模型、检测对象、模型版本和阈值切换检测方案。

- 采用固定窗口指标聚合和事件触发机制，避免每张图片都调用 LLM；仅当异常率、异常分数或连续 NG 满足 Case 创建规则后激活 Agent，兼顾推理成本和系统吞吐量。

- 采用模块化单体与 Ports/Adapters 架构，将 Domain、Application、Contracts、Adapters、Entrypoints 分层，隔离视觉模型、LLM、知识库、存储、QMS 等外部依赖，便于替换真实生产基础设施。

- 设计不可变 Quality Case Snapshot，在事件创建时冻结模型版本、阈值、样本窗口和统计指标，确保后续 Agent 分析、人工审核与结果归档均可复现、可审计。

- 实现 Human-in-the-loop 决策机制，Agent 仅生成结构化 Evidence、Analysis 和 Proposal，由质量工程师审批或驳回；审批通过后再由幂等 Worker 创建外部 QMS 调查任务。

- 实现 Mock QMS、签名 Webhook、任务状态同步、投递重试、Pending/DLQ 和人工授权重放机制，模拟外部质量系统可能出现的超时、重复消息和回调失败。

- 构建工业监控 Web 控制台，提供实时监控、检测模型选择、检测对象选择、异常事件中心、事件详情、Agent 执行轨迹、Case 管理、人工审批、QMS 任务、案例库、知识文档、模型评估和运行状态页面。

- Agent 页面仅展示工具调用、执行阶段、证据引用、耗时和结论摘要，不展示或持久化模型隐藏思维链，兼顾系统可解释性、审计能力和模型安全要求。

- 建立固定 Seed 的工业异常数据集重放与评估机制，支持模拟“读取样本—模型推理—异常聚合—激活 Agent—等待人工决策”的完整流程，用于 Agent Prompt、工具策略和安全停止规则的可复现对比。

- 建立 Schema-first 契约管理，目前包含约 51 个 HTTP 路由、30 份 JSON Schema、19 份 Golden Example 以及版本化 AsyncAPI 事件说明。

- 完成后端单元测试、契约测试和集成测试，当前 53 项 Pytest 测试全部通过；Mypy strict 模式检查 103 个源文件无类型错误，Ruff 静态检查和 React/TypeScript 生产构建通过。

## 三、完整技术栈

### Agent 与大模型

- DeepSeek-V4-Flash
- OpenAI-compatible Chat Completions API
- LLM Provider Adapter
- Structured Output / JSON Mode
- Tool Calling
- Tool Allowlist
- Bounded Agent Loop
- Prompt Versioning
- Evidence Grounding
- Agent Safety Stop
- Human-in-the-loop
- Agent Trace
- Retry / Timeout / Error Redaction
- 确定性离线 LLM Adapter

### RAG 与知识工程

- 技术手册与 SOP 检索
- PDF/文本解析
- Pypdf
- 文档版本管理
- 内容哈希去重
- Applicability Filter
- Evidence ID 引用
- 历史验证 Case 检索
- 确定性 Embedding Adapter
- 向量数据库 Port
- pgvector 替换边界
- 分级证据与检索可信度控制

### 工业视觉与算法

- EfficientAD
- PyTorch
- Torchvision
- OpenCV
- NumPy
- Pillow
- Scikit-learn
- ROI 裁剪
- Anomaly Score
- 动态阈值配置
- NG/OK 分类
- 连续图像流
- anomlib 结果归一化接口
- MVTec AD / VisA / BTAD 类公开数据集重放
- 本地 `my_product_raw` 工业图像测试

### 后端与架构

- Python 3.12
- FastAPI
- Pydantic v2
- Uvicorn
- HTTPX
- 模块化单体
- Hexagonal Architecture
- Ports and Adapters
- Domain/Application/Adapter 分层
- Event-driven Architecture
- Immutable Snapshot
- Idempotent Consumer
- Outbox/Worker 语义
- 有界异步任务队列
- Dependency Injection
- Versioned Contract
- JSON Schema
- AsyncAPI

### 前端与可视化

- React
- TypeScript
- Vite
- Lucide React
- 响应式工业 Dashboard
- 异常事件可视化
- Agent Trace 可视化
- Case 状态流转
- 模型/检测对象选择
- 异常评分与 NG 率展示
- 操作反馈与弹窗交互
- Playwright E2E

### 工程质量与部署

- Pytest
- Mypy strict
- Ruff
- TypeScript Compiler
- Docker
- Docker Compose
- API Health Check
- 配置与密钥环境变量管理
- Mock External Service
- Contract Test
- Integration Test
- Fixed-seed Evaluation
- DLQ / Retry / Audit Log

## 四、核心架构与完整业务链路

```text
工业图像
→ EfficientAD 推理
→ 标准化检测事件
→ 异常指标聚合
→ 创建 Quality Case
→ 激活 DeepSeek Agent
→ 调用只读分析工具
→ 生成证据与排查建议
→ 人工审批
→ 创建 QMS 任务
→ 回传执行结果
→ 归档为可信历史案例
```

项目不是简单的聊天机器人。Agent 的核心作用是将异常检测数据转换为可审核、可执行、可追踪的调查方案，并通过人工审批与外部质量系统形成闭环。

## 五、项目特色素材库

### 1. 检测模型与 LLM 解耦

- 视觉模型只负责输出异常分数、阈值、OK/NG 和缺陷元数据。
- 应用层将不同检测器结果统一转换为标准事件。
- Agent 不依赖 EfficientAD 的内部实现。
- 后续可替换 PatchCore、PaDiM、FastFlow、WinCLIP 或其他 anomlib 模型。
- 支持在前端选择检测模型、检测对象和检测方案。
- 模型升级不影响 Case、Agent、审批和 QMS 主流程。

### 2. 避免逐帧调用大模型

工业相机可能持续产生高频图像，如果每张图片都调用 LLM，成本和延迟不可接受。项目采用以下机制：

- 固定时间窗口聚合；
- 连续 NG 判断；
- NG 比例变化判断；
- 异常分数阈值；
- Case 去重与窗口冻结；
- 仅对值得调查的异常窗口激活 Agent。

该设计体现了 AI 应用开发中的模型调用成本控制，而不仅是完成 API 接入。

### 3. 有边界的 Agent 运行机制

- 限制最大 Agent 循环次数；
- 限制单次模型请求超时；
- 工具名称必须属于白名单；
- 工具参数必须经过 Pydantic 校验；
- 模型输出必须符合结构化协议；
- 拒绝模型直接访问外部 QMS；
- 失败时转换为明确的 STOP 状态；
- 对 API Key、Provider 错误和响应正文进行脱敏；
- 支持真实 LLM 与确定性测试模型切换。

### 4. 证据驱动，而非自由生成

Agent 输出被拆分为：

- Evidence：发现了什么；
- Analysis：这些证据可能说明什么；
- Proposal：建议下一步检查什么；
- Limitation：当前还缺少哪些信息；
- Confidence：结论可信程度；
- Evidence IDs：每项判断引用哪些证据。

证据不足时，Agent 会停止并请求补充数据，不将历史相似案例直接当作本次异常的根因证明。

### 5. 不暴露隐藏思维链

前端所展示的“Agent 思考流程”实际是：

- 执行阶段；
- 工具调用；
- 输入输出摘要；
- Evidence ID；
- 运行耗时；
- 决策结果；
- 安全停止原因。

系统不保存和展示模型隐藏 Chain of Thought。这一设计比直接展示“思维链”更符合实际 AI 应用的安全与审计要求。

### 6. RAG 知识库设计

- 支持技术手册和 SOP 上传；
- 支持 PDF 与纯文本解析；
- 使用内容哈希防止重复入库；
- 维护文档版本和适用设备范围；
- 根据检测对象、工位、设备和异常类型过滤文档；
- 检索结果转化为结构化 Evidence；
- 只有经过人工验证的历史 Case 才能进入可信案例库；
- 历史 Case 仅作为经验性参考，不覆盖当前现场证据。

### 7. Human-in-the-loop

- Agent 只生成排查建议，不自动修改生产参数；
- 质量工程师可查看证据、理由和步骤；
- 支持批准或驳回；
- 批准后才触发外部任务创建；
- 审批操作记录操作者、时间、版本和意见；
- Agent 永远不持有外部系统写权限。

### 8. QMS 闭环与可靠性

- 审批事件由独立 Worker 消费；
- 使用幂等键避免重复创建任务；
- 支持签名 Webhook；
- 对外部回调进行签名校验；
- 记录 Pending、Processed、Failed、DLQ 状态；
- 支持人工授权重试；
- 任务关闭后形成 JSON 归档；
- 仅验证有效的案例进入历史知识索引。

### 9. 可观测性设计

系统可查看：

- Vision Worker 状态；
- 图像任务完成数与失败数；
- Agent Worker 处理量；
- Agent 平均耗时；
- 事件投递状态；
- Pending/DLQ 消息；
- Case Timeline；
- Agent Tool Trace；
- QMS 同步状态；
- 模型评估报告。

### 10. 工业可视化前端

主要页面包括：

- 工业异常监控总览；
- 实时视觉监控；
- 检测模型和对象选择；
- 异常事件中心；
- 事件详情弹窗；
- Agent 自动调研轨迹；
- Quality Case 管理；
- 待人工审批建议；
- QMS 调查任务；
- 已验证案例库；
- 技术文档与 RAG 检索；
- Worker 与消息投递监控；
- 模型配置评估；
- ROI 参数化测算；
- 公开数据集重放沙箱。

### 11. 可复现评估

- 使用固定 Seed 保证输入一致；
- 固定数据集、Prompt、模型和工具版本；
- 支持不同 Agent 配置横向比较；
- 记录通过率、工具调用次数、证据覆盖、安全停止和延迟；
- 保留隐藏真值用于验证 Agent 输出；
- ROI 金额明确标记为示例参数，避免将模拟结果包装为真实业务收益。

## 六、Agent 开发岗位强化版

- 基于 DeepSeek-V4-Flash 构建工业质量调查 Agent，将模型能力限制在结构化决策和只读工具调用范围内，实现可控、可审计的 Agent 执行循环。

- 设计 Provider-neutral LLM Port，将 DeepSeek 真实模型与确定性测试 Adapter 解耦，支持通过环境变量切换模型、Base URL、超时和运行模式。

- 设计 `TOOL_CALL / FINAL / STOP` 决策协议，对模型响应执行 JSON 解析、Schema 校验、工具白名单验证和参数校验，防止任意工具调用和非预期外部操作。

- 构建 Evidence-grounded RAG 流程，将现场 Snapshot、指标数据、技术手册和历史案例分级管理，所有分析和 Proposal 必须关联 Evidence ID。

- 引入 Agent Loop Budget、超时、失败降级、安全停止和证据不足保护机制，解决 Agent 在垂直业务中的幻觉、越权和无限循环问题。

- 设计可审计 Agent Trace，仅记录工具调用、证据引用和结论摘要，不记录模型隐藏思维链。

- 通过 Human-in-the-loop 将 Agent 的建议权与系统执行权分离，外部 QMS 写入必须由人工批准并通过幂等 Worker 执行。

## 七、AI 应用开发岗位强化版

- 独立完成工业视觉异常调查平台从算法接入、Agent 编排、后端 API、知识检索到 React 可视化控制台的全栈开发。

- 将 EfficientAD 工业视觉模型封装为可配置推理服务，支持 ROI、阈值、CPU 设备、异步任务和连续图像目录重放。

- 设计统一检测结果协议，使 EfficientAD、anomlib 及其他视觉模型均可接入同一质量事件和 Agent 流程。

- 构建 FastAPI 服务，覆盖视觉任务、异常事件、Case、Agent、审批、QMS、知识库、运维和评估等约 51 个路由入口。

- 建设工业监控 WebUI，实现检测方案选择、异常评分展示、事件详情、Agent Trace、人工审批和系统运行状态可视化。

- 使用 Docker Compose 提供 API/Web 一键启动环境，并通过 Pytest、Mypy、Ruff、TypeScript Build 和 Playwright 建立自动化质量保障。

## 八、面试时的 60 秒项目介绍

> 我做了一个面向工业视觉质检的异常调查 Agent 平台。这个项目不是让大模型直接判断图片，而是由 EfficientAD 等视觉模型持续处理工业图像，再由普通程序对异常分数和 NG 率进行聚合，只有达到调查条件时才创建 Quality Case 并激活 DeepSeek Agent。
>
> Agent 可以调用现场快照、统计指标、异常样本、技术手册和历史案例等只读工具，最终生成带 Evidence ID 的分析和排查建议。为了防止模型越权，我把模型输出限制为 TOOL_CALL、FINAL 和 STOP 三种结构化决策，并加入了工具白名单、循环预算、超时、安全停止和人工审批。审批通过后，独立 Worker 才会创建 QMS 任务，任务完成后再归档为可信历史案例。
>
> 整个系统使用 Python、FastAPI、Pydantic、DeepSeek、EfficientAD、React 和 TypeScript 开发，目前包含完整的异常监控、Agent Trace、审批、QMS、RAG、评估和运维界面，并通过了 53 项后端自动化测试和严格类型检查。

## 九、ATS 关键词

可根据目标 JD 自然加入以下关键词：

`LLM Agent`、`Tool Calling`、`Structured Output`、`Agent Orchestration`、`RAG`、`Evidence Grounding`、`Human-in-the-loop`、`Prompt Versioning`、`Agent Evaluation`、`DeepSeek`、`FastAPI`、`Pydantic`、`Event-driven`、`Ports and Adapters`、`Industrial AI`、`Computer Vision`、`EfficientAD`、`PyTorch`、`Idempotency`、`Observability`、`Docker`、`React`、`TypeScript`

## 十、真实性与能力边界

- 当前 Docker Compose 默认使用确定性内存 Adapter。PostgreSQL、Redis Streams、MinIO 和 pgvector 主要体现为 Port、Adapter 目录及可替换边界，不应描述为已经完成生产部署。

- 当前外部质量系统以 Mock QMS、HTTP Adapter、签名回调和完整流程模拟为主，不应描述为已经接入真实企业 QMS。

- 项目中的产线、设备、SOP、历史 Case 和 QMS 数据主要是合成数据；视觉侧使用公开数据集或本地工业图像进行验证。

- 前端展示的是可审计执行轨迹、工具调用、证据引用与结论摘要，而不是模型隐藏思维链。

- ROI 金额属于参数化示例测算，不代表真实企业收益。

- 不建议在简历中使用尚未经过稳定方法复验的 P50、P95、P99 或 QPS 数据。

- 当前可复验的工程指标包括约 51 个 HTTP 路由、30 份 JSON Schema、19 份 Golden Example、53 项后端自动化测试通过，以及 103 个源文件通过 Mypy strict 检查。

## 十一、一页简历选取建议

一页简历建议从完整素材中保留以下内容：

1. 一段项目简介；
2. 真实 DeepSeek Agent 接入；
3. 有边界的 Tool Calling；
4. 证据驱动 RAG；
5. EfficientAD 与异常事件聚合；
6. Human-in-the-loop 和 QMS 闭环；
7. Ports/Adapters 架构；
8. 前端工业可视化；
9. 自动化测试与可复验量化数据。

## 十二、项目事实依据

- `docs/architecture/system-overview.md`
- `docs/architecture/package-boundaries.md`
- `docs/architecture/event-sequence.md`
- `docs/portfolio/data-and-limitations.md`
- `docs/acceptance/2026-08-23-full-project-acceptance.md`
- `pyproject.toml`
- `web/package.json`
- `efficientad-package/pyproject.toml`

