# Quality Case Investigation Agent

分阶段生产化与试点修改建议见 [Quality Case Investigation Agent 分阶段优化路线](quality_case_agent_optimization_roadmap.md)。文档从现有 Phase 00–15 继续规划 Phase 16–22，覆盖真实持久化、可靠事件流、可观测性、模型监控、通用调查、真实 QMS 影子接入和量化发布门禁。

Phase 16–18 的实际开发日志：

- [Phase 16 持久化](development-log/2026-08-25-phase-16-persistence.md)
- [Phase 17 事件流](development-log/2026-08-25-phase-17-eventing.md)
- [Phase 18 可观测性](development-log/2026-08-25-phase-18-observability.md)
- [Phase 19 模型与数据健康监控](development-log/2026-08-25-phase-19-monitoring.md)
- [Phase 20 通用证据驱动调查](development-log/2026-08-25-phase-20-investigation.md)

这是一个可审计、有人类授权边界的事件驱动工业质量调查 Agent。核心答案是：检测系统持续产生事实，普通程序聚合成 Quality Case，受控单 Agent 围绕冻结 Snapshot 调用只读工具形成 Evidence/Proposal，人工批准后才触发 QMS，验证结果再沉淀为可信组织知识。

## 先启动、再验收

Windows 双击仓库根目录的 `start.cmd` 即可一键启动 Docker Compose、等待服务健康并打开 WebUI。命令行等价用法：

```powershell
.\start.ps1
```

调试时可跳过重新构建或不自动打开浏览器：

```powershell
.\start.ps1 -NoBuild -NoBrowser
```

最快路径不需要 GPU、真实企业数据或在线模型：

```powershell
uv sync --dev
docker compose up --build
uv run python scripts/seed_demo.py
```

浏览器打开 `http://localhost:5173`。后端健康检查为 `http://localhost:8000/health`；完整主链路和第二次历史复用可运行：

```powershell
uv run python scripts/run_phase10_demo.py
uv run python scripts/run_phase12_demo.py
uv run python scripts/run_phase13_eval.py
```

阶段 13 的 Dashboard 将 Measured Eval 指标与 Illustrative ROI 金额分开显示。开发阶段和最终运行态验收均见 [最终验收报告](acceptance/2026-08-23-full-project-acceptance.md)。

## DeepSeek V4 Flash 真实 LLM

默认运行离线确定性 Agent。要启用真实 LLM，在仓库根目录复制 `.env.example` 为 `.env`，并仅在该本地文件或部署平台的 Secret 中填入密钥：

```dotenv
QUALITY_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-secret-key
QUALITY_LLM_BASE_URL=https://api.deepseek.com
QUALITY_LLM_MODEL=deepseek-v4-flash
QUALITY_LLM_TIMEOUT_S=30
```

随后重新构建服务：

```powershell
docker compose up --build
```

DeepSeek Adapter 使用 OpenAI 兼容的 `/chat/completions` JSON 输出模式，且显式关闭 reasoning 内容；模型只返回受限的 `TOOL_CALL`、`FINAL` 或 `STOP` 决策。应用侧仍会校验工具白名单、参数类型、循环预算和人工审批边界，模型不会获得 QMS 写权限。没有配置 `QUALITY_LLM_PROVIDER=deepseek` 时，系统保持离线确定性模式。

## 设计与边界

仓库保留模块化单体边界，并提供阶段 00–14 的离线可验证主链路：

- Python 后端采用 `backend/src/quality_case_agent` 模块化单体；
- `contracts`、`domain`、`application`、`adapters`、`entrypoints` 是稳定边界；
- 现有 `efficientad-package/` 保持为独立的视觉检测器包；
- Web、模拟器、知识库、协议产物、文档和脚本目录已按计划组织。

当前已完成阶段 00–14 的离线垂直切片：知识文档入库/检索、Case 调查 Agent、Analysis Run、Proposal
人工审批、QMS Worker/Mock QMS 任务闭环、人工结论归档/可信案例索引及 FastAPI 本地入口。真实 PostgreSQL/Redis/MinIO 仍通过 Port
保留替换边界。Phase 16–18 已补充 SQLAlchemy/psycopg、Redis Streams、MinIO、OpenTelemetry 和 Prometheus 适配器；本地可用 SQLite + InMemory，生产通过 `QUALITY_RUNTIME_MODE=production` 和显式资源 URL 装配，API 的 `/metrics` 可直接被 Prometheus 抓取。

## 阶段 5–7 演示

```powershell
uv sync --dev
uv run pytest
uv run python scripts/run_phase5_7_demo.py
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload
```

文档种子位于 `knowledge_base/`。API 提供文档入库/上传、知识检索、Analysis Run、Case 和待审批
 Proposal 查询；批准后由 QMS Worker 创建幂等 Mock QMS 任务，Case 和 WebUI 可查看外部任务状态；Agent
只拥有 Snapshot、指标、代表性样本和知识检索只读工具。

## 阶段 8 演示

```powershell
uv run python scripts/run_phase8_demo.py
uv run uvicorn quality_case_agent.entrypoints.mock_qms.app:app --port 8001
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
cd web
npm run dev
```

独立 Mock QMS 页面位于 `http://localhost:8001/`；主 API 提供 `/api/v1/qms/tasks` 和
`/api/v1/qms/delivery` 运维查询。

## 阶段 9 演示

```powershell
uv run python scripts/run_phase9_demo.py
```

阶段 9 交接文档见：`docs/handoff/2026-08-23-phase-9-handoff.md`。它记录了结果回传、签名、归档、
可信案例索引、API 顺序、验证结果和后续阶段 10 的接入边界。

## 阶段 10 演示

```powershell
uv run python scripts/run_phase10_demo.py
```

阶段 10 将已验证案例摘要回流到统一知识检索工具。第二个 Fixture Offset Case 会命中第一个归档案例，
但输出只把它作为 C 级经验，不能替代当前 Case 的 A/B 证据。阶段记录见：
`docs/development-log/2026-08-23-phase-10-historical-reuse.md`。

## 阶段 11–12 演示

```powershell
uv run python scripts/run_phase11_demo.py
uv run python scripts/run_phase12_demo.py
```

阶段 11 提供光照漂移与证据不足安全停止场景；阶段 12 提供 Case 事件时间线、Worker/Delivery 运维查询和带操作者审计的 DLQ 受控重试。详细记录见：
`docs/development-log/2026-08-23-phase-11-safety-branches.md`、
`docs/development-log/2026-08-23-phase-12-operations.md`。

## 阶段 13–14 演示与作品集材料

```powershell
uv run python scripts/run_phase13_eval.py
uv run python scripts/run_fast_demo.py
```

阶段 13 的 Eval 数据集、报告和 ROI 计算器见 `evaluation/`、`artifacts/evaluation/` 和 WebUI“评估与 ROI”页；阶段 14 的启动手册、架构图、状态机、面试稿和数据真实性声明见 `docs/portfolio/` 与 `docs/architecture/`。

## 阶段 15：连续视觉入口

连续视觉入口说明见 [`docs/portfolio/vision-entrypoint.md`](portfolio/vision-entrypoint.md)。API 提供 EfficientAD 图像队列、任务状态、故障/NG 波动事件查询，以及 anomlib 结果归一化入口：

```powershell
GET  http://localhost:8000/api/v1/vision/schemes
GET  http://localhost:8000/api/v1/vision/status
POST http://localhost:8000/api/v1/vision/frames
POST http://localhost:8000/api/v1/vision/anomlib/detections
```

使用仓库提供的 EfficientAD 包连续处理目录图片：

```powershell
$env:PYTHONPATH = "C:\projects\intelligent-agent\backend\src;C:\projects\intelligent-agent;C:\projects\intelligent-agent\efficientad-package\src;C:\projects\intelligent-agent\.venv\Lib\site-packages"
& C:\projects\intelligent-agent\efficientad-package\.venv\Scripts\python.exe scripts/run_vision_stream.py --max-images 5
```

Worker 会持续消费有界队列，将检测结果接入既有 Inspection/Metric/Case 链路，并记录 `quality.vision.fault.v1` 与 `quality.vision.ng-rate-fluctuation.v1`。EfficientAD 依赖按可选运行时加载；没有配置模型目录时，anomlib 归一化入口仍可用。

## 结构验证

在仓库根目录运行：

```powershell
python scripts/verify_package_structure.py
```

Python 后端源码目录：`backend/src/quality_case_agent/`。
