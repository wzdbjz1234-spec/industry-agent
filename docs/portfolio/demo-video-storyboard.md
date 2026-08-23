# 3–5 分钟演示视频分镜

仓库当前交付的是可复现的演示脚本、Runbook 和本分镜，不包含预录制 MP4。按以下时间线录屏即可得到与验收一致的演示，不需要真实企业数据或在线模型。

| 时间 | 画面与操作 | 要说明的验收点 |
| --- | --- | --- |
| 0:00–0:30 | 打开 WebUI，展示三类 Case、Trace 和当前状态 | 统一 Case/Snapshot/Trace 入口 |
| 0:30–1:20 | 点击 Fixture Offset Demo，查看调查结论、A/B/C 证据 | Agent 只围绕冻结 Snapshot 调查 |
| 1:20–1:55 | 打开 Proposal，执行 Approve，查看 QMS 外部任务 | 高风险动作必须人工授权，投递幂等 |
| 1:55–2:30 | 打开光照漂移 Demo，展示 `DATA_QUALITY_BLOCKED` | 数据质量分支优先于业务假设 |
| 2:30–3:00 | 打开 Operations，展示时间线、Worker/Delivery、DLQ retry | 可观测性、故障恢复和操作者审计 |
| 3:00–3:40 | 打开 Evaluation，运行两套配置并查看通过率/工具调用/延迟 | Eval 是 Measured，避免把 ROI 当实测收益 |
| 3:40–4:10 | 输入日均 Case 数与人工分钟数，展示 Illustrative ROI | ROI 明确标注假设和免责声明 |
| 4:10–4:40 | 展示 README、架构图和 known limitations | 离线适配器、数据边界、下一步基础设施 |

## 可复现命令

```powershell
uv run python scripts/run_fast_demo.py
uv run python scripts/run_phase10_demo.py
uv run python scripts/run_phase11_demo.py
uv run python scripts/run_phase12_demo.py
uv run python scripts/run_phase13_eval.py
```
