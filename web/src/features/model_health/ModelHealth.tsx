import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert, SlidersHorizontal } from "lucide-react";
import { api, type MonitoringDecision, type MonitoringReport } from "../../api/client";

const STATUS_LABEL: Record<MonitoringDecision["status"], string> = {
  NORMAL: "正常",
  PROCESS_SHIFT: "工艺变化",
  MODEL_DRIFT: "模型 / 输入漂移",
  DATA_QUALITY_BLOCK: "数据质量阻断",
  BASELINE_MISSING: "缺少基线",
};

export default function ModelHealth() {
  const [report, setReport] = useState<MonitoringReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("尚未加载监控报告");

  const refresh = async () => {
    setLoading(true);
    try {
      setReport(await api.monitoringHealth());
      setMessage("已同步最近监控窗口");
    } catch (error) {
      setMessage(`监控同步失败：${String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const establishBaseline = async () => {
    try {
      await api.buildMonitoringBaseline();
      await refresh();
      setMessage("基线已更新，后续窗口将按模型版本评估");
    } catch (error) {
      setMessage(`基线更新失败：${String(error)}`);
    }
  };

  useEffect(() => void refresh(), []);

  const decisions = report?.decisions ?? [];
  const blocked = decisions.filter((decision) => decision.status === "DATA_QUALITY_BLOCK").length;
  const shifts = decisions.filter((decision) => decision.status === "PROCESS_SHIFT").length;
  const drifts = decisions.filter((decision) => decision.status === "MODEL_DRIFT").length;

  return <section>
    <div className="dashboard-intro">
      <div><h2>模型健康度</h2><p>按产品、工位和模型版本区分工艺变化、模型漂移与数据质量问题。</p></div>
      <div className="intro-actions"><button className="secondary-button" onClick={establishBaseline}><SlidersHorizontal size={16} />建立基线</button><button className="primary-button" onClick={refresh} disabled={loading}><RefreshCw className={loading ? "spin" : ""} size={16} />刷新监控</button></div>
    </div>
    <p className="subtle-copy">{message} · {report ? `评估 ${new Date(report.evaluated_at).toLocaleString("zh-CN")}` : ""}</p>
    <div className="ops-kpis"><article className="surface"><span><CheckCircle2 size={16} />监控窗口</span><strong>{report?.window_count ?? "—"}</strong><small>{report?.baseline_count ?? 0} 个有效基线</small></article><article className="surface"><span><AlertTriangle size={16} />工艺变化</span><strong>{shifts}</strong><small>触发 Case 或合并候选</small></article><article className="surface"><span><ShieldAlert size={16} />数据质量阻断</span><strong>{blocked}</strong><small>{drifts} 个模型 / 输入漂移</small></article></div>
    <div className="surface data-surface"><div className="filter-row"><strong>最近监控决策</strong><span className="subtle-text">EWMA · CUSUM · PSI · KS</span></div><div className="stack-list">{decisions.length === 0 ? <div className="empty-state"><ShieldAlert size={20} /><strong>暂无监控窗口</strong><p>先运行演示或写入 Inspection 数据，再建立基线。</p></div> : decisions.map((decision) => <article className="stack-row" key={decision.decision_id}><span className={`row-icon ${decision.severity === "CRITICAL" ? "danger" : ""}`}>{decision.status === "NORMAL" ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}</span><div><span className="pill">{STATUS_LABEL[decision.status]}</span><h3>{decision.dimension_key[2]} · {decision.dimension_key[3]}</h3><p>{decision.model_version} · {new Date(decision.window_start).toLocaleString("zh-CN")}</p></div><div className="row-meta"><strong>{decision.action}</strong><span>{decision.signals.map((signal) => `${signal.signal_type} ${signal.statistic.toFixed(2)}`).join(" · ") || "无超阈值信号"}</span></div></article>)}</div></div>
  </section>;
}
