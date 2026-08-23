# 2026-08-23：Phase 2 可复现数据流

## 目标

依据最新设计文档的“Phase 2：可复现数据流”，建立一条不依赖外部服务即可运行的核心链路：

```text
固定 Seed 场景
→ inspection.result.batch.v1
→ Detector Replay Adapter
→ 幂等检测结果接入
→ 1 分钟/5 分钟指标窗口
→ Fixture Offset 连续异常检测
→ Quality Case + Immutable Snapshot + 生命周期事件
```

## 本次实现

- 在 `backend/src/quality_case_agent/contracts/inspection.py` 建立严格的
  `inspection.result.batch.v1` Pydantic 契约；
- 将外部契约映射为不依赖 Pydantic、数据库和网络 SDK 的领域模型；
- 实现 Normal、Fixture Offset、Illumination Drift、Insufficient Evidence 四个固定 Seed 场景；
- 实现可替换 `DetectorAdapter` 协议和 Replay Adapter；
- 实现内存检测结果、指标和 Quality Case 适配器，模拟数据库唯一约束、批次幂等和快照不可变；
- 实现 1 分钟和 5 分钟固定窗口，计算 `total_count`、`ng_count`、`ng_rate`、Score mean、P95、区域分布和混合模型警告；
- 实现 Fixture Offset 的连续越界、单 Case 合并、恢复窗口和 `episode_status` 恢复逻辑；
- 生成 JSON Schema 和 Golden Example；
- 增加离线 Demo 与契约、幂等、指标、Case 生命周期、场景可复现性测试。

## 关键决定

### 1. Phase 2 先使用内存适配器

上一阶段只完成了包结构，PostgreSQL、Redis、MinIO 和 FastAPI 尚未落地。因此本次把业务逻辑放在 application/domain 层，使用 `adapters/in_memory` 实现端到端离线演示。后续基础设施适配器只替换 Port，不改变契约和领域规则。

### 2. Case Detector 使用 1 分钟窗口

5 分钟窗口用于趋势展示和聚合校验；Fixture Offset 的连续越界与恢复规则使用 1 分钟窗口，避免把不同粒度的指标混在同一个状态机中。

### 3. 恢复不等于人工确认

指标连续恢复后只将 `episode_status` 更新为 `RECOVERED`，`case_status` 保持 `WAITING_INVESTIGATION`，与设计文档中的双状态机约束一致。

## 验证

```powershell
uv run pytest
uv run python scripts/generate_schemas.py
uv run python scripts/run_phase2_demo.py
```

测试覆盖：

- Golden Example 能通过契约校验；
- 批次内重复 `result_id` 和无时区时间会被拒绝；
- 重复提交同一个 `batch_message_id` 不增加检测记录；
- Fixture Offset 三个连续异常窗口只创建一个 Case；
- 恢复窗口只产生 `quality.episode.recovered.v1`，不关闭 Case；
- 固定 Seed 生成结果完全一致；
- 其他三类场景不会误触发 Fixture Offset Case。

## 当前限制

- 结果和指标保存在进程内存，尚未接入 PostgreSQL；
- 尚未接入 Redis Streams、Consumer Group、Pending 恢复和 Outbox；
- 图片 URI 已进入契约和场景，但尚未上传 MinIO；
- 尚未实现 FastAPI、WebUI 和真实公开数据集 Replay；
- 当前 Case Detector 只实现 Fixture Offset，Illumination Drift 和证据不足处理留待后续任务。
