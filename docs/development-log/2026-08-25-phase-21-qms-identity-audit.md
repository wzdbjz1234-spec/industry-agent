# Phase 21 开发日志：QMS 影子接入、身份与审计

日期：2026-08-25

## 目标

建立真实 QMS 接入前的安全控制层：身份、角色授权、幂等投递、影子模式、Webhook 防伪与重放、Append-only 审计和生产持久化 seam。Agent 仍不能直接拥有 QMS 写权限。

## 已实现

### 身份与授权

- 新增 `IdentityContract`、角色集合 `VIEWER/QUALITY_ENGINEER/APPROVER/OPERATOR/ADMIN` 和声明摘要哈希。
- 新增 Header Demo/Test Adapter；生产可通过 `QUALITY_OIDC_USERINFO_URL` 使用 OIDC UserInfo Adapter。
- `IdentityPolicy` 在 API 入口检查角色，不依赖前端按钮隐藏。
- Proposal 审批要求 `APPROVER/ADMIN`，QMS 重试要求 `OPERATOR/ADMIN`，审计读取和导出分级授权。
- 生产模式没有 OIDC 配置时默认拒绝无身份请求；Demo/Test 保留兼容的显式演示身份。

### QMS 模式与可靠性

- 新增 `SHADOW/SANDBOX/PRODUCTION` 模式策略。
- `ShadowQmsAdapter` 只生成确定性的 `shadow://` 计划任务，不调用任何外部写端点，也不改变 Case 的真实 QMS 状态。
- HTTP QMS Adapter 增加 `Idempotency-Key`、超时和 HTTP 错误分类。
- 增加 Token Bucket 限流和 Circuit Breaker；既有 Worker 的重试/DLQ 继续负责补偿。
- `QUALITY_QMS_MODE=SHADOW` 已加入 Docker/环境样例，生产切换需显式配置。

### Webhook 安全

- 保留旧 HMAC 兼容协议，同时支持 `X-QMS-Timestamp` + `X-QMS-Nonce` 签名。
- 时间窗口、未来偏差、签名校验和 nonce 重放保护在应用服务侧执行；非法请求不会进入 Case 查询。
- Webhook 结果仍按 `event_id` 幂等处理。

### Append-only 审计

- 新增 `AuditEventContract`，记录 actor、角色、组织、策略版本、声明摘要、关联 ID 和资源版本。
- InMemory 与 SQLAlchemy 两个 Adapter 使用 hash chain；敏感字段（token、secret、password、signature、api key）统一脱敏。
- Proposal 创建、审批决策、QMS 重试和 Webhook 接收写入审计事件。
- 新增 `/api/v1/identity/me`、`/api/v1/qms/status`、`/api/v1/audit/events` 和管理员导出 `/api/v1/audit/export`。

## 文件结构

```text
backend/src/quality_case_agent/contracts/identity.py
backend/src/quality_case_agent/application/ports/identity.py
backend/src/quality_case_agent/application/ports/audit.py
backend/src/quality_case_agent/application/identity/policy.py
backend/src/quality_case_agent/application/audit/service.py
backend/src/quality_case_agent/adapters/identity/oidc.py
backend/src/quality_case_agent/adapters/qms/modes.py
backend/src/quality_case_agent/application/qms/resilience.py
backend/src/quality_case_agent/adapters/postgres/audit.py
backend/migrations/0006_phase21_identity_audit.sql
web/src/features/identity/IdentityBadge.tsx
web/src/features/audit/AuditPanel.tsx
```

## 量化验证

| 检查 | 结果 |
| --- | --- |
| 后端测试 | 86 passed |
| 未授权审批 | Viewer 返回 403，Approver 可继续流程 |
| 影子 QMS 幂等 | 同一 Proposal 只生成一个 shadow task |
| Webhook 过期阻断 | 过期时间戳在 Case 查询前拒绝 |
| 审计脱敏与链完整性 | secret 不落盘，hash chain 校验通过 |
| Ruff | passed |
| Mypy | 163 个源码文件无错误 |
| Web build | TypeScript/Vite 构建通过 |

## 边界与下一步

- OIDC 当前使用标准 UserInfo Adapter，生产仍需接入组织的 issuer、JWKS/网关和密钥轮换策略。
- SQL 审计 Adapter 已建立并由生产组合根装配，数据库迁移执行仍由部署流水线负责。
- Shadow 模式只验证本地预期任务与字段映射；下一阶段需用真实 QMS 沙箱回放，统计差异率和最终成功率，再开放低风险 Sandbox 写入。
