# 基于 EfficientAD 与 AI Agent 的工业视觉质量检测系统设计文档

## 1. 项目概述

### 1.1 项目名称

**Quality Copilot for Visual Inspection**  
**基于 EfficientAD 与 AI Agent 的工业视觉质量检测与根因分析系统**

### 1.2 项目背景

在制造业视觉质量检测场景中，视觉模型通常承担高速、低延迟的在线检测任务。例如 EfficientAD 可用于工业异常检测，根据输入图像生成 anomaly score、anomaly map，并根据阈值完成 OK / NG 判定。

这类视觉系统擅长回答：

- 当前工件是否异常；
- 异常程度有多高；
- 异常主要出现在哪个区域。

但视觉模型通常不能直接回答：

- 为什么最近 NG 率突然升高；
- 当前异常是否与历史事件相似；
- 应该优先排查哪个设备、工艺或夹具；
- 对应的 SOP、FMEA、设备维护手册中有什么规定；
- 是否需要停线、返修或人工复核；
- 当前班次或当天质量状况如何总结。

因此，本项目在 EfficientAD 实时检测系统之外增加一个 **AI Quality Copilot**，将高速视觉检测、实时数据采集、统计分析、质量事件识别、RAG 知识检索和 Agent 推理结合起来。

系统总体遵循以下原则：

> **视觉模型负责发现异常，数据系统负责识别质量事件，RAG 负责提供企业知识，Agent 负责理解异常并形成分析结论。**

---

## 2. 项目目标

本项目希望构建一个面向工业视觉质检场景的完整 AI 应用系统，展示以下能力：

1. 使用 EfficientAD 完成高吞吐工业异常检测；
2. 将逐件检测结果异步写入数据系统；
3. 通过时间窗口聚合计算 NG Rate、anomaly score 分布等质量指标；
4. 使用规则、统计方法检测质量异常事件；
5. 仅在必要时唤醒 AI Agent，而不是逐件调用大模型；
6. 使用 RAG 检索 SOP、FMEA、8D、维修记录、历史质量案例等非结构化知识；
7. 使用 SQL / API Tool 获取结构化实时数据；
8. 由 Agent 组合实时数据、统计分析、历史案例和规范文档，生成可能原因、排查建议和分析报告；
9. 支持定时班次/日报总结以及异常事件主动分析；
10. 在不接入真实企业产线的情况下，通过公开数据集和生产线回放模拟实现完整可复现 Demo。

---

## 3. 设计原则

### 3.1 LLM / Agent 不进入实时检测关键路径

系统必须保证即使 Agent、RAG 或 LLM 服务出现延迟、异常甚至完全不可用，也不会影响 EfficientAD 的实时检测和生产线 OK / NG 判定。

实时链路：

```text
Camera
  ↓
EfficientAD
  ↓
anomaly score / anomaly map
  ↓
threshold
  ↓
OK / NG
  ↓
PLC / 分拣机构
```

Agent 只存在于旁路分析链路中。

### 3.2 高频数据由传统程序处理，低频高价值事件由 Agent 处理

例如产线每秒检测 30 个工件，则每天可能产生数百万条检测记录。

不应让 Agent 对每条数据进行推理，而应通过普通程序完成：

- 数据落库；
- 时间窗口聚合；
- NG Rate 计算；
- anomaly score 分布；
- P95 / P99；
- 异常区域统计；
- 趋势检测；
- 事件触发。

最终 Agent 可能只分析每天几次真正有价值的 Quality Event。

### 3.3 结构化实时数据和非结构化知识分开处理

结构化数据：

- NG Rate；
- anomaly score；
- 批次；
- 工位；
- 检测数量；
- 时间序列；
- 模型版本；
- 设备状态。

使用：

```text
PostgreSQL / TimescaleDB / API
            ↓
        SQL / Tools
            ↓
           Agent
```

非结构化知识：

- SOP；
- FMEA / PFMEA；
- 8D；
- CAPA；
- 设备维护手册；
- 历史故障案例；
- 质量规范；
- 工程师经验总结。

使用：

```text
Document
   ↓
Parsing / Chunking
   ↓
Embedding
   ↓
Vector DB
   ↓
RAG
   ↓
Agent
```

不应将所有逐件检测数据都 Embedding 后放入向量数据库。

---

## 4. 总体系统架构

```text
                           ┌─────────────────────────┐
                           │        Camera           │
                           └────────────┬────────────┘
                                        │
                                        ▼
                           ┌─────────────────────────┐
                           │ EfficientAD Inference   │
                           │ score / map / OK / NG   │
                           └────────────┬────────────┘
                                        │
                     ┌──────────────────┴──────────────────┐
                     │                                     │
                     ▼                                     ▼
          ┌──────────────────────┐              ┌──────────────────────┐
          │ Real-time Decision   │              │   Detection Event    │
          │ PLC / Sort / Reject  │              │    Message Queue     │
          └──────────────────────┘              └──────────┬───────────┘
                                                          │
                                                          ▼
                                               ┌──────────────────────┐
                                               │       DB Writer       │
                                               │     Batch Insert      │
                                               └──────────┬───────────┘
                                                          │
                         ┌────────────────────────────────┼─────────────────────────────┐
                         │                                │                             │
                         ▼                                ▼                             ▼
                ┌──────────────────┐             ┌──────────────────┐         ┌──────────────────┐
                │   PostgreSQL     │             │  MinIO / S3/NAS  │         │ Metrics Worker   │
                │ inspection data │             │ images / maps    │         │ window aggregate │
                └──────────────────┘             └──────────────────┘         └────────┬─────────┘
                                                                                       │
                                                                                       ▼
                                                                            ┌──────────────────┐
                                                                            │ quality_metrics  │
                                                                            └────────┬─────────┘
                                                                                     │
                                                                                     ▼
                                                                            ┌──────────────────┐
                                                                            │ Event Detector   │
                                                                            └────────┬─────────┘
                                                                                     │
                                                                                Quality Event
                                                                                     │
                                                      ┌──────────────────────────────┴───────────────────────────┐
                                                      │                                                          │
                                                      ▼                                                          ▼
                                             Scheduled Trigger                                          Event Trigger
                                             Shift / Daily Report                                      NG Spike / Drift
                                                      │                                                          │
                                                      └───────────────────────────┬──────────────────────────────┘
                                                                                  ▼
                                                                        ┌────────────────────┐
                                                                        │ Agent Orchestrator │
                                                                        └──────────┬─────────┘
                                                                                   │
                                       ┌───────────────────────────────────────────┼────────────────────────────────────┐
                                       │                                           │                                    │
                                       ▼                                           ▼                                    ▼
                              ┌──────────────────┐                         ┌──────────────────┐                ┌──────────────────┐
                              │ Data Analysis    │                         │ Knowledge RAG    │                │ Historical Case  │
                              │ SQL/Python Tool  │                         │ SOP/FMEA/Manual  │                │ Search Tool      │
                              └────────┬─────────┘                         └────────┬─────────┘                └────────┬─────────┘
                                       │                                           │                                    │
                                       └───────────────────────────────────────────┼────────────────────────────────────┘
                                                                                   ▼
                                                                         ┌──────────────────┐
                                                                         │    RCA Agent     │
                                                                         └────────┬─────────┘
                                                                                  │
                                                                                  ▼
                                                                    Root Cause / Recommendation
                                                                                  │
                                                                                  ▼
                                                                       Quality Analysis Report
```

---

## 5. 实时视觉检测模块

### 5.1 输入

- 工业相机图像；
- Replay Mode 下的公开数据集图像；
- Simulation Mode 下由生产线模拟器按设定速率发送的图像。

### 5.2 EfficientAD 输出

每个工件至少生成：

```json
{
  "inspection_id": "uuid",
  "timestamp": "2026-08-20T10:32:01.123",
  "product_id": "P20260820_001238",
  "product_type": "AX17",
  "batch_id": "LOT_0820_A",
  "line_id": "LINE_01",
  "station_id": "VISION_01",
  "anomaly_score": 0.823,
  "threshold": 0.510,
  "is_ng": true,
  "model_version": "efficientad_v1.0",
  "anomaly_region": "top_left",
  "image_uri": "s3://inspection/...jpg",
  "anomaly_map_uri": "s3://inspection/...png"
}
```

### 5.3 必须保存的模型上下文

建议始终保存：

- `model_version`；
- `threshold`；
- `product_type`；
- `station_id`；
- `timestamp`。

这样可以保证后续模型切换、阈值调整后仍能解释历史判定结果。

---

## 6. 数据存储设计

## 6.1 inspection_result：逐件检测记录

建议使用 PostgreSQL。

核心字段：

```sql
inspection_id      UUID PRIMARY KEY
timestamp          TIMESTAMPTZ
product_id         VARCHAR
product_type       VARCHAR
batch_id           VARCHAR
line_id            VARCHAR
station_id         VARCHAR
anomaly_score      FLOAT
threshold          FLOAT
is_ng              BOOLEAN
anomaly_region     VARCHAR
model_version      VARCHAR
image_uri          TEXT
anomaly_map_uri    TEXT
created_at         TIMESTAMPTZ
```

索引建议：

```sql
(timestamp)
(line_id, timestamp)
(station_id, timestamp)
(batch_id)
(is_ng, timestamp)
(product_type, timestamp)
```

## 6.2 图像与 anomaly map

不要把大图、Float32 anomaly map 直接存进 PostgreSQL。

推荐：

```text
MinIO / S3 / NAS
```

数据库只保存 URI。

存储策略：

### OK 工件

- 默认不保存原图；
- 或按 1/1000、1/10000 等比例抽样；
- 可用于后续模型漂移分析。

### NG 工件

保存：

- 原始图像；
- anomaly heatmap；
- 必要的裁剪区域；
- metadata。

### 重复 NG

如果短时间出现大量重复异常，可以只保留：

- Top-K anomaly score 样本；
- 代表性空间区域样本；
- 随机少量样本。

避免数千张几乎相同图像占用大量存储。

---

## 7. 异步写入与消息队列

实时推理线程不应直接同步写数据库。

错误做法：

```text
EfficientAD
  ↓
postgres.insert()
  ↓
下一张图像
```

数据库一旦延迟，就会拖慢推理。

正确设计：

```text
EfficientAD
   ↓
Redis Stream / Kafka
   ↓
DB Writer Consumer
   ↓
100~500 条 Batch Insert
   ↓
PostgreSQL
```

### 作品集推荐

优先使用：

```text
Redis Streams
```

原因：

- 实现成本较低；
- 足够展示异步解耦；
- 支持 Consumer Group；
- 非常适合个人作品集。

如果后续想展示更完整的数据基础设施能力，再切换 Kafka。

---

## 8. quality_metrics：时间窗口聚合

Agent 不应扫描几十万条逐件记录。

Metrics Worker 应持续生成时间窗口指标，例如：

- 1 min；
- 5 min；
- 30 min；
- 1 h。

表结构示例：

```sql
metric_id           UUID PRIMARY KEY
window_start        TIMESTAMPTZ
window_end          TIMESTAMPTZ
line_id             VARCHAR
station_id          VARCHAR
product_type        VARCHAR
batch_id            VARCHAR
model_version       VARCHAR

total_count         INTEGER
ng_count            INTEGER
ng_rate             FLOAT
score_mean          FLOAT
score_std           FLOAT
score_p50           FLOAT
score_p95           FLOAT
score_p99           FLOAT

top_left_ratio      FLOAT
center_ratio        FLOAT
bottom_right_ratio  FLOAT

created_at          TIMESTAMPTZ
```

示例：

```text
10:31-10:32
Total     1812
NG        12
NG Rate   0.66%
Mean      0.19
P95       0.41

10:32-10:33
Total     1794
NG        71
NG Rate   3.96%
Mean      0.35
P95       0.83
```

---

## 9. Event Detector：质量事件检测

系统真正决定是否唤醒 Agent 的模块不是 LLM，而是 **Event Detector**。

它可以基于规则、统计方法和传统机器学习实现。

## 9.1 固定阈值

例如：

```text
NG Rate > 3%
```

或：

```text
连续 NG > 10 件
```

或：

```text
1 min 内 NG > 50
```

适合简单明确的质量规则。

## 9.2 动态基线

相比固定阈值，更推荐基于历史 baseline：

```text
current_ng_rate > rolling_mean + 3 * rolling_std
```

可选算法：

- Z-score；
- EWMA；
- CUSUM；
- Change Point Detection；
- Rolling Baseline。

## 9.3 anomaly score drift

EfficientAD 的优势之一是可以监控 anomaly score，而不仅仅是 OK / NG。

示例：

```text
P95 anomaly score
0.32
0.37
0.42
0.51
0.63
```

即使 NG Rate 尚未明显升高，也可能代表产品分布正在偏离训练时的正常分布。

可生成：

```text
ANOMALY_SCORE_DRIFT
```

事件。

## 9.4 空间聚集

从 anomaly map 提取异常区域后，可以统计：

```text
top_left     74%
center       11%
bottom_right  8%
other         7%
```

当异常高度集中在同一区域时，生成：

```text
SPATIAL_CLUSTER
```

该类事件可能对应：

- 夹具定位问题；
- 相机位置偏移；
- 固定工艺因素；
- 局部污染；
- 光照异常。

## 9.5 多指标 Event Score

为了降低误报警，可以将多个信号组合：

```text
NG Rate 异常          +2
P95 score 异常        +1
空间聚集              +2
连续多窗口异常        +1
批次同步异常          +1
设备参数异常          +2
```

当：

```text
event_score >= 4
```

才创建 Quality Event。

## 9.6 Cooldown 与 Hysteresis

为了防止重复触发：

### Cooldown

同一个事件触发一次 Agent 后，10 分钟内不重复分析。

### Hysteresis

例如：

```text
触发：NG Rate > 3%
恢复：NG Rate < 2% 且持续 5 分钟
```

避免阈值附近反复触发。

---

## 10. quality_event：事件存储

示例：

```json
{
  "event_id": "QE-20260820-00125",
  "event_type": "NG_RATE_SPIKE",
  "severity": "HIGH",
  "line_id": "LINE_03",
  "station_id": "VISION_02",
  "product_type": "AX17",
  "batch_id": "LOT_0820_A",
  "start_time": "2026-08-20T10:32:00",
  "end_time": "2026-08-20T10:35:00",
  "total_count": 5409,
  "ng_count": 238,
  "ng_rate": 0.044,
  "baseline_ng_rate": 0.006,
  "avg_anomaly_score": 0.38,
  "p95_anomaly_score": 0.87,
  "dominant_region": "top_left",
  "dominant_region_ratio": 0.72,
  "status": "OPEN"
}
```

Quality Event 是 Agent 的主要输入对象。

---

## 11. Agent 触发机制

系统推荐采用三种入口。

## 11.1 Event-driven Trigger

当 Event Detector 发现：

- `NG_RATE_SPIKE`；
- `ANOMALY_SCORE_DRIFT`；
- `SPATIAL_CLUSTER`；
- `CONSECUTIVE_NG`；
- `BATCH_ANOMALY`；
- `MODEL_DRIFT_WARNING`。

立即启动一次 Agent 分析流程。

## 11.2 Scheduled Trigger

Agent 不需要永久运行。

由 Scheduler 定时启动短生命周期任务：

- 每班一次；
- 每 8 小时一次；
- 每日一次。

用于生成：

- Shift Quality Report；
- Daily Quality Report。

不推荐每 30 分钟强制生成一篇长报告，否则一天会产生大量低价值报告。

## 11.3 Human Trigger

Dashboard 中提供：

```text
Analyze with AI
```

质量工程师可针对当前：

- Line；
- Station；
- Batch；
- Time Range；
- Event。

主动请求 Agent 分析。

---

## 12. Agent 设计

建议不要做一个“什么都能干”的超级 Agent，而是拆成专用 Skill / Agent。

## 12.1 Quality Data Analysis Skill

负责调用 SQL / Python 完成：

```text
get_quality_metrics()
get_ng_rate()
get_score_distribution()
get_baseline_metrics()
detect_score_drift()
get_spatial_distribution()
get_batch_comparison()
```

统计计算应由 Python / SQL 完成，而不是让 LLM 自己计算大量数字。

## 12.2 Knowledge Agent

负责 RAG：

```text
search_sop()
search_fmea()
search_manual()
search_quality_standard()
```

## 12.3 Historical Case Agent

负责查询：

- 历史 Quality Event；
- 历史 RCA；
- 8D；
- CAPA；
- 相似异常模式。

可以采用：

```text
Metadata Filtering
+
Vector Similarity Search
```

## 12.4 RCA Agent

最终推理 Agent。

输入：

```text
Data Analysis Result
+
Knowledge Retrieval Result
+
Historical Similar Cases
+
Representative NG Samples
```

输出：

- 事件摘要；
- 可能原因；
- 证据；
- 置信度；
- 推荐排查顺序；
- 建议处理措施；
- 是否需要人工升级；
- 引用的 SOP / FMEA / 8D 条目。

---

## 13. RAG 知识库设计

建议构造一个虚拟工厂知识库。

目录：

```text
knowledge_base/

├── sop/
│   ├── visual_inspection.md
│   ├── ng_handling.md
│   └── line_stop_policy.md
│
├── fmea/
│   └── AX17_fmea.md
│
├── quality_standard/
│   └── AX17_quality_standard.md
│
├── maintenance/
│   ├── camera_maintenance.md
│   ├── fixture_maintenance.md
│   └── illumination_maintenance.md
│
├── cases/
│   ├── Q20260115.md
│   ├── Q20260321.md
│   ├── Q20260517.md
│   └── Q20260703.md
│
└── 8d/
    ├── 8D_Q20260517.md
    └── 8D_Q20260703.md
```

示例历史案例：

```text
Case: Q20260517

Product:
AX-17

Station:
VISION-01

Symptom:
NG rate increased from 0.7% to 5.4%.
Abnormal regions were concentrated in upper-left area.

Root Cause:
Fixture positioning deviation caused repeated surface contact.

Corrective Action:
1. Replace fixture
2. Recalibrate positioning system
3. Inspect next 500 units

Result:
NG rate returned to 0.6%.
```

---

## 14. RAG 检索流程

Quality Event：

```text
Product = AX17
Station = VISION01
NG Rate = 4.7%
Dominant Region = top_left
Score P95 = 0.83
```

Agent 形成检索 Query：

```text
AX17 VISION01 upper-left anomaly
NG rate spike
fixture positioning
surface abnormality
```

RAG 返回：

1. FMEA 中与左上区域异常相关的 Failure Mode；
2. 历史相似案例；
3. SOP 中对应的检查步骤；
4. 设备维护手册中的检查说明。

最终由 RCA Agent 综合。

---

## 15. Agent 报告输出示例

```markdown
# Quality Event Analysis

Event ID: QE-20260820-00125
Line: LINE-03
Station: VISION-02
Product: AX17

## Summary

During 10:32-10:35, NG rate increased from a historical baseline of 0.6% to 4.4%.
P95 anomaly score increased from 0.42 to 0.87.
72% of NG samples were concentrated in the upper-left region.

## Possible Causes

### 1. Fixture positioning deviation
Confidence: High

Evidence:
- abnormality strongly clustered in upper-left region;
- FMEA-AX17 §4.3 lists fixture offset as a possible cause;
- historical case Q20260517 showed a similar spatial pattern.

### 2. Illumination instability
Confidence: Medium

Evidence:
- maintenance manual states uneven illumination may increase anomaly scores;
- current evidence is insufficient to confirm the cause.

## Recommended Actions

1. Check fixture offset and positioning accuracy;
2. Verify illumination intensity and angle;
3. Inspect 100 representative NG samples;
4. If NG rate remains above 3%, escalate to quality engineer.

## References

- FMEA-AX17 §4.3
- SOP-NG-Handling §2
- Historical Case Q20260517
```

注意：Agent 应输出“可能原因”，而不是无证据地直接宣称某个因素就是根因。

---

## 16. 低置信度与人工升级机制

RAG 不一定总能找到足够好的证据。

例如：

```text
Top similarity = 0.31
```

系统不应强行回答。

建议：

```text
当前知识库未检索到足够相似的历史案例，无法可靠判断根因。
建议升级至质量工程师人工分析，并将该事件保存为新的案例候选。
```

这可以降低幻觉风险，并形成后续知识闭环。

---

## 17. Dashboard 设计

Dashboard 不需要依赖 LLM 即可展示实时指标。

推荐展示：

### 当前状态

- Current NG Rate；
- Current Throughput；
- Mean Anomaly Score；
- P95 / P99；
- 当前模型版本；
- 当前批次。

### Trend

- NG Rate 时间序列；
- anomaly score 时间序列；
- P95 / P99 trend；
- Batch comparison。

### Spatial Analysis

- anomaly map representative samples；
- 区域异常分布；
- Top-K NG images。

### Quality Events

- OPEN；
- INVESTIGATING；
- RESOLVED。

### AI Copilot

支持：

```text
Analyze with AI
```

并自动携带当前 Dashboard 上下文：

```json
{
  "line_id": "LINE02",
  "station_id": "VISION03",
  "start_time": "14:25",
  "end_time": "14:40",
  "event_id": "QE-381"
}
```

用户可以直接问：

```text
为什么这个时间段 NG 率升高？
```

---

## 18. 公开数据与生产线模拟方案

由于该项目属于个人作品集，不需要也不应未经许可获取企业真实生产数据。

可以采用：

- MVTec AD；
- MVTec AD 2；
- VisA；
- 其他公开工业异常检测数据集。

## 18.1 Replay Mode

使用公开图像，固定 seed，保证复现。

```text
Dataset
  ↓
Replay
  ↓
EfficientAD
  ↓
Inspection Events
```

## 18.2 Simulation Mode

构造 ProductionLineSimulator：

```text
Public Dataset
      ↓
ProductionLineSimulator
      ↓
30 pcs/s
      ↓
EfficientAD
```

模拟 metadata：

```text
product_id
batch_id
line_id
station_id
timestamp
```

但 anomaly score 必须来自 EfficientAD 真实推理。

## 18.3 场景注入

支持：

```bash
python simulate.py --scenario normal
python simulate.py --scenario ng_spike
python simulate.py --scenario score_drift
python simulate.py --scenario spatial_cluster
python simulate.py --scenario intermittent_failure
```

### normal

正常 NG Rate。

### ng_spike

突然增加异常样本比例：

```text
0.6% → 5.8%
```

### score_drift

逐步提高高 anomaly score 样本比例。

### spatial_cluster

注入大量同区域异常。

### intermittent_failure

间歇性产生异常事件。

---

## 19. 压力测试方案

模型推理和数据系统压力测试可以分开。

先离线运行 EfficientAD：

```text
image_001 -> score 0.21
image_002 -> score 0.17
image_003 -> score 0.83
```

保存：

```text
inference_results.parquet
```

压力测试时直接 Replay：

```text
Parquet
  ↓
100 / 500 / 1000 events/s
  ↓
Redis Streams
  ↓
Consumer
  ↓
PostgreSQL
```

这样不需要 GPU 重复推理即可测试消息和数据库吞吐能力。

---

## 20. API 设计

### Inspection

```text
POST /api/v1/inspection
GET  /api/v1/inspection/{inspection_id}
GET  /api/v1/inspection/recent
```

### Metrics

```text
GET /api/v1/metrics
GET /api/v1/metrics/ng-rate
GET /api/v1/metrics/anomaly-score
```

### Events

```text
GET  /api/v1/events
GET  /api/v1/events/{event_id}
POST /api/v1/events/{event_id}/analyze
```

### Agent

```text
POST /api/v1/agent/chat
POST /api/v1/agent/analyze-event
POST /api/v1/agent/daily-report
```

### Knowledge

```text
POST /api/v1/knowledge/search
POST /api/v1/knowledge/index
```

---

## 21. 推荐技术栈

### Vision

- Python；
- PyTorch；
- EfficientAD；
- OpenCV。

### Inference Optimization

可选：

- ONNX Runtime；
- TensorRT。

### Backend

- FastAPI；
- Pydantic；
- SQLAlchemy；
- Alembic。

### Streaming

第一版：

- Redis Streams。

高级版本：

- Kafka。

### Database

- PostgreSQL；
- 可选 TimescaleDB Extension。

### Object Storage

- MinIO。

### RAG

推荐简单起步：

- pgvector。

高级版本：

- Milvus / Qdrant / OpenSearch Vector Search。

### Agent

可选：

- LangGraph；
- 自己实现 Tool Calling Orchestrator；
- OpenAI Function Calling 风格 Tool Schema。

### Dashboard

可选：

- React + ECharts；
- Vue + ECharts；
- Streamlit（快速 Demo）；
- Grafana（纯指标展示）。

### Deployment

- Docker Compose；
- Linux。

作品集阶段不建议为了展示技术栈而过度引入 Kubernetes、Flink 等重型组件。

---

## 22. Docker Compose 建议服务

```text
services:

  inference-service
  redis
  db-writer
  postgres
  minio
  metrics-worker
  event-detector
  rag-service
  agent-service
  backend-api
  dashboard
```

---

## 23. 项目运行模式

### Mode A：Full Demo

```text
Dataset
↓
Simulator
↓
EfficientAD
↓
Redis
↓
PostgreSQL
↓
Metrics
↓
Event Detector
↓
Agent + RAG
↓
Dashboard
```

### Mode B：Fast Replay

跳过 EfficientAD：

```text
Parquet
↓
Redis
↓
Backend Pipeline
```

用于性能测试。

### Mode C：AI Analysis Only

直接加载一个已有 Quality Event：

```text
quality_event.json
↓
Agent
↓
RAG
↓
Report
```

用于面试现场快速演示 Agent。

---

## 24. MVP 实现范围

建议不要一次实现所有功能。

### Phase 1：Vision + Data Pipeline

完成：

- EfficientAD 推理；
- 数据集 Replay；
- Redis Streams；
- PostgreSQL；
- batch insert；
- MinIO；
- 基础 Dashboard。

### Phase 2：Metrics + Event

完成：

- 1min / 5min aggregation；
- NG Rate；
- P95 score；
- NG spike detection；
- score drift detection；
- quality_event。

### Phase 3：RAG

完成：

- SOP；
- FMEA；
- 8D；
- 历史案例；
- pgvector；
- citation。

### Phase 4：Agent

完成：

- SQL Tool；
- RAG Tool；
- Historical Case Tool；
- RCA Agent；
- Event-triggered Analysis。

### Phase 5：Portfolio Polish

完成：

- Dashboard；
- Daily Report；
- Docker Compose；
- README；
- Architecture Diagram；
- Demo Video；
- Performance Benchmark。

---

## 25. 项目最重要的工程亮点

作品集应重点突出以下内容，而不只是“用了 Agent”。

### 25.1 高吞吐检测与 LLM 解耦

Agent 不进入实时 critical path。

### 25.2 异步数据架构

```text
Inference → Queue → DB Writer
```

而不是同步写数据库。

### 25.3 Event-driven Agent

不是每条数据调用 LLM，而是：

```text
2,000,000 inspections
        ↓
1,440 metric windows
        ↓
12 candidate events
        ↓
3 quality events
        ↓
3 Agent analyses
```

### 25.4 RAG 与 SQL Tool 分离

```text
实时生产数据 → SQL
企业知识 → RAG
```

### 25.5 EfficientAD score drift

不仅检测 NG Rate，还使用 anomaly score trend 进行早期预警。

### 25.6 Spatial Pattern Analysis

利用 anomaly map 的空间统计识别局部聚集异常。

### 25.7 可解释 RCA

每个可能原因必须附带：

- 数据证据；
- RAG 证据；
- 历史案例；
- 置信度。

### 25.8 低置信度升级人工

Agent 不能强制给出根因。

---

## 26. 与 Siemens Production Copilot 思路的对应关系

本项目可以参考工业 Production Copilot 的设计思想，但针对视觉质量检测进行领域化缩减。

| Production Copilot 概念 | 本项目映射 |
|---|---|
| Asset | 视觉检测工位 |
| Time Series | anomaly score / NG Rate |
| Event | Quality Event |
| Case | 历史质量异常 / 8D |
| Knowledge Base | SOP / FMEA / Manual |
| Data Exploration | PostgreSQL / SQL Tool |
| Data Analysis | Quality Analysis Skill |
| Copilot Skill | Python / FastAPI Tool |
| Root Cause Assistance | Quality RCA Agent |
| Production Copilot | Quality Copilot |

本项目自己的扩展包括：

- EfficientAD 实时异常检测；
- anomaly map 空间分析；
- Event Detector 自动唤醒 Agent；
- 针对质量分析的 RAG；
- 针对视觉质检的数据回放系统。

---

## 27. README 中的数据真实性说明

建议在 GitHub README 中明确写：

> This project is inspired by industrial visual inspection scenarios encountered during manufacturing practice. Due to production data confidentiality, no proprietary company data is included. Public anomaly-detection datasets are replayed through a simulated production-line environment. Production metadata, historical incidents and quality documents are synthetic. EfficientAD anomaly scores are produced by actual model inference.

中文：

> 本项目受到真实制造业视觉质检场景启发。由于生产数据和企业文档涉及保密要求，项目不包含任何企业内部数据。视觉数据来自公开工业异常检测数据集，生产线 metadata、历史质量事件和质量规范文档均为模拟数据；EfficientAD anomaly score 由模型真实推理产生。

---

## 28. 面试中的项目定位

推荐描述：

> 我做的不是一个简单的“EfficientAD + RAG”拼接 Demo，而是尝试把工业视觉的高速实时检测与大模型的低频复杂分析进行解耦。EfficientAD 负责逐件检测，Redis 和 PostgreSQL 负责检测数据流，Metrics Worker 负责窗口统计，Event Detector 基于 NG Rate、anomaly score drift 和空间聚集判断是否产生质量事件。只有产生事件后才启动 Agent。Agent 使用 SQL Tool 获取实时结构化数据，通过 RAG 检索 SOP、FMEA、8D 和历史案例，再生成带证据的可能根因和排查建议。

### 一句话版本

> **EfficientAD 负责发现异常，Event Detector 负责发现问题模式，RAG 提供制造知识，Agent 负责理解问题。**

---

## 29. 最终项目价值

该项目可以同时展示以下能力：

### 计算机视觉

- EfficientAD；
- anomaly detection；
- anomaly map；
- inference pipeline。

### 数据工程

- Streaming；
- Batch insert；
- Time-window aggregation；
- Time-series metrics。

### 后端工程

- FastAPI；
- PostgreSQL；
- Redis；
- MinIO；
- Docker。

### Agent

- Tool Calling；
- Agent orchestration；
- Event-driven agent；
- Scheduled agent task。

### RAG

- 企业知识库；
- FMEA / SOP / 8D；
- Vector Search；
- Evidence Citation。

### 工业 AI 系统设计

- 实时与非实时链路隔离；
- 故障降级；
- 质量事件检测；
- Root Cause Analysis；
- Human-in-the-loop。

因此，它非常适合作为一个同时连接以下职业方向的个人旗舰项目：

- 工业视觉算法工程师；
- AI 应用工程师；
- Agent 工程师；
- 机器学习应用工程师 / MLE；
- 智能制造 AI 工程师；
- 多模态 / 工业智能体方向。

---

## 30. 推荐的最终仓库结构

```text
quality-copilot/

├── README.md
├── docker-compose.yml
├── .env.example
│
├── inference/
│   ├── efficientad/
│   ├── service.py
│   └── schemas.py
│
├── simulator/
│   ├── production_line.py
│   ├── scenarios/
│   │   ├── normal.py
│   │   ├── ng_spike.py
│   │   ├── score_drift.py
│   │   └── spatial_cluster.py
│   └── replay.py
│
├── backend/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── db/
│
├── workers/
│   ├── db_writer.py
│   ├── metrics_worker.py
│   └── event_detector.py
│
├── agent/
│   ├── orchestrator.py
│   ├── rca_agent.py
│   ├── tools/
│   │   ├── quality_data.py
│   │   ├── knowledge.py
│   │   └── historical_case.py
│   └── prompts/
│
├── rag/
│   ├── ingest.py
│   ├── retriever.py
│   └── vectorstore.py
│
├── knowledge_base/
│   ├── sop/
│   ├── fmea/
│   ├── quality_standard/
│   ├── maintenance/
│   ├── cases/
│   └── 8d/
│
├── dashboard/
│
├── tests/
│
└── docs/
    ├── architecture.md
    ├── database.md
    ├── agent-design.md
    └── demo.md
```

---

## 31. 结论

该系统不尝试使用 Agent 替代实时工业视觉算法，而是将 Agent 放在最适合它的位置：

```text
实时感知
EfficientAD
    ↓
数据理解
Metrics / Event Detector
    ↓
知识理解
RAG
    ↓
复杂推理
AI Agent
    ↓
工程决策支持
Quality Report / RCA / Recommendation
```

完整设计目标可以概括为：

> **构建一个以 EfficientAD 为实时感知核心、以事件驱动数据分析为中间层、以 RAG 与 AI Agent 为质量认知和决策支持层的工业视觉 Quality Copilot。**

