# Quality Case Investigation Agent 开发计划

> 基于《Event-Driven Quality Case Investigation Agent》设计方案的垂直切片开发路线

## 1. 计划目标

本计划用于把设计方案落实为一个可运行、可测试、可演示的个人作品集项目。

开发顺序遵循两个原则：

1. 首先冻结包结构、技术栈和跨进程协议，避免开发过程中反复调整系统边界；
2. 后续每个开发任务都交付一条可以独立运行和演示的垂直功能，而不是分别开发“全部数据库”“全部后端”或“全部前端”。

每个垂直任务应尽量同时包含：

```text
输入或触发
→ 领域逻辑
→ 持久化/消息
→ API
→ 最小WebUI
→ 自动测试
→ 可演示结果
```

---

## 2. 开发原则

### 2.1 先跑通主链路，再增加能力

第一条主链路是：

```text
模拟检测结果
→ 批量接入
→ 指标聚合
→ 创建Quality Case
→ Redis事件触发Agent
→ Agent生成分析和Proposal
→ 人工审批
→ Mock QMS任务
→ 人工回传结果
→ JSON归档和可信案例索引
```

在这条链路完整跑通前，不开发通用聊天、多Agent、定时报表、复杂模型优化或真实MES/QMS连接器。

### 2.2 每个任务必须可验证

一个任务只有同时满足以下条件才算完成：

- 代码路径已经端到端连通；
- 核心失败路径有处理；
- 有自动测试；
- 有本地运行命令；
- WebUI或命令行能够展示结果；
- 文档中记录了输入、输出和限制；
- 不依赖尚未实现的“未来模块”才能演示。

### 2.3 协议优先

- 跨进程通信只使用版本化协议；
- 消息消费者不能直接依赖生产者内部类；
- Pydantic模型生成JSON Schema；
- OpenAPI生成前端TypeScript类型；
- 协议变更必须有兼容性测试；
- 已发布的`v1`字段不随意改名或改变语义。

---

## 3. 技术栈冻结

### 3.1 后端

| 类别 | 决定 | 用途 |
|---|---|---|
| 语言 | Python 3.12 | API、Worker、Agent、模拟器 |
| 包管理 | uv | 依赖锁定、虚拟环境和命令执行 |
| Web框架 | FastAPI | REST API、Webhook、SSE |
| 数据校验 | Pydantic v2 | API和事件Schema |
| ORM | SQLAlchemy 2.x async | PostgreSQL访问 |
| 数据库驱动 | asyncpg | 异步PostgreSQL连接 |
| 数据迁移 | Alembic | Schema迁移 |
| 消息客户端 | redis-py asyncio | Redis Streams |
| 对象存储 | MinIO Python SDK | 图片和Case JSON归档 |
| 向量检索 | PostgreSQL + pgvector | 技术文档和可信历史案例 |
| HTTP客户端 | httpx | QMS、Embedding和LLM适配器 |
| 测试 | pytest、pytest-asyncio | 单元与集成测试 |
| 代码质量 | Ruff、mypy | 格式、静态检查 |
| 配置 | pydantic-settings | 环境变量配置 |
| 日志 | structlog或标准库JSON Formatter | 结构化日志 |

具体补丁版本由`uv.lock`锁定；开发计划只冻结技术选择，不在文档中硬编码易过时的小版本号。

### 3.2 Agent

| 类别 | 决定 |
|---|---|
| Agent形态 | 单个Investigation Agent |
| 循环 | 自己实现的有界ReAct/Tool Calling循环 |
| 模型协议 | Provider-neutral `LLMClient`，支持OpenAI-compatible Tool Calling |
| 输出 | Pydantic结构化输出 |
| 工具 | 领域化、Typed、默认只读 |
| Checkpoint | PostgreSQL保存Analysis Run和Trace Step |
| RAG | Agent自主调用`search_knowledge_base`工具 |
| Embedding | Provider-neutral `EmbeddingClient` |
| 权限 | Agent只能提交Analysis和Proposal，不能调用QMS写接口 |

第一版不引入LangGraph。Agent运行时通过接口隔离；如果后续需要框架能力，可以替换内部实现而不改变业务协议。

### 3.3 前端

| 类别 | 决定 |
|---|---|
| 语言 | TypeScript |
| UI框架 | React + Vite |
| 路由 | React Router |
| 服务端状态 | TanStack Query |
| 图表 | ECharts |
| 样式 | CSS Modules或轻量组件库，项目内统一一种 |
| 实时更新 | 原生EventSource接收SSE |
| API类型 | 从OpenAPI生成TypeScript类型 |
| 端到端测试 | Playwright |

不使用Streamlit作为最终主界面；Streamlit也不作为并行维护的第二套UI。

### 3.4 基础设施

| 组件 | 决定 | 职责 |
|---|---|---|
| PostgreSQL | 主数据库 | 业务事实、指标、Agent运行、文档Metadata |
| pgvector | PostgreSQL扩展 | 文档Chunk和可信历史案例Embedding |
| Redis Streams | 消息系统 | 检测数据队列和Quality Case生命周期事件 |
| MinIO | S3兼容对象存储 | NG图片、热力图和完整Case JSON |
| Docker Compose | 本地编排 | 一键启动所有依赖和应用进程 |
| GitHub Actions | CI | Lint、类型、测试和构建 |

### 3.5 暂不采用

- Kafka；
- Kubernetes；
- TimescaleDB；
- 多Agent框架；
- 任意SQL Agent；
- 任意Python执行沙箱；
- 独立向量数据库；
- GraphRAG；
- WebSocket；
- 微服务多仓库。

---

## 4. 包结构冻结

项目采用Monorepo。Python后端是模块化单体代码库，通过不同Entry Point启动多个进程。

```text
quality-case-agent/
├── README.md
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-lock.yaml
├── docker-compose.yml
├── .env.example
├── Makefile                         # Windows外环境的便捷命令，可选
│
├── backend/
│   ├── alembic.ini
│   ├── migrations/
│   ├── src/
│   │   └── quality_case_agent/
│   │       ├── contracts/           # Pydantic消息/API契约
│   │       │   ├── common.py
│   │       │   ├── inspection.py
│   │       │   ├── quality_case.py
│   │       │   ├── investigation.py
│   │       │   ├── qms.py
│   │       │   └── knowledge.py
│   │       │
│   │       ├── domain/              # 无网络/数据库依赖的领域模型
│   │       │   ├── inspection/
│   │       │   ├── quality_case/
│   │       │   ├── investigation/
│   │       │   └── knowledge/
│   │       │
│   │       ├── application/         # 用例与Port接口
│   │       │   ├── ingestion/
│   │       │   ├── metrics/
│   │       │   ├── case_detection/
│   │       │   ├── investigation/
│   │       │   ├── approval/
│   │       │   ├── archival/
│   │       │   └── ports/
│   │       │
│   │       ├── adapters/            # Port的外部实现
│   │       │   ├── postgres/
│   │       │   ├── redis_streams/
│   │       │   ├── minio/
│   │       │   ├── pgvector/
│   │       │   ├── llm/
│   │       │   ├── embeddings/
│   │       │   ├── detector/
│   │       │   └── qms/
│   │       │
│   │       ├── entrypoints/
│   │       │   ├── api/             # FastAPI routes、依赖注入、SSE
│   │       │   ├── mock_qms/        # 独立Mock QMS FastAPI入口
│   │       │   ├── workers/         # Redis/Outbox/Archive消费者
│   │       │   └── cli/             # 管理和Demo命令
│   │       │
│   │       ├── config.py
│   │       ├── logging.py
│   │       └── bootstrap.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── contracts/
│       └── agent_evals/
│
├── web/
│   ├── package.json
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── overview/
│   │   │   ├── inspections/
│   │   │   ├── cases/
│   │   │   ├── investigations/
│   │   │   ├── documents/
│   │   │   ├── case_library/
│   │   │   └── operations/
│   │   ├── routes/
│   │   └── generated/               # OpenAPI生成，禁止手改
│   └── tests/
│
├── simulator/
│   ├── scenarios/
│   │   ├── normal/
│   │   ├── fixture_offset/
│   │   ├── illumination_drift/
│   │   └── insufficient_evidence/
│   └── fixtures/
│
├── knowledge_base/
│   ├── manuals/
│   ├── sop/
│   ├── fmea/
│   └── seed_verified_cases/
│
├── contracts/
│   ├── json-schema/                 # 从Pydantic生成
│   ├── examples/                    # 协议示例消息
│   └── asyncapi/                    # Redis业务事件目录
│
├── docs/
│   ├── architecture/
│   ├── adr/                         # Architecture Decision Records
│   ├── development-log/
│   ├── demo/
│   └── evaluation/
│
└── scripts/
    ├── generate_schemas.py
    ├── generate_openapi.py
    ├── seed_demo.py
    └── verify_contracts.py
```

### 4.1 包依赖规则

```text
contracts ───────────────► 不依赖业务实现
domain ──────────────────► 只依赖标准库和必要值对象
application ─────────────► domain + contracts + ports
adapters ────────────────► application ports + 外部SDK
entrypoints ─────────────► application + adapters + contracts
```

禁止：

- `domain`导入FastAPI、SQLAlchemy、Redis或LLM SDK；
- API Route直接写SQL；
- Worker直接拼接未经Schema校验的消息；
- Agent Tool直接访问全局数据库Session；
- WebUI维护一套与OpenAPI不同的手写响应类型；
- 模拟器导入业务内部Repository实现。

### 4.2 运行进程

以下进程可以共享一个后端Docker镜像，通过不同命令启动：

```text
api
inspection-db-writer
metrics-worker
case-detector
outbox-publisher
investigation-worker
qms-integration-worker
case-archive-worker
mock-qms
simulator
web
```

共享代码不等于共享运行生命周期。任何Worker崩溃不应终止API或其他Worker。

---

## 5. 协议冻结

### 5.1 同步协议

| 通信方向 | 协议 |
|---|---|
| WebUI → Backend | REST/JSON over HTTP |
| Backend → WebUI状态更新 | SSE |
| Simulator/Detector → Ingestion | REST批量JSON |
| QMS Adapter → Mock QMS | REST/JSON |
| Mock QMS → Backend | 签名Webhook/JSON |
| Backend → LLM/Embedding | Provider Adapter内部HTTP |
| Backend → MinIO | S3 API |

### 5.2 异步协议

| Stream | 消息 |
|---|---|
| `inspection:results` | `inspection.result.batch.v1` |
| `quality:case-events` | 版本化Quality Case生命周期事件 |
| `quality:case-events:dlq` | 统一失败消息 |

Redis采用Consumer Group和at-least-once交付。消费者以`event_id`实现幂等，成功持久化后才`XACK`。

### 5.3 Schema唯一来源

```text
backend/contracts中的Pydantic模型
        │
        ├── 生成OpenAPI
        ├── 生成JSON Schema
        ├── 生成contracts/examples校验
        └── 生成Web TypeScript类型
```

事件目录使用AsyncAPI或等价Markdown/JSON文件记录，但字段Schema引用生成后的JSON Schema，不重复手写第二份定义。

### 5.4 时间、ID和金额

- 服务内部和消息统一使用UTC；
- 时间格式使用带`Z`的ISO 8601，例如`2026-08-22T02:30:00.123Z`；
- WebUI按用户时区展示，Demo默认`Asia/Shanghai`；
- 技术ID使用ULID字符串，便于排序；
- 人类可读Case编号另存为`case_number`，例如`QC-20260822-0042`；
- 比例统一使用`0.0～1.0`，UI负责转换为百分比；
- 金额使用Decimal字符串和ISO 4217货币代码，不使用浮点数；
- 所有消息必须包含`schema_version`或通用事件信封的`spec_version + event_type`。

### 5.5 错误响应

所有HTTP错误使用统一格式：

```json
{
  "error": {
    "code": "CASE_NOT_FOUND",
    "message": "Quality Case does not exist.",
    "details": {},
    "trace_id": "trace_01K2Q9"
  }
}
```

业务错误使用稳定`code`，前端不依赖英文`message`判断逻辑。

### 5.6 幂等协议

| 场景 | 幂等键 |
|---|---|
| 检测结果 | `result_id` |
| 检测批次提交 | `batch_message_id` |
| Redis业务事件 | `event_id` + `consumer_group` |
| 自动Agent运行 | `case_id + snapshot_id + trigger_event_id` |
| 人工重新分析 | `request_id` |
| Proposal审批 | `decision_id` |
| QMS任务创建 | `proposal_id` |
| QMS结果Webhook | `event_id`或QMS结果ID |
| 历史案例索引 | `case_id + archive_revision` |

### 5.7 版本兼容规则

- 新增可选字段属于兼容变更；
- 删除字段、改名、改变单位或语义属于不兼容变更；
- 不兼容变更创建新的事件主版本，例如`.v2`；
- Consumer必须忽略未知可选字段；
- 每个协议至少保留一个Golden Example并在CI中解析验证；
- 任何Schema变更必须同时更新生产者、消费者契约测试和文档。

---

## 6. Definition of Done

所有开发任务共用以下完成标准：

- [ ] 功能从真实入口运行到真实输出，不使用手工修改数据库完成演示；
- [ ] 新增协议有Pydantic模型、JSON Schema和Golden Example；
- [ ] 数据库变更有Alembic Migration；
- [ ] 核心领域逻辑有单元测试；
- [ ] 跨PostgreSQL、Redis或MinIO路径有集成测试；
- [ ] 前端关键流程有至少一个Playwright测试；
- [ ] 错误路径在UI或日志中可见；
- [ ] 日志包含`trace_id`和`case_id`；
- [ ] Ruff、mypy、pytest和前端构建通过；
- [ ] README或对应文档包含运行及演示命令；
- [ ] 不引入与当前任务无关的新基础设施。

---

## 7. 开发任务总览

| 顺序 | 任务 | 垂直交付结果 | 依赖 |
|---:|---|---|---|
| 00 | 工程骨架与协议基线 | 空系统一键启动，协议可生成和校验 | 无 |
| 01 | 正常检测数据接入 | 模拟器发送结果，WebUI看到逐件记录 | 00 |
| 02 | 质量指标窗口 | WebUI看到NG率和Score趋势 | 01 |
| 03 | Fixture Offset Quality Case | 异常场景自动创建Case与Snapshot | 02 |
| 04 | 可靠Case事件投递 | Outbox发布、Consumer接收、崩溃可恢复 | 03 |
| 05 | 企业文档入库与检索 | 上传手册并按适用范围检索到引用 | 00 |
| 06 | Case调查Agent | Case事件自动生成带证据分析 | 04、05 |
| 07 | Proposal与人工审批 | WebUI批准或驳回Agent建议 | 06 |
| 08 | Mock QMS业务接入 | 批准后自动创建外部调查任务 | 07 |
| 09 | 人工结论与知识闭环 | QMS回传后归档并索引可信案例 | 08 |
| 10 | 历史经验复用 | 新Case检索上一次已验证结果 | 09 |
| 11 | 光照漂移与证据不足 | 第二类异常及安全停止可演示 | 06 |
| 12 | 可观测性与故障控制台 | UI展示Trace、失败、重试和DLQ | 04、06 |
| 13 | Agent Eval与ROI看板 | 可重复评估并展示价值指标 | 09～12 |
| 14 | 作品集交付 | 一键Demo、视频、架构与面试材料 | 全部 |

任务05可以与任务01～04并行开发，但单人实施时建议按表中顺序完成，以降低上下文切换。

---

## 8. 详细开发任务

## Task 00：工程骨架与协议基线

### 目标

冻结工程边界，并让空系统能够一键启动、迁移数据库、生成协议和运行CI。

### 垂直路径

```text
docker compose up
→ PostgreSQL/Redis/MinIO/API/Web启动
→ /health检查依赖
→ WebUI显示系统状态
→ CI校验协议和代码质量
```

### 实现内容

- 创建Monorepo目录；
- 初始化Python 3.12和uv；
- 初始化React、TypeScript和Vite；
- 建立`domain/application/adapters/entrypoints/contracts`包；
- 配置PostgreSQL、pgvector、Redis、MinIO和Docker Compose；
- 建立FastAPI`/health/live`和`/health/ready`；
- 建立WebUI System Status页；
- 建立Alembic空基线；
- 实现统一配置、结构化日志和Trace ID Middleware；
- 把最新设计文档中的消息建成Pydantic模型；
- 生成JSON Schema、OpenAPI和TypeScript类型；
- 添加Golden Example解析测试；
- 添加GitHub Actions。

### 验收标准

- `docker compose up`后所有依赖健康；
- Ready Check能够区分PostgreSQL、Redis和MinIO故障；
- 前端不手写API响应类型；
- 所有设计消息示例通过Schema校验；
- CI运行Ruff、mypy、pytest和前端构建；
- 包依赖规则有自动或静态检查。

### 演示

打开System Status页面，依次停止Redis和MinIO，展示Ready状态变化及带Trace ID的错误响应。

---

## Task 01：正常检测数据接入

### 用户故事

作为系统集成工程师，我可以让一个可替换Detector Adapter批量发送检测结果，并在WebUI看到最近入库记录。

### 垂直路径

```text
Normal Scenario Simulator
→ POST InspectionResultBatch
→ inspection:results
→ DB Writer
→ PostgreSQL
→ GET recent inspections
→ WebUI
```

### 实现内容

- `inspection.result.batch.v1`接入API；
- 请求Schema、条数和大小限制；
- Redis Stream Producer；
- DB Writer Consumer Group；
- `inspection_results`表和批量Insert；
- `result_id`与`batch_message_id`幂等；
- Normal Scenario模拟器；
- 最近检测记录API；
- WebUI最近记录表格、OK/NG标识和接入速率；
- DB Writer Pending恢复基础逻辑。

### 验收标准

- 同一批消息发送两次不会产生重复记录；
- DB Writer在数据库短暂不可用时不丢失未确认消息；
- 图片字段只传URI，不在Redis传二进制；
- 100条批量消息可正常校验、入队、落库和显示；
- Detector实现可以替换，后端不导入EfficientAD代码。

### 演示

启动Normal Scenario，WebUI实时显示吞吐、最近结果和模型版本；重复提交相同批次后数据库数量不增加。

---

## Task 02：质量指标窗口

### 用户故事

作为质量工程师，我可以查看指定工位和产品的NG率、异常分数和空间分布趋势，而不需要扫描逐件记录。

### 垂直路径

```text
inspection_results
→ Metrics Worker
→ quality_metrics
→ Metrics API
→ ECharts趋势图
```

### 实现内容

- `quality_metrics`表；
- 1分钟和5分钟固定窗口；
- `total_count`、`ng_count`、`ng_rate`；
- Score mean、P95；
- 区域计数和占比；
- Worker幂等重算；
- 按工位、产品和时间范围查询API；
- Overview趋势图和过滤器；
- 空窗口、迟到记录和混合模型版本标记。

### 验收标准

- 给定固定Fixture数据，聚合结果与预期完全一致；
- 重跑同一窗口不会产生重复指标；
- UI比例与API的`0～1`单位转换正确；
- 窗口显示使用本地时区，但API保持UTC；
- 混合模型版本时生成数据质量Warning。

### 演示

回放固定Normal数据，展示1分钟和5分钟窗口切换、NG率和P95趋势。

---

## Task 03：Fixture Offset Quality Case

### 用户故事

作为质量工程师，当NG率与空间分布连续异常时，我希望系统自动形成一个可调查Case，而不是收到大量逐件NG告警。

### 垂直路径

```text
Fixture Offset Scenario
→ Metrics Worker
→ Event Detector
→ Case聚合规则
→ Quality Case + Immutable Snapshot + Outbox
→ Case列表和详情页
```

### 实现内容

- Fixture Offset场景数据；
- 规则版本配置；
- 连续越界、Hysteresis、恢复窗口；
- Case Fingerprint和异常过程合并；
- `quality_cases`、`quality_case_snapshots`、`quality_episode_metrics`；
- Case、Snapshot和Outbox同事务写入；
- Snapshot Hash和不可变约束；
- `episode_status`与`case_status`；
- Case列表和Case详情页；
- 指标、分布和代表性样本展示。

### 验收标准

- 单个NG不会创建Case；
- 连续满足规则后只创建一个Case；
- 异常持续时不重复创建Case；
- Snapshot包含Observation、Lookback、Baseline和Data Quality；
- Snapshot创建后API不提供修改接口；
- 指标恢复只改变`episode_status`，不自动确认Case。

### 演示

播放Normal到Fixture Offset的场景切换，WebUI自动出现一个Case，随后指标恢复但Case仍等待调查。

---

## Task 04：可靠Case事件投递

### 用户故事

作为平台工程师，我希望Case创建后即使Publisher或Consumer崩溃，Agent触发事件也不会静默丢失或造成重复业务结果。

### 垂直路径

```text
Outbox Row
→ Outbox Publisher
→ quality:case-events
→ Test Consumer
→ processed_events
→ XACK
```

### 实现内容

- Outbox Publisher；
- `quality.case.opened.v1`和`quality.episode.recovered.v1`；
- `processed_events`幂等表；
- Consumer Group封装；
- XREADGROUP、XACK、XPENDING和XAUTOCLAIM；
- 最大重试和DLQ；
- Outbox发布次数、错误和发布时间；
- CLI查看Pending和重放DLQ；
- 集成测试注入Publisher/Consumer崩溃。

### 验收标准

- Case和Snapshot存在时，Outbox事件必然可重新发布；
- 重复事件不会产生重复业务记录；
- Consumer在处理完成前崩溃，消息可被另一个Consumer接管；
- 超过三次失败进入DLQ；
- 所有日志携带Case Correlation ID。

### 演示

在Consumer领取消息后终止进程，等待超时后启动Recovery Consumer，展示消息接管和一次性有效结果。

---

## Task 05：企业文档入库与检索

### 用户故事

作为知识管理员，我可以上传一份技术手册，填写最少的版本和适用信息，并验证系统只检索当前Case适用的内容。

### 垂直路径

```text
上传PDF/Markdown
→ 文本解析和Chunk
→ Embedding
→ pgvector
→ Search API
→ WebUI显示版本、章节和页码
```

### 实现内容

- 文档上传API和页面；
- 文档类型、版本、生效日期和适用范围；
- 文件Hash和重复上传检测；
- Markdown/PDF最小解析；
- Chunk和页码/章节Metadata；
- Embedding Adapter和本地测试替身；
- pgvector Repository；
- Metadata过滤后向量检索；
- ACTIVE/SUPERSEDED状态；
- 检索结果引用展示；
- 合成夹具、光照手册种子数据。

### 验收标准

- 缺少强制Metadata时拒绝入库；
- 相同Hash不会重复索引；
- 过期或不适用文档不会进入默认结果；
- 结果包含`document_id/version/section/page`；
- 旧版本可审计但默认不可用于新Case；
- Embedding Provider可以通过Adapter替换。

### 演示

上传两版夹具手册，将旧版标记为SUPERSEDED；用当前产品检索时只返回适用的新版本引用。

---

## Task 06：Case调查Agent

### 用户故事

作为质量工程师，我希望Case创建后自动得到一份包含候选原因、支持证据、反证、缺失证据和排查步骤的初步分析。

### 垂直路径

```text
quality.case.opened.v1
→ Investigation Worker
→ Bounded ReAct
→ Snapshot/Metric/Sample/RAG Tools
→ InvestigationAnalysis
→ Trace
→ Case详情页
```

### 实现内容

- `InvestigationAgent`稳定接口；
- Provider-neutral `LLMClient`；
- 有界ReAct循环；
- `get_case_snapshot`；
- `compare_quality_metrics`；
- `get_representative_samples`；
- `search_knowledge_base`；
- A/B/C Evidence；
- Hypothesis、限制和终止原因；
- Analysis Run与结构化Trace；
- `quality.analysis.started/completed/failed.v1`；
- 同一Snapshot人工重新分析；
- WebUI Agent时间线和证据详情。

### 验收标准

- Agent由Case事件自动触发；
- 不允许调用任意SQL/Python或QMS写操作；
- 达到预算时能够终止；
- 每个假设包含支持证据、反证和缺失证据字段；
- 历史相似度不直接作为根因置信度；
- Trace不保存模型完整思维链；
- 同一自动触发事件不会创建重复Analysis Run；
- 重新分析创建新Run但仍引用原Snapshot。

### 演示

Fixture Offset Case自动进入ANALYZING，页面实时展示工具调用，最终生成夹具定位和光照两个候选假设及引用。

---

## Task 07：Proposal与人工审批

### 用户故事

作为质量工程师，我可以审阅Agent建议，批准、修改后批准、驳回或要求重新分析，而Agent不能绕过我执行外部动作。

### 垂直路径

```text
InvestigationAnalysis
→ InvestigationTaskProposal
→ Review UI
→ Human Decision
→ Approved/Rejected Event
```

### 实现内容

- Proposal结构和持久化；
- `quality.investigation.proposed.v1`；
- 待审批列表；
- Evidence到Proposal步骤的引用；
- APPROVE、APPROVE_WITH_CHANGES、REJECT、REQUEST_REANALYSIS；
- 审批人、时间、意见和前后版本审计；
- 幂等`decision_id`；
- `approved/rejected.v1`事件；
- Case状态流转；
- 基础用户身份模拟。

### 验收标准

- Agent没有QMS写工具；
- 未经审批不能创建外部任务；
- 修改后批准保留原Proposal和批准版本；
- 驳回必须填写理由；
- 重复提交相同Decision不会重复发事件；
- REQUEST_REANALYSIS创建新的Analysis Run。

### 演示

人工调整Agent建议的检查顺序后批准，页面同时保留原始Proposal和人工修改记录。

---

## Task 08：Mock QMS业务接入

### 用户故事

作为质量工程师，我批准Proposal后，系统可以通过与Agent解耦的业务Adapter在QMS中创建调查任务。

### 垂直路径

```text
quality.investigation.approved.v1
→ QMS Integration Worker
→ QMS Port
→ MockQMSAdapter
→ Mock QMS REST API
→ qms.task.created.v1
→ Case详情页
```

### 实现内容

- QMS Port接口；
- Mock QMS独立API和任务页面；
- QMS Integration Consumer Group；
- `proposal_id`幂等创建；
- 超时、重试和错误映射；
- `qms.task.created.v1`；
- Case与外部任务关联；
- WebUI外部任务状态和链接。

### 验收标准

- 只有Approved事件可以创建任务；
- 重复Approved事件只产生一个QMS任务；
- Mock QMS不可用时消息保留Pending或进入DLQ；
- QMS响应不直接泄漏到领域层；
- 替换Adapter不需要修改Investigation Agent。

### 演示

批准Proposal后自动在Mock QMS出现任务；重复投递批准事件，任务数量保持不变。

---

## Task 09：人工结论与知识闭环

### 用户故事

作为现场工程师，我可以在QMS提交实际根因、措施和验证数据，系统随后完成Case确认、JSON归档和可信知识索引。

### 垂直路径

```text
Mock QMS填写结果
→ Signed Webhook
→ qms.task.result-submitted.v1
→ Case Confirmation
→ quality.case.confirmed.v1
→ Archive Worker
→ MinIO JSON + pgvector
→ quality.case.archived.v1
```

### 实现内容

- Mock QMS结果提交表单；
- Webhook签名、时间窗和重放保护；
- 实际原因、措施和验证Schema；
- Case Confirmation事务；
- 知识晋升条件；
- 完整Case JSON组装、日期目录和Hash；
- MinIO归档；
- 带日期前缀的受控摘要；
- 已验证案例pgvector记录；
- 归档和索引幂等；
- `confirmed.v1`与`archived.v1`。

### 验收标准

- 未验证结果可以留档，但不能进入可信索引；
- `VERIFIED_EFFECTIVE`且根因、措施完整时才能索引；
- JSON包含Snapshot、Analysis、Trace摘要、审批、QMS和人工结论；
- 日期同时存在于文本前缀和Metadata；
- 重复Webhook不会生成重复归档或索引；
- 原始归档不可覆盖，修订创建Revision。

### 演示

在Mock QMS填写“定位销松动”和验证数据，Case变为CONFIRMED/ARCHIVED；MinIO出现JSON，Case Library出现可检索记录。

---

## Task 10：历史经验复用

### 用户故事

作为质量工程师，当相似异常再次发生时，我希望Agent能够检索已验证案例，但不会把相似性当作本次根因证明。

### 垂直路径

```text
第二个Fixture Offset Case
→ Agent搜索VERIFIED_CASE
→ 命中上一次归档摘要
→ C级Evidence
→ 新Analysis和Proposal
```

### 实现内容

- `VERIFIED_CASE`检索类型；
- 产品、工位、异常家族和日期Metadata过滤；
- 技术文档与历史案例统一工具、分级响应；
- C级Evidence显示；
- Case回查完整JSON接口；
- Agent提示和输出约束；
- 历史案例引用准确性测试。

### 验收标准

- 只返回`CONFIRMED + VERIFIED_EFFECTIVE`案例；
- Analysis明确标注历史案例不能证明本次根因；
- 引用可从摘要跳转到完整归档；
- 非适用产品案例不会因向量相似而越权进入结果；
- 无已验证案例时Agent仍能基于A/B证据工作。

### 演示

再次注入Fixture Offset场景，展示Agent检索到此前人工确认的案例，并将其作为C级经验而非确定结论。

---

## Task 11：光照漂移与证据不足

### 用户故事

作为面试评审者，我可以看到系统不仅能完成成功案例，也能区分另一类问题并在证据不足时安全停止。

### 垂直路径A

```text
Illumination Drift
→ Score/Distribution变化
→ Quality Case
→ 检索光照手册
→ 光照检查Proposal
```

### 垂直路径B

```text
Insufficient Evidence Snapshot
→ Agent检查Data Quality
→ 不继续强行RCA
→ INSUFFICIENT_EVIDENCE
→ 请求补充信息
```

### 实现内容

- 可复现光照变换；
- Score Shift规则；
- 合成光照维护手册；
- 样本不足、数据缺失和混合模型版本场景；
- `DATA_QUALITY_BLOCKED`终止；
- WebUI证据不足状态和所需信息；
- 对错误确定性结论的Eval断言。

### 验收标准

- 光照场景不会总是复制Fixture Proposal；
- 数据质量失败时不创建误导性行动Proposal；
- 输出列出具体缺失信息；
- 三个场景固定Seed可重复；
- 测试能够检测Agent无证据宣称根因的行为。

### 演示

依次运行光照漂移和证据不足场景，对比正常分析与安全停止的UI表现。

---

## Task 12：可观测性与故障控制台

### 用户故事

作为运维人员，我可以从一个Case追踪完整事件链，并处理失败消息而不直接操作Redis数据库。

### 垂直路径

```text
case_id / trace_id
→ Event Timeline
→ Worker Status
→ Pending/DLQ
→ Authorized Retry
→ 恢复后的Case状态
```

### 实现内容

- Case事件时间线Projection；
- Worker处理时延和错误计数；
- Pending与DLQ只读API；
- 受控重试操作；
- Analysis成本和工具调用指标；
- WebUI Operations页；
- 敏感错误脱敏；
- 结构化日志查询说明。

### 验收标准

- 从Case详情可看到事件因果链；
- UI不直接连接Redis；
- 重试保留原事件和审计记录；
- 不展示模型完整思维链；
- 故障消息包含消费者、次数、错误类型和时间；
- 能区分业务拒绝、证据不足和系统故障。

### 演示

人为让知识检索超时，展示重试、DLQ、人工恢复以及最终Analysis状态。

---

## Task 13：Agent Eval与ROI看板

### 用户故事

作为面试评审者，我可以看到该项目如何量化Agent质量、系统可靠性、成本和潜在业务价值。

### 垂直路径

```text
Scenario Dataset
→ Eval Runner
→ Schema/Evidence/Behavior Metrics
→ PostgreSQL Eval Runs
→ Evaluation + ROI Dashboard
```

### 实现内容

- 场景评估数据格式；
- Fixture Offset、Illumination Drift、Insufficient Evidence测试集；
- 输出Schema、引用、适用性、拒答和工具调用评价；
- 重复运行与模型配置对比；
- 单次Analysis Token、时延和成本；
- Time to First Analysis等业务指标；
- 参数化ROI Calculator；
- 明确区分Measured与Illustrative指标；
- Eval报告导出。

### 验收标准

- Eval固定输入可以重复运行；
- 结果保存模型配置、Prompt版本、工具版本和数据集版本；
- ROI金额必须显示“示例测算”；
- 不把场景隐藏真值提供给Agent；
- 至少比较两次Agent配置或Prompt版本；
- Dashboard能够定位失败Case而不只展示平均分。

### 演示

运行Eval，展示三个场景的证据引用率、安全停止率、平均时延和成本，再调整ROI参数查看潜在回收周期。

---

## Task 14：作品集交付

### 用户故事

作为招聘方，我可以在有限时间内理解项目价值、启动Demo、观察完整闭环并判断候选人的Agent工程能力。

### 垂直路径

```text
Clone
→ 配置环境变量
→ docker compose up
→ seed-demo
→ 一键运行主场景
→ 浏览器完成闭环
```

### 实现内容

- README答案优先重写；
- 一键初始化和Seed脚本；
- 架构图、时序图、状态机图；
- 3至5分钟主Demo视频；
- 60秒快速演示模式；
- 故障恢复演示脚本；
- 性能、Agent Eval和ROI结果；
- 已知限制与非目标；
- 数据真实性声明；
- 简历项目描述和面试讲解稿；
- 全量Clean Environment验证。

### 验收标准

- 新环境按README可以启动；
- 不要求真实企业数据；
- 不要求GPU也能使用Fast Replay完成主Demo；
- 模型API不可用时可以使用录制响应演示非Agent数据链路；
- README首先突出事件驱动和业务闭环，而不是EfficientAD；
- 演示能够在5分钟内完成Case创建到知识归档；
- 所有示例收益明确标注为假设或实测。

### 演示

完整执行主场景，并展示第二次相似事件成功复用第一次人工验证的经验。

---

## 9. 任务依赖图

```text
Task 00 工程与协议
├── Task 01 检测接入
│   └── Task 02 指标窗口
│       └── Task 03 Quality Case
│           └── Task 04 可靠事件
│               └── Task 06 调查Agent
│                   ├── Task 07 人工审批
│                   │   └── Task 08 Mock QMS
│                   │       └── Task 09 知识闭环
│                   │           └── Task 10 历史复用
│                   ├── Task 11 第二场景/安全停止
│                   └── Task 12 故障控制台
└── Task 05 文档入库 ────────────┘

Task 09～12
    └── Task 13 Eval与ROI
        └── Task 14 作品集交付
```

---

## 10. 里程碑

### Milestone A：Event Pipeline可见

包含Task 00～04。

交付结果：模拟数据能够经过Redis和PostgreSQL形成不可变Quality Case，且事件投递可以故障恢复。

### Milestone B：Agent调查可见

包含Task 05～06。

交付结果：Case自动触发单Agent，Agent能够调用数据与知识工具生成结构化分析。

### Milestone C：业务闭环可见

包含Task 07～10。

交付结果：人工审批、Mock QMS、结果回传、归档以及已验证历史经验复用全部连通。

### Milestone D：质量与作品集可见

包含Task 11～14。

交付结果：安全停止、故障恢复、Agent Eval、ROI和一键Demo达到可投递状态。

---

## 11. 每个任务的提交策略

建议一个Task对应一个短生命周期Feature Branch或一组连续提交。提交顺序保持：

```text
contract/test
→ domain/application
→ adapter/infrastructure
→ API/worker
→ WebUI
→ docs/demo
```

每个Task结束时创建一个可运行Tag：

```text
milestone/event-pipeline
milestone/agent-investigation
milestone/business-loop
milestone/portfolio-ready
```

不要在一个Task中顺手实现下一个Task的业务功能；可以提前建立接口和测试替身，但真实实现应留在对应垂直切片中。

---

## 12. 风险与控制

| 风险 | 控制方式 |
|---|---|
| 基础设施过多导致无法完成 | PostgreSQL + Redis + MinIO封顶，其他能力通过Adapter |
| 项目再次变成RAG Demo | RAG只在Task 06中作为一个工具出现 |
| Agent输出看起来像固定Prompt | 展示多轮工具选择、Trace、预算和不同场景行为 |
| 事件驱动只停留在架构图 | Task 04必须演示Consumer崩溃恢复 |
| Agent幻觉根因 | Evidence分级、缺失证据、人工确认和安全停止 |
| 历史知识被错误分析污染 | 只有`VERIFIED_EFFECTIVE`Case进入索引 |
| 前后端类型漂移 | OpenAPI生成TypeScript类型 |
| Demo依赖GPU或在线服务 | Fast Replay、固定Seed、测试LLM/Embedding Adapter |
| Mock QMS显得像假功能 | 使用真实Webhook、签名、幂等和Adapter边界 |
| ROI被质疑 | 严格区分实测系统指标和假设业务金额 |

---

## 13. 最终交付清单

- [ ] 冻结后的架构决策记录；
- [ ] 版本化消息Schema和Golden Examples；
- [ ] Docker Compose一键运行环境；
- [ ] 三个可复现场景；
- [ ] 从检测数据到Quality Case的事件管道；
- [ ] Outbox、Consumer Group、幂等、恢复和DLQ；
- [ ] 单Investigation Agent及受控工具；
- [ ] 文档上传和Agentic RAG工具；
- [ ] Case WebUI和结构化Trace；
- [ ] Proposal审批与Mock QMS；
- [ ] 人工结论Webhook、JSON归档和可信知识索引；
- [ ] Agent Eval和ROI Calculator；
- [ ] 自动化测试、CI和性能结果；
- [ ] README、架构图、Demo视频和面试讲解稿。

当上述内容全部完成时，项目能够清晰证明：开发者不仅会调用LLM和向量数据库，还能够把Agent放进一个可靠、可审计、有人类授权边界的事件驱动业务系统中。
