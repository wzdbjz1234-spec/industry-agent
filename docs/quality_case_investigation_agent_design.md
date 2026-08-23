# Event-Driven Quality Case Investigation Agent

> 面向工业视觉质量异常的事件驱动调查 Agent——个人作品集设计方案

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 项目名称 | Quality Case Investigation Agent |
| 项目类型 | 个人作品集 / 可复现工程 Demo |
| 目标岗位 | Agent 开发工程师、AI 应用工程师、智能制造 AI 工程师 |
| 非目标岗位 | 纯视觉算法工程师 |
| 文档版本 | 1.0 |
| 核心定位 | 事件驱动、企业知识分析、现有业务系统接入、Human-in-the-loop |

---

## 2. 产品定义

### 2.1 一句话定位

> 当传统检测系统发现一段持续的质量指标异常后，系统将异常窗口冻结为 Quality Case，自动唤醒一个调查型 Agent。Agent 使用受控工具分析质量快照、检索企业技术文档和已验证历史案例，输出带证据的排查建议，经人工审批后接入 QMS 闭环，并将验证完成的结果沉淀为可复用经验。

### 2.2 产品不是做什么

本项目不是：

- 新的工业异常检测算法；
- EfficientAD 专用应用；
- 每个 NG 工件都调用一次大模型的高成本流水线；
- 用聊天框包装的普通 RAG；
- 自动决定停线、报废或修改设备参数的自治控制系统；
- 声称能够仅凭视觉信息自动确定真实根因的 RCA 系统。

检测器是可替换适配器。EfficientAD、PatchCore、PaDiM、目标检测、分类模型、规则算法或真实 AOI 系统，只要能输出统一的检测结果格式，都可以接入后续流程。

### 2.3 Agent 的准确职责

Agent 负责：

- 理解当前 Quality Case 的异常表现；
- 使用工具完成统计比较，而不是自行心算大量数字；
- 主动决定检索什么企业知识；
- 根据当前事实、技术规范和历史经验提出候选假设；
- 明确支持证据、反证和缺失证据；
- 给出有顺序、可执行、可审批的排查建议；
- 在证据不足时明确停止并请求人工调查。

Agent 不负责：

- 在线 OK/NG 判定；
- 直接控制 PLC、相机、夹具或分拣机构；
- 直接写入 QMS/MES；
- 将候选假设描述为已经确认的根因；
- 将未经人工验证的分析写入可信历史案例索引。

---

## 3. 项目切入点与突出点

### 3.1 核心切入点

工业视觉系统通常能够快速回答“哪个工件异常”，但异常发生后仍需要质量工程师人工完成：

1. 查看近期质量指标；
2. 判断异常是否持续、是否集中在特定区域；
3. 查找设备手册、SOP、FMEA；
4. 搜索过去是否出现过类似问题；
5. 形成排查顺序；
6. 在 QMS 中创建任务并等待现场反馈；
7. 归档实际原因和解决措施。

本项目切入的是这段跨数据、知识和业务系统的调查流程，而不是替代视觉模型。

### 3.2 与普通 RAG 项目的差异

| 普通 RAG | 本项目 |
|---|---|
| 用户发起问题 | 业务事件主动唤醒 Agent |
| 主要输入是自然语言 | 主要输入是不可变 Quality Case Snapshot |
| 向量检索是主体 | 向量数据库只是一个受控工具 |
| 输出答案 | 输出结构化调查分析和行动 Proposal |
| 缺少业务状态 | 有 Case、异常过程和审批状态机 |
| 通常没有外部闭环 | 人工批准后通过 Adapter 接入 QMS |
| 对话历史充当记忆 | 已验证案例形成受控的企业经验记忆 |

### 3.3 对 Agent 岗位最有价值的工程亮点

- **事件驱动 Agent**：Agent 不等待用户提问，由低频高价值业务事件唤醒。
- **实时链路隔离**：LLM 故障不会影响在线检测和分拣。
- **有界 ReAct**：Agent 自主选择工具，但受到轮次、时间、检索数量和写权限限制。
- **结构化证据链**：每个候选假设都必须绑定当前事实、规范依据或历史经验。
- **Human-in-the-loop**：Agent 只提交 Proposal，人工批准后普通业务服务才产生外部副作用。
- **可靠消息处理**：Transactional Outbox、Redis Consumer Group、幂等消费和失败恢复。
- **企业系统接入**：通过 Adapter 隔离 Mock QMS 与未来真实 MES/QMS。
- **知识闭环**：只有人工确认并验证有效的案例才进入可信向量索引。
- **可替换的 Agent Runtime**：业务工作流不依赖特定 Agent 框架或模型供应商。

---

## 4. ROI 定义

### 4.1 ROI 的业务来源

这个应用不直接提高检测模型速度。它的潜在收益来自异常发生后的调查与协作环节：

- 缩短异常初步分诊时间；
- 减少工程师搜索手册和历史记录的时间；
- 提高排查步骤的一致性和可追溯性；
- 减少重复问题再次从零调查；
- 缩短从异常发生到创建 QMS 调查任务的时间；
- 通过更快定位，潜在减少停线、持续生产不良品和报废；
- 将个人经验转化为可复用、可验证的组织知识。

### 4.2 ROI 公式

年度净收益可以定义为：

```text
Annual Benefit
= Labor Time Saved
+ Avoided Downtime Cost
+ Avoided Scrap/Rework Cost
+ Repeated-Incident Knowledge Reuse Value
```

```text
Annual Cost
= Model API / Inference Cost
+ Infrastructure Cost
+ Knowledge Maintenance Cost
+ Human Review Cost
+ System Maintenance Cost
```

```text
ROI = (Annual Benefit - Annual Cost - Initial Investment)
      / Initial Investment
```

回收周期：

```text
Payback Period = Initial Investment / Monthly Net Benefit
```

### 4.3 可直接观测的价值指标

| 指标 | 定义 |
|---|---|
| Time to First Analysis | Case 打开到 Agent 初步分析完成的时间 |
| Time to Approved Task | Case 打开到人工批准排查任务的时间 |
| Manual Triage Time | 人工为阅读快照、找资料和整理建议投入的时间 |
| Evidence Coverage | 有有效证据引用的假设占比 |
| Action Acceptance Rate | Agent Proposal 被人工批准或修改后批准的比例 |
| Repeat Case Retrieval Hit Rate | 重复事件成功命中已验证历史案例的比例 |
| Inconclusive Precision | 证据不足时，Agent 是否能够正确拒绝强行下结论 |
| Case Closure Lead Time | Case 打开到人工确认和验证完成的时间 |
| Cost per Analysis | 单次 Agent 调查的模型、检索和计算成本 |

### 4.4 作品集中的 ROI 表达边界

本项目使用公开图像与合成生产元数据，不能声称已经产生真实企业收益。README 和演示应分别展示：

1. **已测量的 Demo 指标**：Agent 时延、工具调用数、检索准确率、任务批准率、消息恢复能力；
2. **可配置的业务测算模型**：输入人工时薪、案例数量、人工分诊时长、停线成本后计算潜在 ROI；
3. **明确标注的假设示例**：所有金额均标记为 illustrative，不作为实际客户收益声明。

示例假设：

```text
每天 Case 数量：8
传统人工初步分诊：30 分钟/Case
Agent 辅助后的人工复核：8 分钟/Case
年生产天数：250
综合人工成本：150 元/小时

年度人工时间节省：
(30 - 8) / 60 × 8 × 250 = 733.3 小时

年度人工成本节省示例：
733.3 × 150 ≈ 110,000 元
```

以上仅说明计算方法。真实 ROI 通常更依赖停线和报废损失，但必须由企业真实数据验证。

---

## 5. 产品范围

### 5.1 MVP 范围

- 检测结果批量接入；
- PostgreSQL 检测记录；
- MinIO/S3 兼容图片存储；
- 时间窗口指标计算；
- NG Rate、score drift 和空间分布变化检测；
- Quality Case 聚合与不可变 Snapshot；
- `quality.case.opened.v1`事件自动触发 Agent；
- 单 Investigation Agent + 受控工具；
- 普通 Agentic RAG；
- 技术文档最小上传、Embedding 和入库；
- Case Dashboard、分析证据、人工审批；
- Mock QMS Adapter；
- 人工提交实际原因、措施和验证结果；
- JSON 全量归档和已验证案例向量索引；
- 同一 Snapshot 的人工重新分析；
- Docker Compose 一键运行。

### 5.2 MVP 明确不做

- 通用聊天入口；
- 定时班次/日报 Agent；
- 任意时间范围的自由 Agent 分析；
- 多 Agent 协作；
- Agent 直接操作 QMS/MES；
- 任意 SQL 或任意 Python 执行；
- Kubernetes、Flink、Kafka 等非必要重型基础设施；
- 自动停线或设备闭环控制；
- 将未经验证的 Case 加入可信历史案例索引。

---

## 6. 总体架构

```text
Public Dataset / Camera / Existing AOI
                 │
                 ▼
       Detector Adapter / Replay
                 │ InspectionResultBatch
                 ▼
          Inspection Ingestion API
                 │
                 ▼
     Redis Stream: inspection:results
                 │
                 ▼
              DB Writer ───────────────► PostgreSQL
                 │                           │
                 │                           ▼
                 │                    Metrics Worker
                 │                           │
                 ▼                           ▼
             MinIO/S3                 Window Metrics
                                             │
                                             ▼
                                       Event Detector
                                             │
                   PostgreSQL Transaction    │
                   ┌─────────────────────────┤
                   │ Quality Case            │
                   │ Immutable Snapshot      │
                   │ Outbox Event            │
                   └─────────────────────────┘
                                             │
                                             ▼
                                      Outbox Publisher
                                             │
                                             ▼
                         Redis Stream: quality:case-events
                                             │
                                             ▼
                                     Investigation Worker
                                             │
                    ┌────────────────────────┼──────────────────────┐
                    ▼                        ▼                      ▼
             Quality Data Tools      Knowledge Search Tool   Sample Tool
                    │                        │                      │
                    └────────────────────────┴──────────────────────┘
                                             │
                                             ▼
                                  Analysis + Task Proposal
                                             │
                                             ▼
                                        PostgreSQL
                                             │
                                             ▼
                                  WebUI Human Approval
                                             │
                                             ▼
                                      Mock QMS Adapter
                                             │
                                             ▼
                           Root Cause / Action / Verification
                                             │
                                             ▼
                         Full JSON Archive + Trusted Vector Index
```

### 6.1 关键边界

> 检测结果是高频数据，Quality Case 才是 Agent 事件。

- 完整业务事实保存在 PostgreSQL、Snapshot JSON 和对象存储；
- Redis Stream 负责传递通知与任务，不作为最终事实来源；
- Agent 通过`case_id`和`snapshot_id`读取数据，不从消息正文拼装事实；
- Agent 服务不可用时，检测、分拣、数据写入和指标计算仍可运行。

---

## 7. Quality Case 定义

### 7.1 Case 边界

一个 Quality Case 表示：

> 一个工位、一个产品、一个异常家族、一次连续异常过程。

推荐聚合键：

```text
factory_id
+ line_id
+ station_id
+ product_id
+ trigger_family
```

`trigger_family`采用稳定的异常家族：

```text
RATE_SHIFT
DISTRIBUTION_SHIFT
SCORE_SHIFT
DATA_QUALITY_FAILURE
```

异常持续时不重复创建 Case。指标恢复并持续满足恢复规则后，该异常过程结束；后续再次越界才创建新 Case。

### 7.2 双状态机

异常过程状态与人工调查状态必须分离。

```text
episode_status:
NORMAL → ACTIVE → RECOVERING → RECOVERED
                   └────────→ ACTIVE
```

```text
case_status:
OPEN
→ ANALYZING
→ WAITING_FOR_APPROVAL
→ INVESTIGATING
→ WAITING_FOR_VERIFICATION
→ CONFIRMED
→ ARCHIVED

任意调查阶段 → INCONCLUSIVE
```

`episode_status=RECOVERED`只表示指标恢复，不能证明候选根因正确。

### 7.3 Case 创建规则示例

```yaml
rule_id: ng-rate-spatial-shift
version: "1.2"

scope:
  group_by:
    - factory_id
    - line_id
    - station_id
    - product_id

window:
  type: sliding
  duration_minutes: 15
  evaluation_interval_minutes: 5
  min_sample_count: 500

conditions:
  all:
    - metric: ng_rate
      operator: greater_than
      value: 0.05
    - metric: ng_rate_ratio_to_baseline
      operator: greater_than
      value: 2.0
  any:
    - metric: spatial_shift_score
      operator: greater_than
      value: 0.7
    - metric: mean_anomaly_score_delta
      operator: greater_than
      value: 0.2

stability:
  consecutive_breaches: 2

case_policy:
  merge_window_minutes: 60
  recovery_consecutive_windows: 3
  severity: HIGH
```

### 7.4 Snapshot 原则

- Case 创建时生成 Snapshot v1；
- Snapshot 创建后不可修改；
- Agent 分析期间新检测数据继续落库，但不进入当前 Snapshot；
- 异常过程的实时指标可以继续更新，但与 Snapshot 分开保存；
- 人工“重新分析”仍使用同一 Snapshot，并创建新的`analysis_run_id`；
- 未来如需重新冻结证据，应显式创建 Snapshot v2，不得覆盖 v1；
- MVP 默认只使用 Snapshot v1，不实现持续重分析。

---

## 8. 消息设计总则

### 8.1 事件命名

事件使用已经发生的业务事实和版本号：

```text
<domain>.<aggregate>.<past-tense-action>.v<schema-version>
```

例如：

```text
quality.case.opened.v1
quality.analysis.completed.v1
quality.investigation.approved.v1
quality.case.confirmed.v1
```

### 8.2 通用事件信封

所有业务事件使用统一信封：

```json
{
  "spec_version": "1.0",
  "event_id": "evt_01K2Q9E4F5M8R7T6",
  "event_type": "quality.case.opened.v1",
  "occurred_at": "2026-08-22T10:30:00.123+08:00",
  "source": "quality-case-service",
  "subject": "quality-case/QC-20260822-0042",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "window-evaluation-01K2Q9",
  "trace_id": "trace-01K2Q9",
  "partition_key": "factory-01:line-01:part-A",
  "data": {}
}
```

字段语义：

| 字段 | 说明 |
|---|---|
| `event_id` | 全局唯一业务幂等键 |
| `event_type` | 事件类型和 Schema 主版本 |
| `occurred_at` | 业务事实发生时间，不是 Redis 入队时间 |
| `source` | 产生事件的服务 |
| `subject` | 事件对应业务实体 |
| `correlation_id` | 贯穿整个 Case 生命周期 |
| `causation_id` | 导致该事件的上游事件或命令 |
| `trace_id` | 跨服务可观测性追踪标识 |
| `partition_key` | 保证同一业务范围内有序处理的键 |
| `data` | 事件专有数据 |

### 8.3 交付语义

- Redis Streams使用 at-least-once 交付；
- 消费者不能假设消息只到达一次；
- 所有副作用必须以`event_id`或业务唯一键实现幂等；
- 只有业务结果成功持久化后才能`XACK`；
- 超时 Pending 消息使用`XAUTOCLAIM`接管；
- 超过最大重试次数的消息进入 Dead Letter Stream。

### 8.4 消息目录

下表是MVP消息契约的完整目录。未列入表中的内部函数调用不视为跨进程消息。

| 消息类型 | 类别 | 生产者 | 主要消费者 | 作用 |
|---|---|---|---|---|
| `inspection.result.batch.v1` | 数据消息 | Detector Adapter | DB Writer | 批量传输逐件检测结果 |
| `quality.case.opened.v1` | 业务事件 | Quality Case Service | Investigation Agent | 创建Case后自动触发调查 |
| `quality.episode.recovered.v1` | 业务事件 | Quality Case Service | Projection/UI | 通知异常指标恢复 |
| `quality.analysis.started.v1` | 业务事件 | Investigation Agent | Projection/UI | 记录一次分析开始 |
| `quality.analysis.completed.v1` | 业务事件 | Investigation Agent | Projection/UI | 记录结构化分析完成 |
| `quality.analysis.failed.v1` | 业务事件 | Investigation Agent | Projection/UI/Operations | 记录本次分析最终失败 |
| `quality.investigation.proposed.v1` | 业务事件 | Investigation Agent | Projection/UI | 通知产生了待审批Proposal |
| `quality.investigation.approved.v1` | 业务事件 | Quality Case API | QMS Integration | 通知人工已经批准Proposal |
| `quality.investigation.rejected.v1` | 业务事件 | Quality Case API | Projection/UI | 通知人工驳回Proposal |
| `qms.task.created.v1` | 集成事件 | QMS Adapter | Quality Case Service/UI | 通知外部调查任务已创建 |
| `qms.task.result-submitted.v1` | 入站集成事件 | Mock/External QMS | Quality Case Service | 回传实际原因、措施和验证结果 |
| `quality.case.confirmed.v1` | 业务事件 | Quality Case Service | Archive Worker | 通知案例已经人工确认 |
| `quality.case.archived.v1` | 业务事件 | Archive Worker | Projection/UI | 通知JSON归档和知识索引完成 |
| DLQ消息 | 运维消息 | 任意Consumer | Operations | 保存超过重试上限的失败事件 |

---

## 9. 检测数据消息

### 9.1 `inspection.result.batch.v1`

用途：Detector Adapter批量提交检测结果。它属于数据流消息，不触发Agent。

推荐传输：

```text
POST /api/v1/inspection-results/batches
```

接入服务校验后写入：

```text
Redis Stream: inspection:results
Consumer Group: inspection-db-writers
```

消息格式：

```json
{
  "schema_version": "1.0",
  "batch_message_id": "ib_01K2Q8Z8",
  "producer_id": "detector-adapter-01",
  "produced_at": "2026-08-22T10:21:35.000+08:00",
  "records": [
    {
      "result_id": "ir_01K2Q8Y1",
      "inspected_at": "2026-08-22T10:21:34.123+08:00",
      "factory_id": "factory-01",
      "line_id": "line-01",
      "station_id": "camera-01",
      "product_id": "part-A",
      "unit_id": "unit-000238",
      "batch_id": "batch-20260822-03",
      "is_ng": true,
      "anomaly_score": 0.86,
      "threshold": 0.51,
      "defect_type": "surface_anomaly",
      "defect_region": {
        "x_normalized": 0.71,
        "y_normalized": 0.23,
        "area_ratio": 0.08,
        "region_label": "upper_right"
      },
      "image_uri": "s3://inspection/2026-08-22/ir_01K2Q8Y1.png",
      "anomaly_map_uri": "s3://inspection/2026-08-22/ir_01K2Q8Y1-map.png",
      "detector": {
        "type": "efficientad-compatible",
        "model_version": "detector-1.2.0",
        "adapter_version": "1.0.0"
      },
      "metadata": {
        "shift": "A",
        "simulated": true
      }
    }
  ]
}
```

约束：

- `result_id`全局唯一，数据库设置唯一约束；
- 单批建议1至100条，按吞吐压测调整；
- 图片二进制不进入Redis，消息只携带URI；
- 正常样本默认不保存全部原图，可按固定比例抽样；
- NG样本保留代表性图片、热力图和元数据；
- Producer重试导致批次重复时，DB Writer依靠`result_id`去重。

---

## 10. Quality Case Snapshot格式

Snapshot是Agent分析的主要事实对象，不作为Redis消息正文传输。

```json
{
  "schema_version": "1.0",
  "snapshot_id": "QCS-20260822-0042-v1",
  "snapshot_version": 1,
  "case_id": "QC-20260822-0042",
  "created_at": "2026-08-22T10:30:00+08:00",
  "immutable": true,

  "scope": {
    "factory_id": "factory-01",
    "line_id": "line-01",
    "station_id": "camera-01",
    "product_id": "part-A",
    "batch_ids": ["batch-20260822-03"],
    "detector_type": "efficientad-compatible",
    "model_versions": ["detector-1.2.0"]
  },

  "trigger": {
    "rule_id": "ng-rate-spatial-shift",
    "rule_version": "1.2",
    "trigger_family": "DISTRIBUTION_SHIFT",
    "severity": "HIGH",
    "summary": "NG率显著升高，异常区域集中于工件右上方",
    "consecutive_breaches": 2
  },

  "windows": {
    "observation": {
      "start": "2026-08-22T10:15:00+08:00",
      "end": "2026-08-22T10:30:00+08:00"
    },
    "lookback": {
      "start": "2026-08-22T08:00:00+08:00",
      "end": "2026-08-22T10:15:00+08:00"
    },
    "baseline": {
      "start": "2026-08-15T00:00:00+08:00",
      "end": "2026-08-21T23:59:59+08:00",
      "selection_method": "same_station_product_last_7_days"
    }
  },

  "metrics": {
    "observation": {
      "total_count": 2480,
      "ng_count": 216,
      "ng_rate": 0.0871,
      "score_mean": 0.48,
      "score_p95": 0.91
    },
    "baseline": {
      "total_count": 112400,
      "ng_count": 2360,
      "ng_rate": 0.021,
      "score_mean": 0.22,
      "score_p95": 0.44
    },
    "changes": {
      "ng_rate_absolute_delta": 0.0661,
      "ng_rate_ratio": 4.15,
      "score_mean_delta": 0.26,
      "score_p95_delta": 0.47
    }
  },

  "distribution": {
    "spatial_shift_score": 0.82,
    "dominant_region": "upper_right",
    "dominant_region_ratio": 0.74,
    "region_counts": {
      "upper_left": 12,
      "upper_right": 160,
      "center": 25,
      "lower_left": 8,
      "lower_right": 11
    },
    "defect_type_counts": {
      "scratch": 23,
      "surface_anomaly": 193
    }
  },

  "representative_samples": [
    {
      "result_id": "ir_01K2Q8Y1",
      "image_uri": "s3://inspection/2026-08-22/ir_01K2Q8Y1.png",
      "anomaly_map_uri": "s3://inspection/2026-08-22/ir_01K2Q8Y1-map.png",
      "anomaly_score": 0.91,
      "selection_reason": "highest_anomaly_score"
    }
  ],

  "data_quality": {
    "missing_record_ratio": 0.002,
    "sample_count_sufficient": true,
    "timestamp_gap_detected": false,
    "mixed_model_versions": false,
    "warnings": []
  },

  "integrity": {
    "content_hash": "sha256:...",
    "record_count": 2480
  }
}
```

---

## 11. Quality Case生命周期消息

### 11.1 `quality.case.opened.v1`

用途：唯一的MVP自动Agent触发事件。

```json
{
  "spec_version": "1.0",
  "event_id": "evt_01K2Q9E4F5M8R7T6",
  "event_type": "quality.case.opened.v1",
  "occurred_at": "2026-08-22T10:30:00.123+08:00",
  "source": "quality-case-service",
  "subject": "quality-case/QC-20260822-0042",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "window-evaluation-01K2Q9",
  "trace_id": "trace-01K2Q9",
  "partition_key": "factory-01:line-01:part-A",
  "data": {
    "case_id": "QC-20260822-0042",
    "snapshot_id": "QCS-20260822-0042-v1",
    "snapshot_version": 1,
    "scope": {
      "factory_id": "factory-01",
      "line_id": "line-01",
      "station_id": "camera-01",
      "product_id": "part-A"
    },
    "observation_window": {
      "start": "2026-08-22T10:15:00+08:00",
      "end": "2026-08-22T10:30:00+08:00"
    },
    "trigger": {
      "rule_id": "ng-rate-spatial-shift",
      "rule_version": "1.2",
      "trigger_family": "DISTRIBUTION_SHIFT",
      "severity": "HIGH",
      "summary": "NG率显著升高，异常区域集中于工件右上方"
    },
    "routing": {
      "analysis_profile": "visual-quality-investigation",
      "priority": 80
    }
  }
}
```

### 11.2 `quality.episode.recovered.v1`

用途：通知异常指标已经恢复，只更新`episode_status`，不自动确认根因，也不改变已经冻结的Snapshot。

```json
{
  "spec_version": "1.0",
  "event_id": "evt_01K2QB10",
  "event_type": "quality.episode.recovered.v1",
  "occurred_at": "2026-08-22T11:15:00+08:00",
  "source": "quality-case-service",
  "subject": "quality-case/QC-20260822-0042",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "window-evaluation-01K2QB",
  "trace_id": "trace-01K2Q9",
  "partition_key": "factory-01:line-01:part-A",
  "data": {
    "case_id": "QC-20260822-0042",
    "recovered_at": "2026-08-22T11:15:00+08:00",
    "recovery_rule_id": "ng-rate-spatial-shift",
    "normal_windows": 3,
    "current_ng_rate": 0.019,
    "baseline_ng_rate": 0.021
  }
}
```

---

## 12. Agent运行与工具设计

### 12.1 稳定接口

业务系统只依赖稳定接口，不依赖LangGraph或特定模型：

```python
class InvestigationAgent(Protocol):
    async def analyze(
        self,
        snapshot: QualityCaseSnapshot,
        tools: InvestigationTools,
        limits: AgentLimits,
    ) -> InvestigationAnalysis:
        ...
```

### 12.2 有界ReAct循环

```text
加载不可变Snapshot
→ 判断数据是否足够
→ 形成候选假设
→ 选择统计、样本或知识检索工具
→ 读取结构化Observation
→ 更新假设、反证和缺失证据
→ 输出分析或INSUFFICIENT_EVIDENCE
```

推荐预算：

```yaml
agent_limits:
  max_iterations: 8
  max_total_seconds: 120
  max_tool_failures: 3
  max_retrieval_calls: 6
  top_k_per_retrieval: 5
  max_evidence_items_in_context: 12
  tool_timeout_seconds: 10
```

终止条件：

- 已形成满足Schema的可执行建议；
- 证据不足，需要人工补充信息；
- 达到轮次或时间预算；
- 连续工具失败；
- Snapshot存在严重数据质量问题。

### 12.3 工具集合

```text
get_case_snapshot(case_id, snapshot_id)
compare_quality_metrics(snapshot_id, dimensions)
get_representative_samples(snapshot_id, strategy, limit)
search_knowledge_base(query, source_types, filters, top_k)
submit_investigation_analysis(analysis)
submit_task_proposal(proposal)
```

限制：

- 不提供任意SQL；
- 不提供任意Python执行；
- 不提供QMS写工具；
- 不允许修改Snapshot；
- 不允许修改或删除知识索引；
- 所有工具参数和结果摘要写入Trace。

### 12.4 Agentic RAG工具请求

```json
{
  "query": "夹具定位偏移的检查步骤以及可能出现的空间异常特征",
  "source_types": ["TECHNICAL_DOCUMENT", "VERIFIED_CASE"],
  "filters": {
    "station_id": "camera-01",
    "product_id": "part-A",
    "effective_at": "2026-08-22T10:30:00+08:00",
    "status": "ACTIVE"
  },
  "top_k": 5
}
```

工具响应：

```json
{
  "items": [
    {
      "evidence_id": "DOC-0014:chunk-0082",
      "evidence_type": "TECHNICAL_DOCUMENT",
      "title": "夹具维护手册",
      "version": "3.2",
      "section": "4.1 定位销检查",
      "page": 17,
      "content": "……",
      "retrieval_score": 0.83,
      "applicability": {
        "status": "APPLICABLE",
        "reasons": [
          "适用于fixture-A",
          "适用于part-A",
          "事件发生时文档有效"
        ]
      }
    }
  ],
  "query_metadata": {
    "embedding_model": "configured-embedding-model",
    "collection": "enterprise-knowledge",
    "duration_ms": 143
  }
}
```

---

## 13. 证据模型

### 13.1 证据等级

| 等级 | 来源 | 用途 |
|---|---|---|
| A：当前事实 | 当前Snapshot、统计结果、图片 | 描述当前Case真实表现 |
| B：规范依据 | 当前有效技术手册、SOP、FMEA | 提供适用规范和标准排查步骤 |
| C：经验依据 | 已确认且验证有效的历史案例 | 提供候选假设，不能单独证明根因 |

约束：

- 没有A级证据，不得对当前Case作确定性描述；
- 历史案例相似度不能直接转换成根因置信度；
- 技术文档必须携带版本、章节、页码和适用范围；
- 文档过期或适用范围不匹配时只能作为低可信参考；
- 证据冲突必须显式输出；
- 证据不足时返回`INSUFFICIENT_EVIDENCE`。

### 13.2 Evidence格式

```json
{
  "evidence_id": "EV-001",
  "evidence_class": "A",
  "evidence_type": "CURRENT_SNAPSHOT",
  "reference": "QCS-20260822-0042-v1#/distribution",
  "claim": "74%的NG样本集中在工件右上区域",
  "supports": ["H-01"],
  "contradicts": [],
  "applicability": "DIRECT",
  "retrieved_at": null
}
```

---

## 14. Agent运行消息

### 14.1 `quality.analysis.started.v1`

```json
{
  "spec_version": "1.0",
  "event_id": "evt_analysis_started_01",
  "event_type": "quality.analysis.started.v1",
  "occurred_at": "2026-08-22T10:30:02+08:00",
  "source": "investigation-agent-service",
  "subject": "analysis-run/AR-20260822-0042-01",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_01K2Q9E4F5M8R7T6",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "analysis_run_id": "AR-20260822-0042-01",
    "case_id": "QC-20260822-0042",
    "snapshot_id": "QCS-20260822-0042-v1",
    "trigger_mode": "EVENT",
    "agent_profile": "visual-quality-investigation-v1",
    "model_config_id": "default-investigation-model"
  }
}
```

人工重新分析时：

```json
{
  "analysis_run_id": "AR-20260822-0042-02",
  "case_id": "QC-20260822-0042",
  "snapshot_id": "QCS-20260822-0042-v1",
  "trigger_mode": "HUMAN_RERUN",
  "requested_by": "engineer-01"
}
```

### 14.2 Agent Trace格式

Trace只保存结构化操作和决策摘要，不保存模型完整自由推理过程。

```json
{
  "trace_step_id": "TS-0003",
  "analysis_run_id": "AR-20260822-0042-01",
  "step": 3,
  "timestamp": "2026-08-22T10:31:08+08:00",
  "action_type": "TOOL_CALL",
  "action": {
    "tool": "search_knowledge_base",
    "arguments": {
      "query": "夹具定位偏移 检查步骤",
      "source_types": ["TECHNICAL_DOCUMENT"],
      "top_k": 5
    }
  },
  "observation": {
    "status": "SUCCESS",
    "returned_count": 3,
    "evidence_ids": [
      "DOC-0014:chunk-0082",
      "DOC-0014:chunk-0084"
    ],
    "duration_ms": 143
  },
  "decision_summary": "结果支持优先检查定位销，但仍缺少当前夹具测量数据。",
  "hypothesis_updates": [
    {
      "hypothesis_id": "H-01",
      "status_before": "CANDIDATE",
      "status_after": "SUPPORTED",
      "confidence_before": 0.55,
      "confidence_after": 0.68
    }
  ]
}
```

### 14.3 InvestigationAnalysis格式

```json
{
  "schema_version": "1.0",
  "analysis_run_id": "AR-20260822-0042-01",
  "case_id": "QC-20260822-0042",
  "snapshot_id": "QCS-20260822-0042-v1",
  "status": "COMPLETED",
  "completed_at": "2026-08-22T10:31:17+08:00",
  "summary": "当前窗口NG率较基线升高4.15倍，异常区域明显集中于右上方。现有证据支持优先检查夹具定位，但不足以确认真实根因。",
  "hypotheses": [
    {
      "hypothesis_id": "H-01",
      "title": "夹具定位发生方向性偏移",
      "status": "SUPPORTED",
      "confidence": 0.68,
      "supporting_evidence_ids": [
        "EV-SNAPSHOT-01",
        "DOC-0014:chunk-0082",
        "CASE-QC-20260417-0018"
      ],
      "counter_evidence_ids": [],
      "missing_evidence": [
        "当前定位销间隙测量结果",
        "最近一次换线和维护记录"
      ],
      "recommended_checks": [
        "测量定位销间隙",
        "使用基准件复测工件成像位置"
      ]
    },
    {
      "hypothesis_id": "H-02",
      "title": "局部光照发生变化",
      "status": "POSSIBLE",
      "confidence": 0.42,
      "supporting_evidence_ids": ["DOC-0021:chunk-0011"],
      "counter_evidence_ids": [],
      "missing_evidence": ["当前光照强度记录"],
      "recommended_checks": ["检查光源角度和亮度"]
    }
  ],
  "evidence": [],
  "limitations": [
    "Snapshot不包含夹具测量和光照传感器数据",
    "历史案例相似性不能证明本次根因"
  ],
  "termination": {
    "reason": "ACTIONABLE_RECOMMENDATION_READY",
    "iterations": 5,
    "tool_calls": 4,
    "retrieval_calls": 2,
    "duration_ms": 15120
  },
  "usage": {
    "input_tokens": 8200,
    "output_tokens": 1300,
    "estimated_cost": 0.0,
    "currency": "CNY"
  }
}
```

证据不足时：

```json
{
  "status": "INSUFFICIENT_EVIDENCE",
  "summary": "样本数量不足且当前窗口混用了两个模型版本，无法可靠判断质量分布是否真实变化。",
  "hypotheses": [],
  "required_information": [
    "统一模型版本后的至少500条检测记录",
    "相机曝光和光源状态"
  ],
  "termination": {
    "reason": "DATA_QUALITY_BLOCKED"
  }
}
```

### 14.4 `quality.analysis.completed.v1`

Event只携带分析结果引用和摘要，不复制完整分析正文。

```json
{
  "spec_version": "1.0",
  "event_id": "evt_analysis_completed_01",
  "event_type": "quality.analysis.completed.v1",
  "occurred_at": "2026-08-22T10:31:17+08:00",
  "source": "investigation-agent-service",
  "subject": "analysis-run/AR-20260822-0042-01",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_analysis_started_01",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "analysis_run_id": "AR-20260822-0042-01",
    "case_id": "QC-20260822-0042",
    "snapshot_id": "QCS-20260822-0042-v1",
    "status": "COMPLETED",
    "analysis_uri": "db://investigation_analysis/AR-20260822-0042-01",
    "top_hypothesis": "夹具定位发生方向性偏移",
    "top_confidence": 0.68,
    "requires_human_review": true
  }
}
```

### 14.5 `quality.analysis.failed.v1`

只有在重试预算耗尽或发生不可恢复错误时发布。单次工具失败只记录Trace，不立即发布该事件。

```json
{
  "spec_version": "1.0",
  "event_id": "evt_analysis_failed_01",
  "event_type": "quality.analysis.failed.v1",
  "occurred_at": "2026-08-22T10:40:00+08:00",
  "source": "investigation-agent-service",
  "subject": "analysis-run/AR-20260822-0042-01",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_analysis_started_01",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "analysis_run_id": "AR-20260822-0042-01",
    "case_id": "QC-20260822-0042",
    "snapshot_id": "QCS-20260822-0042-v1",
    "failure_code": "TOOL_RETRY_EXHAUSTED",
    "failure_summary": "知识检索工具连续超时，分析未形成有效结果。",
    "retryable": true,
    "attempts": 3,
    "requires_human_attention": true
  }
}
```

---

## 15. Proposal、审批与QMS消息

### 15.1 InvestigationTaskProposal格式

Agent只能提交Proposal，不能直接创建QMS任务。

```json
{
  "schema_version": "1.0",
  "proposal_id": "PROP-20260822-0012",
  "case_id": "QC-20260822-0042",
  "analysis_run_id": "AR-20260822-0042-01",
  "created_at": "2026-08-22T10:31:17+08:00",
  "title": "检查camera-01工位夹具定位状态",
  "reason": "NG区域出现方向性聚集，当前快照和适用技术手册均支持优先检查定位销。",
  "steps": [
    {
      "order": 1,
      "instruction": "测量定位销间隙",
      "expected_evidence": "定位销间隙测量值"
    },
    {
      "order": 2,
      "instruction": "使用基准件复测工件位置",
      "expected_evidence": "基准件位置偏移量"
    },
    {
      "order": 3,
      "instruction": "检查最近一次换线记录",
      "expected_evidence": "换线时间和操作记录"
    }
  ],
  "requested_role": "QUALITY_ENGINEER",
  "priority": "HIGH",
  "risk_level": "LOW",
  "evidence_ids": [
    "QCS-20260822-0042-v1",
    "DOC-0014:chunk-0082"
  ],
  "status": "PENDING_APPROVAL"
}
```

Proposal和Analysis在同一个数据库事务中持久化后，Outbox发布：

```json
{
  "spec_version": "1.0",
  "event_id": "evt_investigation_proposed_01",
  "event_type": "quality.investigation.proposed.v1",
  "occurred_at": "2026-08-22T10:31:17+08:00",
  "source": "investigation-agent-service",
  "subject": "proposal/PROP-20260822-0012",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_analysis_completed_01",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "proposal_id": "PROP-20260822-0012",
    "case_id": "QC-20260822-0042",
    "analysis_run_id": "AR-20260822-0042-01",
    "title": "检查camera-01工位夹具定位状态",
    "priority": "HIGH",
    "risk_level": "LOW",
    "status": "PENDING_APPROVAL"
  }
}
```

### 15.2 人工审批命令

API：

```text
POST /api/v1/proposals/{proposal_id}/decision
```

请求格式：

```json
{
  "decision_id": "DEC-20260822-0008",
  "decision": "APPROVE_WITH_CHANGES",
  "decided_by": "engineer-01",
  "decided_at": "2026-08-22T10:45:00+08:00",
  "comment": "增加光源检查并调整任务顺序",
  "approved_steps": [
    "检查光源角度和亮度",
    "测量定位销间隙",
    "使用基准件复测工件位置"
  ]
}
```

允许的决定：

```text
APPROVE
APPROVE_WITH_CHANGES
REJECT
REQUEST_REANALYSIS
```

### 15.3 `quality.investigation.approved.v1`

```json
{
  "spec_version": "1.0",
  "event_id": "evt_investigation_approved_01",
  "event_type": "quality.investigation.approved.v1",
  "occurred_at": "2026-08-22T10:45:00+08:00",
  "source": "quality-case-api",
  "subject": "proposal/PROP-20260822-0012",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "DEC-20260822-0008",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "case_id": "QC-20260822-0042",
    "proposal_id": "PROP-20260822-0012",
    "decision": "APPROVE_WITH_CHANGES",
    "approved_by": "engineer-01",
    "approved_steps": [
      "检查光源角度和亮度",
      "测量定位销间隙",
      "使用基准件复测工件位置"
    ]
  }
}
```

拒绝时使用：

```json
{
  "spec_version": "1.0",
  "event_id": "evt_investigation_rejected_01",
  "event_type": "quality.investigation.rejected.v1",
  "occurred_at": "2026-08-22T10:45:00+08:00",
  "source": "quality-case-api",
  "subject": "proposal/PROP-20260822-0012",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "DEC-20260822-0008",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "case_id": "QC-20260822-0042",
    "proposal_id": "PROP-20260822-0012",
    "rejected_by": "engineer-01",
    "rejection_reason": "当前异常与夹具无关，应先补充相机曝光记录。",
    "request_reanalysis": true
  }
}
```

`rejection_reason`为强制字段。驳回Proposal不等于关闭Quality Case。

### 15.4 `qms.task.created.v1`

人工批准事件由普通业务服务消费，再调用Mock QMS Adapter。

```json
{
  "spec_version": "1.0",
  "event_id": "evt_qms_task_created_01",
  "event_type": "qms.task.created.v1",
  "occurred_at": "2026-08-22T10:45:02+08:00",
  "source": "mock-qms-adapter",
  "subject": "qms-task/QMS-TASK-0087",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_investigation_approved_01",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "task_id": "QMS-TASK-0087",
    "case_id": "QC-20260822-0042",
    "proposal_id": "PROP-20260822-0012",
    "external_system": "MOCK_QMS",
    "status": "OPEN",
    "assignee_role": "QUALITY_ENGINEER",
    "created_by": "quality-integration-service",
    "task_uri": "/mock-qms/tasks/QMS-TASK-0087"
  }
}
```

---

## 16. 人工结论与知识闭环消息

### 16.1 QMS调查结果回传

工程师在Mock QMS中填写实际原因、措施和验证结果。QMS Adapter通过Webhook向Quality Case Service回传：

```json
{
  "spec_version": "1.0",
  "event_id": "evt_qms_result_submitted_01",
  "event_type": "qms.task.result-submitted.v1",
  "occurred_at": "2026-08-22T13:20:00+08:00",
  "source": "mock-qms-adapter",
  "subject": "qms-task/QMS-TASK-0087",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "QMS-TASK-0087",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "confirmation_id": "CONF-20260822-0004",
    "case_id": "QC-20260822-0042",
    "task_id": "QMS-TASK-0087",
    "confirmed_by": "engineer-01",
    "actual_root_cause": {
      "code": "FIXTURE_LOCATING_PIN_LOOSE",
      "description": "定位销松动导致工件向右上方向偏移"
    },
    "actual_actions": [
      "更换定位销",
      "重新标定夹具",
      "使用基准件完成位置确认"
    ],
    "verification": {
      "status": "VERIFIED_EFFECTIVE",
      "start": "2026-08-22T12:30:00+08:00",
      "end": "2026-08-22T13:15:00+08:00",
      "sample_count": 500,
      "ng_rate_before": 0.0871,
      "ng_rate_after": 0.018,
      "acceptance_criteria": "连续500件NG率低于2%",
      "notes": "异常空间聚集消失"
    },
    "agent_assessment": {
      "top_hypothesis_matched": true,
      "useful": true,
      "human_rating": 4,
      "comment": "排查顺序有效"
    }
  }
}
```

Webhook端点：

```text
POST /api/v1/integrations/qms/task-results
```

Quality Case Service校验`task_id`、`case_id`、签名和幂等键后，在同一个事务中保存人工结论并生成`quality.case.confirmed.v1` Outbox事件。

### 16.2 `quality.case.confirmed.v1`

```json
{
  "spec_version": "1.0",
  "event_id": "evt_case_confirmed_01",
  "event_type": "quality.case.confirmed.v1",
  "occurred_at": "2026-08-22T13:20:00+08:00",
  "source": "quality-case-api",
  "subject": "quality-case/QC-20260822-0042",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "CONF-20260822-0004",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "case_id": "QC-20260822-0042",
    "confirmation_id": "CONF-20260822-0004",
    "verification_status": "VERIFIED_EFFECTIVE",
    "knowledge_promotion_eligible": true,
    "confirmed_by": "engineer-01"
  }
}
```

### 16.3 历史Case完整JSON归档格式

所有Case都保存完整JSON审计记录，无论最终是否确认。文件建议：

```text
case_archive/2026/08/22/2026-08-22_QC-20260822-0042.json
```

```json
{
  "schema_version": "1.0",
  "archived_at": "2026-08-22T13:20:03+08:00",
  "case": {
    "case_id": "QC-20260822-0042",
    "episode_status": "RECOVERED",
    "case_status": "CONFIRMED"
  },
  "snapshot": {
    "snapshot_id": "QCS-20260822-0042-v1"
  },
  "analysis_runs": [
    {
      "analysis_run_id": "AR-20260822-0042-01",
      "status": "COMPLETED"
    }
  ],
  "approved_proposal": {
    "proposal_id": "PROP-20260822-0012"
  },
  "qms_task": {
    "task_id": "QMS-TASK-0087"
  },
  "human_confirmation": {
    "confirmation_id": "CONF-20260822-0004",
    "actual_root_cause": "定位销松动导致工件向右上方向偏移",
    "actual_actions": ["更换定位销", "重新标定夹具"],
    "verification_status": "VERIFIED_EFFECTIVE"
  },
  "integrity": {
    "content_hash": "sha256:..."
  }
}
```

实际归档文件应内嵌完整Snapshot、所有Analysis、Trace摘要、审批和人工结论，而不是只保存示例中的ID引用。

### 16.4 可信历史案例向量索引格式

只有同时满足以下条件的Case才能进入Agent可检索索引：

```text
case_status == CONFIRMED
verification.status == VERIFIED_EFFECTIVE
actual_root_cause 非空
actual_actions 非空
```

索引文本：

```text
日期：2026-08-22
案例：QC-20260822-0042
工位：camera-01
产品：part-A
异常表现：NG率由2.1%升至8.71%，74%的异常集中于右上区域。
Agent初步假设：夹具定位偏移。
人工确认根因：定位销松动导致工件向右上方向偏移。
实际措施：更换定位销并重新标定夹具。
验证结果：连续500件NG率恢复至1.8%，空间聚集消失。
```

向量记录：

```json
{
  "document_id": "verified-case:QC-20260822-0042",
  "source_type": "VERIFIED_CASE",
  "text": "日期：2026-08-22\n案例：QC-20260822-0042\n……",
  "metadata": {
    "case_id": "QC-20260822-0042",
    "date_prefix": "2026-08-22",
    "factory_id": "factory-01",
    "line_id": "line-01",
    "station_id": "camera-01",
    "product_id": "part-A",
    "trigger_family": "DISTRIBUTION_SHIFT",
    "root_cause_code": "FIXTURE_LOCATING_PIN_LOOSE",
    "verification_status": "VERIFIED_EFFECTIVE",
    "indexed_at": "2026-08-22T13:20:05+08:00"
  }
}
```

日期既出现在文本前缀中，也必须作为结构化Metadata保存。

### 16.5 `quality.case.archived.v1`

```json
{
  "spec_version": "1.0",
  "event_id": "evt_case_archived_01",
  "event_type": "quality.case.archived.v1",
  "occurred_at": "2026-08-22T13:20:05+08:00",
  "source": "case-archive-worker",
  "subject": "quality-case/QC-20260822-0042",
  "correlation_id": "QC-20260822-0042",
  "causation_id": "evt_case_confirmed_01",
  "trace_id": "trace-01K2Q9",
  "partition_key": "QC-20260822-0042",
  "data": {
    "case_id": "QC-20260822-0042",
    "archive_uri": "s3://case-archive/2026/08/22/2026-08-22_QC-20260822-0042.json",
    "knowledge_index_status": "INDEXED",
    "knowledge_document_id": "verified-case:QC-20260822-0042",
    "content_hash": "sha256:..."
  }
}
```

---

## 17. Transactional Outbox格式

Quality Case、Snapshot和待发布事件必须在同一个PostgreSQL事务中创建。

```sql
CREATE TABLE outbox_events (
    event_id          VARCHAR PRIMARY KEY,
    aggregate_type    VARCHAR NOT NULL,
    aggregate_id      VARCHAR NOT NULL,
    event_type        VARCHAR NOT NULL,
    payload           JSONB NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL,
    published_at      TIMESTAMPTZ,
    publish_attempts  INTEGER NOT NULL DEFAULT 0,
    last_error        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

事务边界：

```sql
BEGIN;

INSERT INTO quality_cases (...);
INSERT INTO quality_case_snapshots (...);
INSERT INTO outbox_events (..., 'quality.case.opened.v1', ...);

COMMIT;
```

Outbox Publisher：

```text
读取未发布Outbox
→ XADD quality:case-events
→ 标记published_at
```

如果Publisher在`XADD`后、标记完成前崩溃，事件可能重复发布；Agent端依靠`event_id`幂等处理。

---

## 18. Redis Streams设计

| Stream | Consumer Group | 用途 |
|---|---|---|
| `inspection:results` | `inspection-db-writers` | 批量检测数据落库 |
| `quality:case-events` | `investigation-agents` | Agent消费`quality.case.opened.v1` |
| `quality:case-events` | `quality-projections` | 更新WebUI查询模型 |
| `quality:case-events` | `qms-integrations` | 消费人工批准事件并创建QMS任务 |
| `quality:case-events` | `case-archivers` | 消费确认事件并归档、索引 |
| `quality:case-events:dlq` | `operations` | 记录多次失败的事件 |

消费规则：

```text
XREADGROUP领取
→ 检查event_id是否已完成
→ 执行业务处理
→ 在同一数据库事务中保存结果和幂等记录
→ XACK
```

恢复规则：

- 5分钟未确认的Pending消息允许`XAUTOCLAIM`；
- 默认最多重试3次；
- 超过上限写入DLQ并确认原消息；
- WebUI显示失败状态和人工重试入口；
- Redis Stream可以设置近似`MAXLEN`，但PostgreSQL和归档JSON仍是事实来源。

DLQ消息格式：

```json
{
  "failed_event_id": "evt_01K2Q9E4F5M8R7T6",
  "failed_event_type": "quality.case.opened.v1",
  "case_id": "QC-20260822-0042",
  "consumer_group": "investigation-agents",
  "consumer": "agent-worker-01",
  "attempts": 3,
  "failed_at": "2026-08-22T10:40:00+08:00",
  "error_type": "TOOL_TIMEOUT",
  "error_message": "knowledge retrieval timed out",
  "original_payload": {}
}
```

---

## 19. 文档入库设计

### 19.1 最小上传字段

上传界面保持简单，但以下信息必须提供：

```text
文件
文档类型
版本号
生效日期
适用设备、工位或产品
```

文档记录：

```json
{
  "document_id": "DOC-20260822-0014",
  "title": "夹具维护手册",
  "document_type": "TECHNICAL_MANUAL",
  "version": "3.2",
  "effective_from": "2026-06-01",
  "effective_to": null,
  "applicability": {
    "equipment_types": ["fixture-A"],
    "station_ids": ["camera-01"],
    "product_ids": ["part-A"]
  },
  "status": "ACTIVE",
  "uploaded_at": "2026-08-22T14:20:00+08:00",
  "content_hash": "sha256:..."
}
```

Chunk记录：

```json
{
  "chunk_id": "DOC-20260822-0014:chunk-0082",
  "document_id": "DOC-20260822-0014",
  "section": "4.1 定位销检查",
  "page": 17,
  "text": "……",
  "version": "3.2",
  "status": "ACTIVE",
  "applicable_product_ids": ["part-A"]
}
```

旧版本不删除，只标记为`SUPERSEDED`。默认检索只使用事件发生时有效且适用范围匹配的文档。

---

## 20. WebUI设计

主产品采用WebUI。桌面GUI仅作为检测器调试、阈值标定或本地工程工具。

推荐技术栈：

```text
FastAPI + React/Vue + ECharts + SSE
```

SSE用于把Case状态和Agent进度推送到浏览器；浏览器不直接连接Redis。

### 20.1 页面

```text
/overview             质量概览和待处理Case
/cases                Quality Case列表
/cases/{case_id}      Case详情、证据、Trace和审批
/review               待人工审批任务
/documents            文档上传、版本和索引状态
/case-library         已验证历史案例
/operations           DLQ和失败任务，仅演示运维能力
```

### 20.2 Case详情页

```text
┌──────────── Quality Case #QC-20260822-0042 ────────────┐
│ NG率 2.1% → 8.7%   右上区域聚集   状态：待人工审批     │
├──────────────────────┬─────────────────────────────────┤
│ 趋势图 / 空间热力图   │ Agent调查时间线                 │
│ 代表性NG图片          │ ✓ 加载不可变快照                │
│ 基准与当前窗口对比     │ ✓ 检索适用技术手册              │
│ 数据质量提示          │ ✓ 检索已验证历史案例            │
├──────────────────────┴─────────────────────────────────┤
│ 假设1：夹具定位偏移  0.68                              │
│ 支持证据 / 反证 / 缺失证据 / 推荐验证步骤              │
├────────────────────────────────────────────────────────┤
│ [批准] [修改后批准] [要求重新分析] [驳回]              │
└────────────────────────────────────────────────────────┘
```

Trace展示工具调用、证据ID和结构化决策摘要，不展示模型完整思维链。

---

## 21. API设计

### 检测接入

```text
POST /api/v1/inspection-results/batches
GET  /api/v1/inspection-results/{result_id}
```

### Quality Case

```text
GET  /api/v1/cases
GET  /api/v1/cases/{case_id}
GET  /api/v1/cases/{case_id}/snapshot
GET  /api/v1/cases/{case_id}/analysis-runs
POST /api/v1/cases/{case_id}/reanalyze
```

### Proposal与审批

```text
GET  /api/v1/proposals/pending
GET  /api/v1/proposals/{proposal_id}
POST /api/v1/proposals/{proposal_id}/decision
```

### 文档

```text
POST /api/v1/documents
GET  /api/v1/documents
GET  /api/v1/documents/{document_id}
POST /api/v1/documents/{document_id}/supersede
```

### 演示QMS

```text
GET  /mock-qms/tasks
GET  /mock-qms/tasks/{task_id}
POST /mock-qms/tasks/{task_id}/result
POST /api/v1/integrations/qms/task-results
```

### 实时状态

```text
GET /api/v1/cases/{case_id}/events
Content-Type: text/event-stream
```

不提供通用`/agent/chat`和任意`/agent/analyze-range`接口。

---

## 22. 数据库核心表

```text
inspection_results
quality_metrics
quality_cases
quality_case_snapshots
quality_episode_metrics
analysis_runs
agent_trace_steps
knowledge_evidence
investigation_proposals
proposal_decisions
qms_tasks
case_confirmations
documents
document_chunks
outbox_events
processed_events
```

关键约束：

- `inspection_results.result_id`唯一；
- `outbox_events.event_id`唯一；
- `processed_events(consumer_group, event_id)`联合唯一；
- `quality_case_snapshots(case_id, snapshot_version)`联合唯一；
- `analysis_runs.analysis_run_id`唯一；
- 同一个`case_id + snapshot_id + trigger_event_id`只能自动创建一个Analysis Run；
- 所有人工操作记录用户、时间和修改前后值。

---

## 23. Demo场景

### 23.1 主场景：夹具定位偏移

```text
正常生产
→ NG率和右上区域聚集连续越界
→ 创建Quality Case和Snapshot
→ Agent检索夹具手册及已验证案例
→ 提出检查定位销的Proposal
→ 人工批准
→ Mock QMS创建任务
→ 人工确认定位销松动
→ 更换并验证NG率恢复
→ JSON归档和可信案例索引
```

### 23.2 光照漂移

使用公开数据集图片进行亮度、对比度或局部照明变换，形成不依赖企业生产数据的可复现场景。Agent应检索照明维护手册，并建议检查亮度、角度、曝光与校准状态。

### 23.3 证据不足

构造样本数不足、混合模型版本或数据缺失的Snapshot。Agent必须输出`INSUFFICIENT_EVIDENCE`，不能强行选择根因。

---

## 24. 测试与评估

### 24.1 传统软件测试

- Schema校验测试；
- Case去重与合并测试；
- Snapshot不可变性测试；
- Outbox发布恢复测试；
- Redis重复投递幂等测试；
- Worker崩溃后`XAUTOCLAIM`测试；
- QMS Adapter契约测试；
- 文档版本和适用范围过滤测试；
- 未验证Case禁止索引测试；
- 权限与审计测试。

### 24.2 Agent评估

每个场景保存：

```text
输入Snapshot
可用文档
可用历史案例
隐藏的场景真值
期望工具调用
允许的候选假设
必须引用的证据
禁止出现的确定性结论
期望停止原因
```

评价指标：

- 输出Schema通过率；
- 必需工具调用覆盖率；
- 引用有效率；
- 文档适用性判断准确率；
- 历史案例误用率；
- 根因候选Top-K命中率；
- 无证据确定性断言率；
- 证据不足场景正确拒答率；
- Proposal可执行性人工评分；
- 平均工具调用数、时延和成本。

### 24.3 消息可靠性演示

作品集演示中应主动展示一次故障恢复：

1. Worker领取`quality.case.opened.v1`后被终止；
2. 消息停留在Pending列表；
3. Recovery Worker通过`XAUTOCLAIM`接管；
4. Agent重新执行；
5. 幂等约束保证只产生一个有效分析结果；
6. WebUI显示恢复后的状态。

这是项目“事件驱动能力”最有说服力的演示之一。

---

## 25. 安全、权限与审计

- Agent只使用只读领域工具和内部Proposal提交工具；
- 任何QMS写操作必须由人工批准事件触发；
- 文档上传、废止、审批和确认操作需要用户身份；
- 所有事件保留`correlation_id`、`causation_id`和`trace_id`；
- 敏感配置通过环境变量或Secret管理，不写入仓库；
- 图片URI使用短期签名访问，不把对象存储设为公开；
- Agent输入输出进行大小限制和Schema校验；
- 检索到的文档内容视为不可信输入，防止提示注入；
- 工具层不执行文档中的命令；
- 历史Case修订生成新Revision，不覆盖原始审计记录。

---

## 26. 技术栈

| 层 | 推荐选择 |
|---|---|
| Detector Adapter | Python、可替换模型适配器 |
| API | FastAPI、Pydantic |
| ORM与迁移 | SQLAlchemy、Alembic |
| 主数据库 | PostgreSQL |
| 向量检索 | pgvector |
| 消息 | Redis Streams |
| 对象存储 | MinIO / S3兼容接口 |
| Agent | 单Agent、有界ReAct、工具调用；Runtime可替换 |
| 前端 | React或Vue、ECharts |
| 状态推送 | SSE |
| 部署 | Docker Compose、Linux |
| 可观测性 | 结构化日志、OpenTelemetry风格Trace ID、基础指标 |

个人作品集不需要为了技术栈数量引入Kafka、Kubernetes、Flink或多Agent框架。

---

## 27. 推荐仓库结构

```text
quality-case-agent/
├── README.md
├── docker-compose.yml
├── .env.example
├── contracts/
│   ├── events/
│   ├── snapshots/
│   └── agent_outputs/
├── apps/
│   ├── api/
│   ├── web/
│   └── simulator/
├── services/
│   ├── inspection_ingestion/
│   ├── db_writer/
│   ├── metrics_worker/
│   ├── case_detector/
│   ├── outbox_publisher/
│   ├── investigation_agent/
│   ├── qms_integration/
│   └── case_archiver/
├── domain/
│   ├── inspection/
│   ├── quality_case/
│   ├── investigation/
│   └── knowledge/
├── adapters/
│   ├── detectors/
│   ├── vector_store/
│   ├── object_store/
│   ├── llm/
│   └── qms/
├── knowledge_base/
│   ├── manuals/
│   ├── sop/
│   ├── fmea/
│   └── synthetic_cases/
├── scenarios/
│   ├── fixture_offset/
│   ├── illumination_drift/
│   └── insufficient_evidence/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contracts/
│   └── agent_evals/
└── docs/
    ├── architecture.md
    ├── event-contracts.md
    ├── agent-design.md
    ├── evaluation.md
    └── demo-script.md
```

---

## 28. 实施顺序

### Phase 1：业务骨架

- 定义Pydantic/JSON Schema消息契约；
- PostgreSQL表和迁移；
- Redis Streams、Consumer Group、幂等消费；
- Case、Snapshot、Outbox和双状态机。

### Phase 2：可复现数据流

- Detector Adapter；
- 公开数据集Replay；
- 三个合成场景；
- 指标Worker和Case Detector；
- MinIO代表性样本。

### Phase 3：Agent调查

- 受控数据工具；
- 文档上传和pgvector；
- 单Agent有界ReAct；
- Evidence、Analysis和Trace结构化输出；
- Agent Eval。

### Phase 4：人工闭环

- Case WebUI；
- Proposal审批；
- Mock QMS Adapter；
- 人工确认、验证和双写归档；
- 可信历史案例索引。

### Phase 5：作品集打磨

- 故障恢复演示；
- ROI Calculator；
- 架构图和时序图；
- Docker Compose一键启动；
- 3至5分钟演示视频；
- README中的设计权衡、限制和数据真实性声明。

---

## 29. 作品集叙事

### 29.1 简历描述

> 设计并实现事件驱动的工业质量调查Agent：将高频检测结果聚合为不可变Quality Case，通过PostgreSQL Outbox与Redis Streams可靠触发有界ReAct调查流程；Agent使用统计工具和企业知识库形成带证据的排查Proposal，经人工审批后通过QMS Adapter闭环，并将验证完成的案例沉淀为可信经验索引。

### 29.2 面试讲解顺序

1. 为什么不能逐件调用LLM；
2. 检测数据和Quality Case事件如何分离；
3. Snapshot为什么必须不可变；
4. Redis重复消息、Worker崩溃和Outbox一致性如何处理；
5. Agent为什么是有界单Agent而不是多Agent；
6. Agentic RAG如何受文档版本和适用范围约束；
7. 为什么Agent只提Proposal、不直接操作QMS；
8. 如何通过人工验证防止历史记忆污染；
9. 如何评估Agent输出和业务ROI。

### 29.3 最有辨识度的演示

```text
公开数据回放
→ 质量分布出现持续偏移
→ WebUI自动出现Quality Case
→ Agent自主调用统计和知识检索工具
→ 展示证据链和缺失证据
→ 人工修改后批准Proposal
→ Mock QMS收到任务
→ 工程师提交实际原因和验证结果
→ Case JSON归档
→ 下一次相似Case能够检索到已验证经验
```

---

## 30. 数据真实性声明

README中应明确写明：

> 本项目面向工业视觉质量调查场景，但不包含任何企业内部生产数据或保密文档。视觉数据来自公开工业异常检测数据集；产线、批次、工位、设备状态、技术手册、历史案例和QMS记录均为合成数据。检测分数可来自真实模型推理或可复现的离线回放。所有ROI金额均为参数化示例，不代表已在真实工厂验证的收益。

---

## 31. 最终结论

本项目的核心价值不在于使用了某个视觉模型、向量数据库或Agent框架，而在于完整表达了一个可落地的Agent业务模式：

```text
传统系统持续产生事实
→ 普通程序识别值得调查的业务事件
→ Agent围绕冻结证据自主调用工具
→ 输出可审计的判断和行动建议
→ 人工掌握最终授权和根因确认
→ 业务系统执行动作
→ 验证后的结果成为新的组织记忆
```

这使项目能够集中展示Agent开发岗位真正关心的能力：事件驱动、工具编排、上下文构建、可靠消息处理、企业知识接入、人机协作、业务系统集成、评估和知识闭环。
