# 阶段 9 开发交接文档

## 1. 交接结论

阶段 9“人工结论与知识闭环”已完成离线垂直切片：

```text
Mock QMS 结果
→ qms.task.result-submitted.v1
→ HMAC + 时间窗 + 重放保护
→ Case Confirmation
→ quality.case.confirmed.v1
→ CaseClosureService
→ 日期分区 JSON Archive
→ quality.case.archived.v1
→ VERIFIED_EFFECTIVE 可信案例索引
```

当前实现可在本地完成批准 Proposal、创建 QMS 任务、提交人工根因和验证结果、归档 Case，并在案例库中看到可信案例。

## 2. 关键代码入口

| 能力 | 入口 |
| --- | --- |
| QMS 结果契约和事件版本 | `backend/src/quality_case_agent/contracts/qms.py` |
| 签名、时间窗和重放保护 | `backend/src/quality_case_agent/application/qms/service.py` |
| Confirmation + Archive + Index 编排 | `backend/src/quality_case_agent/application/archival/service.py` |
| Mock QMS 结果表单/API | `backend/src/quality_case_agent/entrypoints/mock_qms/app.py` |
| 主 API Webhook/归档/案例库 | `backend/src/quality_case_agent/entrypoints/api/app.py` |
| 不可覆盖内存归档 | `backend/src/quality_case_agent/adapters/in_memory/archive.py` |
| 阶段 9 演示 | `scripts/run_phase9_demo.py` |
| 阶段 9 测试 | `backend/tests/integration/test_phase9_closure.py` |

## 3. 本地运行

在仓库根目录：

```powershell
uv sync --dev
uv run python scripts/run_phase9_demo.py
uv run uvicorn quality_case_agent.entrypoints.mock_qms.app:app --port 8001
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload --port 8000
```

另开终端启动前端：

```powershell
cd web
npm run dev
```

页面入口：

- 主工作台：`http://localhost:5173`
- Mock QMS：`http://localhost:8001/`
- 结果表单：Mock QMS 任务列表中的“填写结果”链接

## 4. API 交互顺序

1. `POST /api/v1/demo/fixture-offset`
2. `GET /api/v1/proposals/pending`
3. `POST /api/v1/proposals/{proposal_id}/decisions`
4. `GET /api/v1/qms/tasks`
5. 在 Mock QMS 中打开任务结果页，或直接调用：

   `POST /api/v1/tasks/{task_id}/result`

   该接口返回：

   - `result`
   - `signature`
   - `webhook_url`

6. 将 `result` 作为请求体、`signature` 作为 `X-QMS-Signature` 调用主 API：

   `POST /api/v1/integrations/qms/task-results`

7. 查询：

   - `GET /api/v1/cases/{case_id}`
   - `GET /api/v1/cases/{case_id}/archive`
   - `GET /api/v1/case-library`

## 5. 业务规则

- HMAC 签名使用规范化 JSON，演示密钥为 `phase9-demo-secret`，生产环境必须从 Secret 配置读取。
- 默认允许结果发生时间距当前最多 7 天，未来最多允许 5 分钟时钟偏差。
- 相同 `event_id` 的重复 Webhook 返回同一个 Confirmation/Archive 结果，不产生重复对象或索引记录。
- 同一个 Case 的新人工结论会生成新的 `r2`、`r3` 归档 URI，旧对象不会覆盖。
- 只有 `VERIFIED_EFFECTIVE`、非空根因描述、至少一项实际措施同时满足时，才进入可信案例索引。
- `NOT_VERIFIED` 和 `INCONCLUSIVE` 仍然归档，但 `knowledge_index_status=NOT_ELIGIBLE`。
- 归档 JSON 包含 Snapshot、调查输出和 Trace、审批事件、批准 Proposal、QMS 任务、人工确认及内容 Hash。

## 6. 验证结果

已执行：

```powershell
uv run pytest -q
uv run ruff check backend/src backend/tests simulator scripts
uv run mypy
npm run build                 # 在 web/ 下执行
uv run python scripts/generate_schemas.py
uv run python scripts/verify_package_structure.py
uv run python scripts/run_phase9_demo.py
```

当前结果：后端 `31 passed`，Ruff、mypy、前端构建、Schema 生成和包结构检查均通过。

## 7. 已知限制与下一步

- 所有存储仍为内存实现，进程重启后 Case、Archive、Index、Delivery 状态会丢失。
- Mock QMS 返回签名结果，但不会自动向主 API 发起网络回调；交互式表单和演示脚本负责串联这一步。
- 真实环境需要把 HMAC Secret、时间窗和回调地址改为环境配置，并加入身份认证、权限和审计主体。
- `CaseClosureService` 当前通过内存 Proposal/Analysis Run 查找完整调查上下文，生产环境应在同一事务或可靠读取模型中完成关联。
- 后续阶段 10 应在 `VERIFIED_CASE` 检索结果上增加历史经验复用，并明确标注“历史相似案例不能证明本次根因”。
