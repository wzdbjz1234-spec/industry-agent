# Package boundaries

本项目以最新开发计划中的 `backend/src/quality_case_agent` 模块化单体为结构基线。

```text
contracts ───────────────► 不依赖业务实现
domain ──────────────────► 只依赖标准库和必要值对象
application ─────────────► domain + contracts + ports
adapters ────────────────► application ports + 外部 SDK
entrypoints ─────────────► application + adapters + contracts
```

约束：

- `domain` 不得导入 FastAPI、SQLAlchemy、Redis 或 LLM SDK；
- API Route 不直接写 SQL；
- Worker 只消费经过 Schema 校验的消息；
- Agent Tool 通过 application port 访问外部能力，不持有全局数据库 Session；
- WebUI 的 API 类型从 OpenAPI 生成，`web/src/generated/` 禁止手工维护；
- 模拟器只依赖公开契约和适配器接口，不导入业务 Repository 实现；
- `efficientad-package/` 是现有检测器包，暂不与新后端包建立反向依赖。

协议模型的唯一来源是 `backend/src/quality_case_agent/contracts/`；生成的 JSON Schema、
AsyncAPI 目录和示例分别落在根目录 `contracts/` 的对应子目录。
