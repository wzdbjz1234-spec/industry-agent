# 阶段 0：工程骨架与协议基线

## 完成内容

- 冻结 `contracts`、`domain`、`application`、`adapters`、`entrypoints` 模块边界和独立 `efficientad-package` 边界。
- 建立 Python 3.12 + uv 工程、Ruff、mypy、pytest 和生成式 JSON Schema 工作流。
- 为检测批次、Case 事件、Analysis、Proposal、QMS、归档、Eval 和 ROI 建立 Pydantic 契约；生成 JSON Schema 与 Golden Examples。
- 增加 `/health` 健康检查、Docker Compose API/Web 启动环境和 CI 配置。
- 明确离线确定性 Adapter 是验收路径，PostgreSQL、Redis、MinIO 和真实模型通过 Port 保留替换位置。

## 验收命令

```powershell
uv sync --dev
uv run python scripts/generate_schemas.py
uv run python scripts/verify_package_structure.py
docker compose config
```

## 边界

Compose 默认不伪装成生产基础设施；它启动可演示的 API/Web 作品集环境，数据在内存中运行，生产持久化 Adapter 仍需按部署环境接入。
