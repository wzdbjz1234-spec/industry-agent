# 全项目开发与验收报告

日期：2026-08-23  
范围：`quality_case_agent_development_plan.md` Task 00–14、阶段 9 交接文档要求的阶段 10 接续能力，以及阶段 15 连续视觉入口。

## 1. 验收结论

离线可复现主链路已完成并通过本地验收：检测结果进入 Case，冻结 Snapshot，单 Agent 生成带证据引用的 Analysis/Proposal，人工授权后才投递 Mock QMS，结果回传后归档并进入可信案例索引，后续 Case 可复用历史经验但只能作为 C 级上下文。阶段 11 的数据质量安全停止、阶段 12 的运维/DLQ 控制台、阶段 13 的固定种子 Eval/ROI、阶段 14 的作品集交付和阶段 15 的 EfficientAD 连续视觉入口也已落地。

当前验收采用确定性离线适配器。真实 PostgreSQL/Redis/MinIO/QMS 连接仍由 Port/Compose 边界保留，未把本地内存实现误报为生产基础设施。

## 2. 阶段与日志矩阵

| Task | 交付与验证入口 | 阶段日志 |
| --- | --- | --- |
| 00 | Python 包骨架、协议基线、Schema/Golden 生成 | [Phase 0](../development-log/2026-08-23-phase-0-engineering-baseline.md) |
| 01 | 正常检测数据接入与幂等 | [Phase 1](../development-log/2026-08-23-phase-1-inspection-ingestion.md) |
| 02 | 指标窗口与异常聚合 | [Phase 2](../development-log/2026-08-23-phase-2-reproducible-data-flow.md) |
| 03 | Fixture Offset Quality Case | [Phase 3](../development-log/2026-08-23-phase-3-agent-investigation.md) |
| 04 | 可靠事件、Consumer、Case 调查触发 | [Phase 4](../development-log/2026-08-23-phase-4-human-loop.md) |
| 05 | 文档入库、哈希幂等、混合检索 | [Phase 5](../development-log/2026-08-23-phase-5-case-knowledge.md) |
| 06 | 单 Agent 调查、Trace、证据与 Proposal | [Phase 6](../development-log/2026-08-23-phase-6-agent-investigation.md) |
| 07 | 人工审批、版本审计、QMS 写边界 | [Phase 7](../development-log/2026-08-23-phase-7-human-approval.md) |
| 08 | Mock QMS、幂等投递和结果回传 | [Phase 8](../development-log/2026-08-23-phase-8-mock-qms.md) |
| 09 | 人工结论、归档、可信案例索引 | [Phase 9](../development-log/2026-08-23-phase-9-knowledge-closure.md) |
| 10 | 历史经验复用，C 级上下文隔离 | [Phase 10](../development-log/2026-08-23-phase-10-historical-reuse.md) |
| 11 | 光照漂移、证据不足、安全停止 | [Phase 11](../development-log/2026-08-23-phase-11-safety-branches.md) |
| 12 | 时间线、Worker/Delivery 指标、DLQ 受控重试 | [Phase 12](../development-log/2026-08-23-phase-12-operations.md) |
| 13 | 固定数据集 Eval、双配置对比、ROI | [Phase 13](../development-log/2026-08-23-phase-13-evaluation-roi.md) |
| 14 | README、架构图、Demo Runbook、面试材料 | [Phase 14](../development-log/2026-08-23-phase-14-portfolio-delivery.md) |
| 15 | EfficientAD 连续图像队列、NG/波动事件、anomlib 输入保留接口 | [Phase 15](../development-log/2026-08-23-phase-15-continuous-vision.md) |

原 Phase 5–7 合并记录仍保留在 [vertical slice log](../development-log/2026-08-23-phase-5-7-vertical.md)，独立日志用于逐阶段追踪。

## 3. 自动化验证结果

以下命令在验收环境执行成功：

```powershell
uv run pytest                         # 51 passed
uv run ruff check backend scripts     # All checks passed
uv run mypy backend/src               # Success: no issues in 102 source files
uv run python scripts/generate_schemas.py
cd web
npm run build                         # Vite production build passed
npm run test:e2e                      # 1 passed
```

协议生成结果为 29 个 JSON Schema 和 18 个 Golden example。Playwright 关键流覆盖：打开 WebUI、运行光照漂移 Demo、确认 `COMPLETED`、切换运维页和评估/ROI 页。视觉专项测试覆盖真实 EfficientAD 目录处理、异步 Job 完成态、NG 故障、NG 率波动、处理失败脱敏和 anomlib 归一化输入。

阶段演示脚本全部返回退出码 0：

```powershell
uv run python scripts/run_phase2_demo.py
uv run python scripts/run_phase3_demo.py
uv run python scripts/run_phase4_demo.py
uv run python scripts/run_phase5_7_demo.py
uv run python scripts/run_phase8_demo.py
uv run python scripts/run_phase9_demo.py
uv run python scripts/run_phase10_demo.py
uv run python scripts/run_phase11_demo.py
uv run python scripts/run_phase12_demo.py
uv run python scripts/run_phase13_eval.py
uv run python scripts/run_fast_demo.py
```

## 4. 运行态验收

最终验收使用 Docker Compose 启动：

- API 容器：`intelligent-agent-api-1`，健康状态 `healthy`
- Web 容器：`intelligent-agent-web-1`，地址 `http://127.0.0.1:5173/`

实测结果：

- `GET /health` 返回 `status=ok`；
- `GET /api/v1/evaluation/dataset` 返回 3 个场景，返回内容不含 `hidden_truth`；
- `POST /api/v1/evaluation/matrix` 返回 2 份报告，baseline 与 safe-v2 均为 3/3、`pass_rate=1.0`；
- `POST /api/v1/roi/calculate` 返回 `classification=ILLUSTRATIVE` 和免责声明；
- `GET /api/v1/vision/schemes` 返回视觉方案注册状态；Docker 默认不加载大型 EfficientAD 运行时，但 `POST /api/v1/vision/anomlib/detections` 成功接收并归一化 NG 结果，同时记录视觉故障事件；
- WebUI 光照漂移 Demo 产生 `COMPLETED` Analysis Run 和待审批 Proposal；
- WebUI 评估页成功运行两组配置并展示结果；ROI 页成功计算并展示“示例测算”边界；
- Phase 12 演示验证 DLQ `attempts=2` 后由带 `operator_id` 的受控重试恢复为 `PROCESSED`。
- 容器入口 `scripts/seed_demo.py` 成功返回健康信息和 Fixture Case；容器化 Playwright 关键流 `1 passed`。

评测报告产物：[phase13-report.json](../../artifacts/evaluation/phase13-report.json)。演示分镜和录屏步骤见 [demo-video-storyboard.md](../portfolio/demo-video-storyboard.md)。

## 5. Compose 与基础设施边界

`docker compose config`、`docker compose build` 和 `docker compose up -d` 均已通过。API 与 Web 镜像构建成功，API 健康检查为 `healthy`，Web 端口 5173 可访问。期间发现并修复了 API wheel 安装布局下 Phase 13 数据集路径问题，重建 API 后评测矩阵恢复正常。

本次容器验收命令：

```powershell
docker compose build
docker compose up -d
```

## 6. 已知边界

- 当前默认使用内存存储和确定性模型/Embedding/QMS 适配器，生产部署需接入计划中的 PostgreSQL/pgvector、Redis Streams、MinIO、真实 QMS 和模型服务；
- 连续视觉 Worker、视觉事件 Store 和视觉 Inspection 接入当前为内存实现；EfficientAD 依赖与模型文件作为可选视觉运行时提供，真实启用时需使用 `efficientad-package` 环境并配置模型目录；
- Eval latency/cost 是离线估算指标，适用于回归比较，不代表线上 SLA 或真实模型费用；
- ROI 看板只提供参数化 Illustrative 测算，不代表客户收益；
- 仓库交付可复现 Demo Runbook 和视频分镜，不包含预录制 MP4；
- 真实企业数据、客户收益和生产容量指标未纳入本次验收。

## 7. 交付入口

- 一键启动：[start.cmd](../../start.cmd)，PowerShell 入口：[start.ps1](../../start.ps1)
- 启动与快速验收：[README.md](../README.md)
- 架构总览：[system-overview.md](../architecture/system-overview.md)
- 事件时序：[event-sequence.md](../architecture/event-sequence.md)
- Case 状态机：[case-state-machine.md](../architecture/case-state-machine.md)
- Demo Runbook：[demo-runbook.md](../portfolio/demo-runbook.md)
- 面试讲解：[interview-script.md](../portfolio/interview-script.md)
- 数据与限制：[data-and-limitations.md](../portfolio/data-and-limitations.md)
