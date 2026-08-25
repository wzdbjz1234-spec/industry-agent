import { useEffect, useRef, useState } from "react";
import {
  Activity, AlertTriangle, ArrowRight, ArrowUpRight, Bell, Bot, Boxes, Check,
  CheckCircle2, ChevronDown, ChevronRight, CircleDot, ClipboardCheck, Clock3,
  Database, FileSearch, Gauge, ImagePlus, Layers3, LayoutDashboard, Menu, Network,
  PanelLeftClose, Play, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal,
  Sparkles, SquareStack, TimerReset, TriangleAlert, Workflow, X, Zap,
} from "lucide-react";
import {
  api, type AgentTraceEvent, type AnalysisOutput, type AnalysisRun,
  type DeliveryRecord, type EvaluationReport, type Proposal, type QmsTask,
  type QualityCase, type VerifiedCase, type VisionEvent, type VisionStatus,
  type WorkerStatus,
} from "./api/client";
import ModelHealth from "./features/model_health/ModelHealth";

type Tab = "monitor" | "events" | "cases" | "approval" | "qms" | "library" | "operations" | "evaluation" | "documents" | "model-health";
type DemoStage = 0 | 1 | 2 | 3 | 4 | 5;

const NAV_GROUPS: Array<{ title: string; items: Array<{ id: Tab; label: string; icon: typeof Activity; count?: string }> }> = [
  { title: "生产监控", items: [
    { id: "monitor", label: "实时监控", icon: LayoutDashboard },
    { id: "events", label: "异常事件", icon: AlertTriangle, count: "3" },
    { id: "cases", label: "质量 Case", icon: SquareStack },
  ] },
  { title: "Agent 调研", items: [
    { id: "approval", label: "待人工决策", icon: ClipboardCheck },
    { id: "qms", label: "QMS 任务", icon: Workflow },
    { id: "library", label: "验证案例库", icon: Database },
  ] },
  { title: "系统管理", items: [
    { id: "model-health", label: "模型健康度", icon: ShieldCheck },
    { id: "operations", label: "系统运行", icon: Activity },
    { id: "evaluation", label: "模型评估", icon: Gauge },
    { id: "documents", label: "知识文档", icon: FileSearch },
  ] },
];

const FALLBACK_TRACE: AgentTraceEvent[] = [
  { sequence: 1, event_type: "STARTED", iteration: 0, action: "capture_snapshot", arguments: {}, summary: "冻结异常窗口、模型版本和工位上下文，创建不可变 Snapshot", duration_ms: 84, evidence_ids: ["A-021"] },
  { sequence: 2, event_type: "TOOL_CALL", iteration: 1, action: "inspect_metrics", arguments: {}, summary: "读取近 5 分钟检测指标，确认 NG 率由 1.2% 升至 8.7%", duration_ms: 126, evidence_ids: ["A-022"] },
  { sequence: 3, event_type: "TOOL_CALL", iteration: 2, action: "compare_samples", arguments: {}, summary: "比对 24 张代表性样本，异常集中于对象右上区域", duration_ms: 341, evidence_ids: ["A-023"] },
  { sequence: 4, event_type: "TOOL_CALL", iteration: 3, action: "search_knowledge_base", arguments: {}, summary: "检索 SOP 与历史案例，命中定位销偏移检查项", duration_ms: 208, evidence_ids: ["B-014", "C-008"] },
  { sequence: 5, event_type: "FINAL", iteration: 4, action: "draft_proposal", arguments: {}, summary: "形成可证伪假设并生成 3 步排查建议，等待人工审批", duration_ms: 117, evidence_ids: ["A-022", "B-014"] },
];

type EventItem = { id: string; time: string; station: string; object: string; kind: string; score: number; severity: "critical" | "high" | "medium"; state: string };

const EVENT_ITEMS: EventItem[] = [
  { id: "EVT-0823-041", time: "14:32:18", station: "CAM-01", object: "MVTec AD / Hazelnut", kind: "表面裂纹", score: 0.91, severity: "critical", state: "调研完成" },
  { id: "EVT-0823-040", time: "14:31:52", station: "CAM-01", object: "MVTec AD / Hazelnut", kind: "结构异常", score: 0.87, severity: "high", state: "Agent 调研中" },
  { id: "EVT-0823-039", time: "14:29:08", station: "CAM-02", object: "VisA / PCB", kind: "焊点缺失", score: 0.78, severity: "medium", state: "待处理" },
  { id: "EVT-0823-038", time: "14:21:43", station: "CAM-03", object: "BTAD / Gear", kind: "边缘缺损", score: 0.72, severity: "medium", state: "已归档" },
];

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export default function App() {
  const [tab, setTab] = useState<Tab>("monitor");
  const [mobileNav, setMobileNav] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [cases, setCases] = useState<QualityCase[]>([]);
  const [qmsTasks, setQmsTasks] = useState<QmsTask[]>([]);
  const [library, setLibrary] = useState<VerifiedCase[]>([]);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [delivery, setDelivery] = useState<{ pending: DeliveryRecord[]; processed: DeliveryRecord[]; dlq: DeliveryRecord[] }>({ pending: [], processed: [], dlq: [] });
  const [evaluationReports, setEvaluationReports] = useState<EvaluationReport[]>([]);
  const [visionEvents, setVisionEvents] = useState<VisionEvent[]>([]);
  const [visionStatus, setVisionStatus] = useState<VisionStatus | null>(null);
  const [analysisOutput, setAnalysisOutput] = useState<AnalysisOutput | null>(null);
  const [connection, setConnection] = useState<"connected" | "offline" | "loading">("loading");
  const [message, setMessage] = useState("正在连接边缘检测服务…");
  const [model, setModel] = useState("EfficientAD · MVTEC pretrained");
  const [target, setTarget] = useState("MVTec AD · Hazelnut");
  const [demoStage, setDemoStage] = useState<DemoStage>(0);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const refresh = async () => {
    try {
      const [nextProposals, nextRuns, nextCases, nextQmsTasks, nextLibrary, nextWorkers, nextDelivery, nextEvaluationReports, nextVisionEvents, nextVisionStatus] = await Promise.all([
        api.pending(), api.runs(), api.cases(), api.qmsTasks(), api.caseLibrary(), api.workers(), api.delivery(), api.evaluationReports(), api.visionEvents(), api.visionStatus(),
      ]);
      setProposals(nextProposals); setRuns(nextRuns); setCases(nextCases);
      setQmsTasks(nextQmsTasks.items); setLibrary(nextLibrary); setWorkers(nextWorkers.workers);
      setDelivery({ pending: nextDelivery.pending, processed: nextDelivery.processed, dlq: nextDelivery.dlq });
      setEvaluationReports(nextEvaluationReports); setVisionEvents(nextVisionEvents); setVisionStatus(nextVisionStatus);
      const latestRun = nextRuns.at(-1);
      setAnalysisOutput(latestRun ? await api.analysisOutput(latestRun.analysis_run_id) : null);
      setConnection("connected"); setMessage("边缘节点在线 · 数据链路正常");
    } catch (error) {
      setConnection("offline"); setMessage("演示模式 · 后端连接后将自动同步"); console.warn(error);
    }
  };

  useEffect(() => void refresh(), []);

  const runDemo = async () => {
    if (demoStage > 0 && demoStage < 5) return;
    setDemoStage(1); setTab("monitor"); setMessage("正在重放公开数据集样本…");
    await delay(700); setDemoStage(2); await delay(700);
    try {
      const [dataset, category] = target.split(" · ");
      const selectedModel = model.split(" · ")[0] as "EfficientAD" | "PatchCore" | "PaDiM" | "DRAEM";
      await api.replayPublicDataset({ dataset: dataset as "MVTec AD" | "VisA" | "BTAD", category, model: selectedModel, seed: 7, fps: 10 });
      setDemoStage(3); await refresh();
    } catch (error) {
      setConnection("offline"); setMessage("本地交互演示完成 · 启动 API 后可写入真实 Case"); console.warn(error); setDemoStage(3);
    }
    await delay(800); setDemoStage(4); await delay(900); setDemoStage(5);
    setMessage("全链路调研已完成 · 等待人工决策");
  };

  const pageTitle = NAV_GROUPS.flatMap((group) => group.items).find((item) => item.id === tab)?.label ?? "实时监控";
  const openEvent = (eventId: string) => { setSelectedEventId(eventId); setTab("events"); };

  return <div className="app-frame">
    <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Network size={21} /></div><div><strong>Aegis IQ</strong><span>工业异常智能体</span></div><button className="icon-button sidebar-close" onClick={() => setMobileNav(false)} aria-label="关闭菜单"><PanelLeftClose size={18} /></button></div>
      <button className="plant-card" onClick={() => setMessage("当前生产空间：华东智造工厂 · Line-A") } aria-label="查看当前生产空间"><span className="plant-icon"><Boxes size={17} /></span><div><small>当前生产空间</small><strong>华东智造工厂</strong></div><ChevronDown size={15} /></button>
      <nav className="side-nav" aria-label="主导航">{NAV_GROUPS.map((group) => <div className="nav-group" key={group.title}><p>{group.title}</p>{group.items.map((item) => { const Icon = item.icon; const count = item.id === "approval" && proposals.length ? String(proposals.length) : item.count; return <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => { setTab(item.id); setMobileNav(false); }}><Icon size={17} /><span>{item.label}</span>{count && <b>{count}</b>}</button>; })}</div>)}</nav>
      <div className="sidebar-system"><div className="system-row"><span className={`live-dot ${connection}`} /><div><strong>系统状态</strong><small>{connection === "connected" ? "所有服务正常" : connection === "loading" ? "正在检测" : "前端演示模式"}</small></div><span>{connection === "connected" ? "99.98%" : "LOCAL"}</span></div><div className="system-row"><span className="edge-chip">E</span><div><strong>边缘节点</strong><small>{visionStatus?.running ? "Vision Worker 运行中" : "Edge-01 · Standby"}</small></div><ChevronRight size={15} /></div></div>
    </aside>
    {mobileNav && <button className="nav-backdrop" aria-label="关闭菜单" onClick={() => setMobileNav(false)} />}
    <main className="main-area">
      <header className="topbar"><div className="page-heading"><button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="打开菜单"><Menu size={20} /></button><div><p>质量调查工作台 / {pageTitle}</p><h1>{pageTitle}</h1></div></div><div className="top-actions"><button className="quick-search" onClick={() => { setSearchOpen(true); setNoticeOpen(false); setUserMenuOpen(false); }}><Search size={16} /><span>搜索事件、工位或 Case</span><kbd>⌘ K</kbd></button><button className="icon-button has-notice" aria-label="通知" aria-expanded={noticeOpen} onClick={() => { setNoticeOpen(!noticeOpen); setUserMenuOpen(false); }}><Bell size={18} /><i /></button><button className="user-menu" aria-expanded={userMenuOpen} onClick={() => { setUserMenuOpen(!userMenuOpen); setNoticeOpen(false); }}><span>林</span><div><strong>林工程师</strong><small>质量管理员</small></div><ChevronDown size={14} /></button></div></header>
      {searchOpen && <TopDialog title="快速搜索" onClose={() => setSearchOpen(false)}><button className="dialog-action" onClick={() => { openEvent(EVENT_ITEMS[0].id); setSearchOpen(false); }}><AlertTriangle size={16} /><span><strong>EVT-0823-041</strong><small>CAM-01 · 表面裂纹</small></span><ChevronRight size={16} /></button><button className="dialog-action" onClick={() => { setTab("cases"); setSearchOpen(false); }}><SquareStack size={16} /><span><strong>质量 Case</strong><small>查看异常调查与执行状态</small></span><ChevronRight size={16} /></button></TopDialog>}
      {noticeOpen && <TopPopover title="通知"><button onClick={() => { openEvent(EVENT_ITEMS[0].id); setNoticeOpen(false); }}><AlertTriangle size={15} /><span><strong>检测到高优先级异常</strong><small>EVT-0823-041 已完成 Agent 调研</small></span></button></TopPopover>}
      {userMenuOpen && <TopPopover title="账户"><button onClick={() => { setTab("operations"); setUserMenuOpen(false); }}><Activity size={15} /><span><strong>系统运行</strong><small>查看边缘节点与服务状态</small></span></button></TopPopover>}
      <div className="content">
        {tab === "monitor" && <MonitorDashboard model={model} setModel={setModel} target={target} setTarget={setTarget} runDemo={runDemo} demoStage={demoStage} connection={connection} message={message} proposals={proposals} runs={runs} cases={cases} visionEvents={visionEvents} analysisOutput={analysisOutput} onRefresh={refresh} onOpenEvent={openEvent} onNavigate={(nextTab) => setTab(nextTab)} />}
        {tab === "events" && <EventsPage visionEvents={visionEvents} onRunDemo={runDemo} selectedEventId={selectedEventId} onSelectedEventChange={setSelectedEventId} onNavigate={(nextTab) => setTab(nextTab)} />}
        {tab === "cases" && <Cases cases={cases} runs={runs} />}
        {tab === "approval" && <Approval proposals={proposals} onDone={refresh} />}
        {tab === "qms" && <QmsTasks tasks={qmsTasks} />}
        {tab === "library" && <CaseLibrary cases={library} />}
        {tab === "operations" && <Operations workers={workers} delivery={delivery} visionStatus={visionStatus} onRefresh={refresh} />}
        {tab === "evaluation" && <Evaluation reports={evaluationReports} onRefresh={refresh} />}
        {tab === "documents" && <Documents onMessage={setMessage} />}
        {tab === "model-health" && <ModelHealth />}
      </div>
    </main>
  </div>;
}

function MonitorDashboard({ model, setModel, target, setTarget, runDemo, demoStage, connection, message, proposals, runs, cases, visionEvents, analysisOutput, onRefresh, onOpenEvent, onNavigate }: {
  model: string; setModel: (value: string) => void; target: string; setTarget: (value: string) => void; runDemo: () => void; demoStage: DemoStage; connection: string; message: string; proposals: Proposal[]; runs: AnalysisRun[]; cases: QualityCase[]; visionEvents: VisionEvent[]; analysisOutput: AnalysisOutput | null; onRefresh: () => void; onOpenEvent: (eventId: string) => void; onNavigate: (tab: Tab) => void;
}) {
  const [selectedEvent, setSelectedEvent] = useState(EVENT_ITEMS[0].id);
  const [range, setRange] = useState("6H");
  const [view, setView] = useState("single");
  const [traceOpen, setTraceOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const trace = analysisOutput?.trace.events.length ? analysisOutput.trace.events : FALLBACK_TRACE;
  const isRunning = demoStage > 0 && demoStage < 5;
  const activeStage = demoStage || 5;
  const latestRun = runs.at(-1);
  const latestProposal = proposals.at(-1) ?? analysisOutput?.proposal;
  const publicDataset = target.split(" · ")[0]; const category = target.split(" · ")[1] ?? target;
  const totalEvents = Math.max(visionEvents.length, EVENT_ITEMS.length);

  return <section className="dashboard-page">
    <div className="dashboard-intro"><div><div className="title-line"><h2>产线异常态势</h2><span className={`connection-badge ${connection}`}><i />{message}</span></div><p>将视觉检测、异常聚合与 Agent 调研放在同一条可审计工作流中。</p>{selectedFile && <small className="file-selection">已选择待检测图像：{selectedFile}</small>}</div><div className="intro-actions"><input ref={fileInput} className="hidden-file-input" type="file" accept="image/*" onChange={(event) => setSelectedFile(event.target.files?.[0]?.name ?? "")} /><button className="secondary-button" onClick={() => fileInput.current?.click()}><ImagePlus size={16} />导入图像</button><button className="primary-button" onClick={runDemo} disabled={isRunning}>{isRunning ? <RefreshCw className="spin" size={16} /> : <Play size={16} fill="currentColor" />}{isRunning ? "正在运行闭环" : "运行全链路演示"}</button></div></div>
    <div className="control-strip">
      <ControlSelect icon={<Sparkles size={17} />} label="检测模型" value={model} onChange={setModel} options={["EfficientAD · MVTEC pretrained", "PatchCore · WideResNet-50", "PaDiM · ResNet-18", "DRAEM · Synthetic defects"]} />
      <div className="control-divider" /><ControlSelect icon={<SquareStack size={17} />} label="检测对象 / 数据集" value={target} onChange={setTarget} options={["MVTec AD · Hazelnut", "MVTec AD · Cable", "VisA · PCB", "BTAD · Gear"]} />
      <div className="control-divider" /><div className="control-meta"><span><CircleDot size={15} />工位</span><strong>Line-A · CAM-01</strong></div>
      <div className="control-divider" /><div className="control-meta"><span><SlidersHorizontal size={15} />异常阈值</span><strong>0.72 <small>自动校准</small></strong></div><button className="refresh-button" onClick={onRefresh} aria-label="刷新监控数据"><RefreshCw size={17} /></button>
    </div>
    <div className="kpi-grid">
      <KpiCard icon={<Activity size={19} />} label="今日检测量" value="12,847" note="较昨日" trend="+8.2%" direction="up" spark="teal" />
      <KpiCard icon={<TriangleAlert size={19} />} label="NG 率" value="3.7%" note="基线 1.2%" trend="+2.5%" direction="bad" spark="orange" />
      <KpiCard icon={<AlertTriangle size={19} />} label="活跃异常" value={String(totalEvents)} note="高优先级 2" trend="需关注" direction="warn" spark="red" />
      <KpiCard icon={<Bot size={19} />} label="Agent 完成率" value={runs.length ? "92%" : "89%"} note={`${Math.max(runs.length, 14)} 次自动调研`} trend="+4.1%" direction="up" spark="blue" />
    </div>
    <div className="monitor-grid">
      <section className="surface vision-panel"><PanelHeader eyebrow="LIVE INSPECTION" title="实时检测画面" aside={<><span className="streaming"><i />LIVE</span><label className="view-select"><span className="sr-only">监控布局</span><select aria-label="监控布局" value={view} onChange={(event) => setView(event.target.value)}><option value="single">单画面</option><option value="dual">双画面</option><option value="heatmap">异常热图</option></select><ChevronDown size={14} /></label></>} /><div className={`vision-stage ${view === "heatmap" ? "heatmap-view" : ""}`}><div className="camera-meta"><span>CAM-01</span><span>{view === "dual" ? "双画面对比" : "1920 × 1200"}</span><span>25 FPS</span></div><div className="industrial-part" aria-label={`${category} anomaly inspection visualization`}><div className="part-shadow" /><div className="part-body"><i className="part-hole h1" /><i className="part-hole h2" /><i className="part-hole h3" /><i className="part-hole h4" /><i className="part-ring" /><i className="part-groove g1" /><i className="part-groove g2" /><i className="part-groove g3" /></div><div className={`scan-line ${isRunning ? "scanning" : ""}`} /><div className="heat-spot spot-one" /><div className="heat-spot spot-two" /><div className="defect-box defect-one"><span>裂纹 · 0.91</span></div><div className="defect-box defect-two"><span>异物 · 0.78</span></div><div className="frame-index">FRAME 008417 · {publicDataset.toUpperCase()}</div></div></div><div className="vision-footer"><div><span className="status-symbol danger"><X size={15} /></span><div><small>当前判定</small><strong>异常 / NG</strong></div></div><div><small>异常分数</small><strong className="danger-text">0.91</strong></div><div><small>推理耗时</small><strong>38 ms</strong></div><div><small>模型版本</small><strong>{model.split(" · ")[0]} v2.4</strong></div></div></section>
      <section className="surface event-panel"><PanelHeader eyebrow="ANOMALY FEED" title="异常事件" aside={<button className="text-button" onClick={() => onNavigate("events")}>查看全部 <ArrowRight size={14} /></button>} /><div className="event-list">{EVENT_ITEMS.slice(0, 3).map((item, index) => <button key={item.id} className={`event-row ${selectedEvent === item.id ? "selected" : ""}`} onClick={() => { setSelectedEvent(item.id); onOpenEvent(item.id); }}><span className={`severity-icon ${item.severity}`}><AlertTriangle size={16} /></span><div className="event-main"><div><strong>{item.kind}</strong><time>{item.time}</time></div><p>{item.station} · {item.object}</p><span className={`event-state ${index === 0 && isRunning ? "running" : ""}`}>{index === 0 && isRunning ? "Agent 调研中" : item.state}</span></div><div className="score-ring" style={{ "--score": `${item.score * 360}deg` } as React.CSSProperties}><span>{Math.round(item.score * 100)}</span></div></button>)}</div><div className="event-summary"><span>最近 30 分钟</span><div><b>4</b> 个异常</div><div><b>2</b> 个高优先级</div></div></section>
    </div>
    <div className="analysis-grid">
      <section className="surface trend-panel"><PanelHeader eyebrow="ANOMALY SCORE" title="异常分数趋势" aside={<div className="range-tabs">{["1H", "6H", "24H"].map((item) => <button key={item} className={range === item ? "active" : ""} onClick={() => setRange(item)} aria-pressed={range === item}>{item}</button>)}</div>} /><div className="chart-legend"><span><i className="legend-line teal" />异常分数 · {range}</span><span><i className="legend-line dashed" />阈值 0.72</span><b><ArrowUpRight size={15} /> 峰值 0.91</b></div><ScoreChart /></section>
      <section className="surface insight-panel"><PanelHeader eyebrow="AGENT INSIGHT" title="调研结论" aside={<span className="confidence"><ShieldCheck size={14} />置信度 86%</span>} /><div className="insight-callout"><Sparkles size={18} /><p>{analysisOutput?.analysis.summary ?? "异常样本在右上区域呈稳定聚集，时间上与换型后的治具定位偏移高度相关；光照变化不足以单独解释当前 NG 率上升。"}</p></div><div className="hypothesis-list">{(analysisOutput?.analysis.hypotheses.slice(0, 2) ?? [
        { hypothesis_id: "H1", title: "治具定位销偏移", description: "空间聚集模式与历史已验证 Case 相似", confidence: .86, supporting_evidence_ids: [], contradicting_evidence_ids: [], missing_evidence: [] },
        { hypothesis_id: "H2", title: "局部照明衰减", description: "亮度有变化，但与缺陷区域相关性较弱", confidence: .42, supporting_evidence_ids: [], contradicting_evidence_ids: [], missing_evidence: [] },
      ]).map((item, index) => <div className="hypothesis" key={item.hypothesis_id}><span>H{index + 1}</span><div><strong>{item.title}</strong><small>{item.description}</small></div><b>{Math.round(item.confidence * 100)}%</b></div>)}</div><button className="proposal-link" onClick={() => onNavigate("approval")}>{latestProposal ? `查看排查方案 · ${latestProposal.steps.length} 个步骤` : "查看建议排查方案"}<ArrowRight size={15} /></button></section>
    </div>
    <section className="surface agent-panel"><PanelHeader eyebrow="AUDITABLE AGENT WORKFLOW" title="Agent 自动调研轨迹" aside={<><span className={`run-status ${isRunning ? "working" : "done"}`}>{isRunning ? <RefreshCw className="spin" size={13} /> : <CheckCircle2 size={14} />}{isRunning ? `执行中 · ${activeStage}/5` : latestRun ? latestRun.status : "演示轨迹"}</span><button className="icon-button" onClick={() => setSettingsOpen(true)} aria-label="查看 Agent 配置"><Settings size={16} /></button></>} /><div className="trace-note"><ShieldCheck size={14} />展示的是工具调用、证据与结论摘要，用于审计；不暴露模型隐藏思维链。</div><div className="agent-flow">{trace.slice(0, 5).map((event, index) => { const complete = activeStage > index + 1 || demoStage === 0 || demoStage === 5; const active = isRunning && activeStage === index + 1; return <div className={`flow-step ${complete ? "complete" : ""} ${active ? "active" : ""}`} key={`${event.sequence}-${event.action}`}><div className="flow-top"><span>{complete ? <Check size={15} /> : active ? <RefreshCw className="spin" size={14} /> : index + 1}</span>{index < 4 && <i />}</div><div className="flow-card"><small>STEP {index + 1}</small><strong>{traceTitle(event.action)}</strong><p>{event.summary}</p><div><span>{event.duration_ms ?? 0} ms</span>{event.evidence_ids.slice(0, 2).map((id) => <b key={id}>{id}</b>)}</div></div></div>; })}</div><div className="flow-footer"><span><Clock3 size={14} />总耗时 1.8s</span><span><Zap size={14} />{trace.filter((event) => event.event_type === "TOOL_CALL").length} 次工具调用</span><span><Layers3 size={14} />{new Set(trace.flatMap((event) => event.evidence_ids)).size} 条证据</span><button onClick={() => setTraceOpen(true)}>{cases.length ? `${cases.length} 个 Case 已生成 · Trace` : "打开完整 Trace"}<ChevronRight size={14} /></button></div></section>
    {traceOpen && <TraceDialog trace={trace} onClose={() => setTraceOpen(false)} />}
    {settingsOpen && <TopDialog title="Agent 调研配置" onClose={() => setSettingsOpen(false)}><div className="settings-grid"><span>执行边界</span><strong>只读工具调用，外部写入需人工审批</strong><span>最大循环</span><strong>5 步</strong><span>证据要求</span><strong>每项结论需关联 Snapshot 或知识库证据</strong></div></TopDialog>}
    <DatasetReplay model={model} target={target} demoStage={demoStage} runDemo={runDemo} />
  </section>;
}

function ControlSelect({ icon, label, value, onChange, options }: { icon: React.ReactNode; label: string; value: string; onChange: (value: string) => void; options: string[] }) { return <label className="control-select"><span>{icon}{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label>; }

function KpiCard({ icon, label, value, note, trend, direction, spark }: { icon: React.ReactNode; label: string; value: string; note: string; trend: string; direction: string; spark: string }) { return <article className="surface kpi-card"><div className={`kpi-icon ${spark}`}>{icon}</div><div className="kpi-copy"><span>{label}</span><strong>{value}</strong><small>{note} <b className={direction}>{direction === "up" || direction === "bad" ? <ArrowUpRight size={13} /> : <CircleDot size={11} />}{trend}</b></small></div><MiniSpark color={spark} /></article>; }

function MiniSpark({ color }: { color: string }) { const stroke = { teal: "#0d9488", orange: "#e0883e", red: "#db5b55", blue: "#4e7edb" }[color] ?? "#0d9488"; return <svg className="mini-spark" viewBox="0 0 82 36" aria-hidden="true"><path d="M1 30 C9 25, 13 29, 20 22 S32 26, 39 17 S50 20, 58 11 S70 16, 81 3" fill="none" stroke={stroke} strokeWidth="2" /><path d="M1 30 C9 25, 13 29, 20 22 S32 26, 39 17 S50 20, 58 11 S70 16, 81 3 L81 36 L1 36Z" fill={stroke} opacity=".08" /></svg>; }

function PanelHeader({ eyebrow, title, aside }: { eyebrow: string; title: string; aside?: React.ReactNode }) { return <header className="panel-header"><div><span>{eyebrow}</span><h3>{title}</h3></div>{aside && <div className="panel-aside">{aside}</div>}</header>; }

function ScoreChart() { return <div className="score-chart"><svg viewBox="0 0 680 190" preserveAspectRatio="none" role="img" aria-label="六小时异常分数折线图"><defs><linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0d9488" stopOpacity=".22" /><stop offset="100%" stopColor="#0d9488" stopOpacity="0" /></linearGradient></defs><g className="grid-lines"><line x1="36" y1="22" x2="664" y2="22" /><line x1="36" y1="65" x2="664" y2="65" /><line x1="36" y1="108" x2="664" y2="108" /><line x1="36" y1="151" x2="664" y2="151" /></g><line className="threshold-line" x1="36" y1="61" x2="664" y2="61" /><path className="area" d="M36 139 C73 134 91 129 126 132 S181 120 215 126 S272 112 304 117 S348 98 376 102 S419 78 449 82 S488 48 520 72 S563 42 594 48 S626 25 664 38 L664 162 L36 162Z" /><path className="score-line" d="M36 139 C73 134 91 129 126 132 S181 120 215 126 S272 112 304 117 S348 98 376 102 S419 78 449 82 S488 48 520 72 S563 42 594 48 S626 25 664 38" /><circle cx="636" cy="31" r="5" /><g className="axis-labels"><text x="4" y="26">1.0</text><text x="4" y="69">0.7</text><text x="4" y="112">0.4</text><text x="4" y="155">0.0</text><text x="36" y="184">09:00</text><text x="155" y="184">10:00</text><text x="278" y="184">11:00</text><text x="400" y="184">12:00</text><text x="522" y="184">13:00</text><text x="628" y="184">14:00</text></g></svg></div>; }

function DatasetReplay({ model, target, demoStage, runDemo }: { model: string; target: string; demoStage: DemoStage; runDemo: () => void }) {
  const stages = ["读取公开样本", "模型推理", "异常聚合", "Agent 调研", "等待人工决策"];
  return <section className="surface replay-panel"><div className="replay-intro"><span className="dataset-logo">MV</span><div><span className="eyebrow">PUBLIC DATASET REPLAY</span><h3>公开工业异常数据集重放沙箱</h3><p>以 MVTec AD / VisA / BTAD 的测试集作为“相机帧”，统一归一化为检测事件，再进入生产级 Case 与 Agent 工作流。</p></div></div><div className="replay-config"><div><span>数据源</span><strong>{target}</strong></div><ArrowRight size={16} /><div><span>检测器</span><strong>{model.split(" · ")[0]}</strong></div><ArrowRight size={16} /><div><span>重放节奏</span><strong>10 FPS · 固定 Seed</strong></div><button className="primary-button" onClick={runDemo} disabled={demoStage > 0 && demoStage < 5}>{demoStage > 0 && demoStage < 5 ? "重放中…" : "开始重放"}</button></div><div className="replay-steps">{stages.map((stage, index) => { const done = demoStage === 5 || (demoStage > 0 && demoStage > index + 1); const active = demoStage === index + 1; return <div className={`${done ? "done" : ""} ${active ? "active" : ""}`} key={stage}><span>{done ? <Check size={13} /> : index + 1}</span><strong>{stage}</strong>{index < stages.length - 1 && <i />}</div>; })}</div><div className="replay-foot"><span><ShieldCheck size={14} />只使用公开图像；产线元数据、SOP 和历史 Case 均为合成数据</span><span><TimerReset size={14} />支持固定种子复现与逐帧审计</span></div></section>;
}

function EventsPage({ visionEvents, onRunDemo, selectedEventId, onSelectedEventChange, onNavigate }: { visionEvents: VisionEvent[]; onRunDemo: () => void; selectedEventId: string | null; onSelectedEventChange: (id: string | null) => void; onNavigate: (tab: Tab) => void }) {
  const [filter, setFilter] = useState<"all" | "priority" | "investigating">("all");
  const [query, setQuery] = useState("");
  const items: EventItem[] = visionEvents.length ? visionEvents.map((event, index) => ({ id: event.event_id, time: new Date(event.occurred_at).toLocaleTimeString("zh-CN", { hour12: false }), station: "CAM-01", object: event.detector_type ?? "vision", kind: String(event.details?.defect_type ?? event.fault_kind ?? "视觉异常"), score: event.anomaly_score ?? .75, severity: index === 0 ? "critical" : "high", state: "已触发调研" })) : EVENT_ITEMS;
  const filteredItems = items.filter((item) => (filter !== "priority" || item.severity === "critical" || item.severity === "high") && (filter !== "investigating" || item.state.includes("调研")) && `${item.id} ${item.kind} ${item.station} ${item.object}`.toLowerCase().includes(query.toLowerCase()));
  const selected = items.find((item) => item.id === selectedEventId) ?? null;
  return <section><PageIntro title="异常事件中心" description="按严重程度、工位和调研状态统一处理视觉异常。" action={<button className="primary-button" onClick={onRunDemo}><Play size={16} />载入演示事件</button>} /><div className="surface data-surface"><div className="filter-row"><button className={`filter ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>全部 <b>{items.length}</b></button><button className={`filter ${filter === "priority" ? "active" : ""}`} onClick={() => setFilter("priority")}>高优先级</button><button className={`filter ${filter === "investigating" ? "active" : ""}`} onClick={() => setFilter("investigating")}>调研中</button><label className="table-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索事件 ID 或缺陷类型" /></label></div><div className="event-table"><div className="event-table-head"><span>事件</span><span>检测对象</span><span>异常分数</span><span>状态</span><span>时间</span><span /></div>{filteredItems.map((item) => <div className="event-table-row" key={item.id}><span><i className={`severity-dot ${item.severity}`} /><div><strong>{item.kind}</strong><small>{item.id}</small></div></span><span><strong>{item.station}</strong><small>{item.object}</small></span><span><b className="score-value">{item.score.toFixed(2)}</b><i className="score-bar"><em style={{ width: `${item.score * 100}%` }} /></i></span><span><mark>{item.state}</mark></span><time>{item.time}</time><button className="icon-button" aria-label={`查看事件详情 ${item.id}`} onClick={() => onSelectedEventChange(item.id)}><ChevronRight size={16} /></button></div>)}{filteredItems.length === 0 && <EmptyState icon={<Search />} title="没有匹配的异常事件" text="尝试更换筛选条件或搜索关键词。" />}</div></div>{selected && <EventDetail event={selected} onClose={() => onSelectedEventChange(null)} onOpenCases={() => { onSelectedEventChange(null); onNavigate("cases"); }} />}</section>;
}

function TopDialog({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}><section className="dialog-card" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}><header><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="关闭"><X size={17} /></button></header><div className="dialog-body">{children}</div></section></div>; }

function TopPopover({ title, children }: { title: string; children: React.ReactNode }) { return <section className="top-popover" aria-label={title}><strong>{title}</strong><div>{children}</div></section>; }

function EventDetail({ event, onClose, onOpenCases }: { event: EventItem; onClose: () => void; onOpenCases: () => void }) { return <TopDialog title="异常事件详情" onClose={onClose}><div className="detail-grid"><span>事件 ID</span><strong>{event.id}</strong><span>发生时间 / 工位</span><strong>{event.time} · {event.station}</strong><span>检测对象</span><strong>{event.object}</strong><span>异常类型</span><strong>{event.kind}</strong><span>异常分数</span><strong className="danger-text">{event.score.toFixed(2)} / 阈值 0.72</strong><span>处置状态</span><strong>{event.state}</strong></div><p className="detail-note">该异常已冻结对应的图像窗口与检测版本；Agent 仅输出可审计的工具调用和证据摘要。</p><div className="dialog-footer"><button className="secondary-button" onClick={onClose}>返回列表</button><button className="primary-button" onClick={onOpenCases}>查看相关 Case <ArrowRight size={15} /></button></div></TopDialog>; }

function TraceDialog({ trace, onClose }: { trace: AgentTraceEvent[]; onClose: () => void }) { return <TopDialog title="完整 Agent Trace" onClose={onClose}><p className="detail-note">以下内容是执行事件、工具调用和证据引用，不包含模型隐藏思维链。</p><div className="trace-list">{trace.map((event) => <article key={`${event.sequence}-${event.action}`}><span>{event.sequence}</span><div><strong>{traceTitle(event.action)}</strong><p>{event.summary}</p><small>{event.event_type} · {event.duration_ms ?? 0} ms · {event.evidence_ids.join("、") || "无证据 ID"}</small></div></article>)}</div></TopDialog>; }

function PageIntro({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) { return <div className="dashboard-intro"><div><h2>{title}</h2><p>{description}</p></div>{action}</div>; }

function Cases({ cases, runs }: { cases: QualityCase[]; runs: AnalysisRun[] }) {
  const [selectedCase, setSelectedCase] = useState<QualityCase | null>(null);
  return <section><PageIntro title="质量 Case" description="从异常窗口到外部 QMS 的完整状态视图。" /><div className="surface data-surface"><PanelHeader eyebrow="CASE REGISTER" title="异常调查 Case" aside={<span className="subtle-text">Snapshot 不可变 · 外部状态只读同步</span>} /><div className="case-grid">{cases.length === 0 ? <EmptyState icon={<SquareStack />} title="尚无质量 Case" text="运行公开数据集重放后，异常会自动聚合为 Case。" /> : cases.map((item) => { const run = runs.find((candidate) => candidate.case_id === item.case_id); return <article className="case-card" key={item.case_id}><div className="case-card-top"><span className="case-icon"><AlertTriangle size={17} /></span><span className="pill">{item.case_status}</span><button className="icon-button" aria-label={`查看 Case 详情 ${item.case_id}`} onClick={() => setSelectedCase(item)}><ChevronRight size={16} /></button></div><h3>{item.case_id}</h3><p>{item.episode_status} · {run ? `Analysis ${run.status}` : "等待 Agent"}</p><div className="case-progress"><span className="done"><Check size={12} /></span><i /><span className={run ? "done" : ""}><Bot size={12} /></span><i /><span className={item.qms_task_id ? "done" : ""}><ClipboardCheck size={12} /></span></div><footer><span>{run?.trace_event_count ?? 0} trace events</span><strong>{item.qms_task_id ?? "等待审批"}</strong></footer></article>; })}</div></div>{selectedCase && <TopDialog title="质量 Case 详情" onClose={() => setSelectedCase(null)}><div className="detail-grid"><span>Case ID</span><strong>{selectedCase.case_id}</strong><span>Case 状态</span><strong>{selectedCase.case_status}</strong><span>异常聚合</span><strong>{selectedCase.episode_status}</strong><span>QMS 任务</span><strong>{selectedCase.qms_task_id ?? "尚未创建，等待人工审批"}</strong></div></TopDialog>}</section>;
}

function QmsTasks({ tasks }: { tasks: QmsTask[] }) { return <section><PageIntro title="QMS 调查任务" description="审批通过后由 Worker 创建，Agent 不持有外部写权限。" /><div className="surface data-surface"><PanelHeader eyebrow="EXTERNAL QMS" title="任务队列" aside={<span className="confidence"><ShieldCheck size={14} />Human-in-the-loop</span>} /><div className="stack-list">{tasks.length === 0 ? <EmptyState icon={<Workflow />} title="暂无 QMS 任务" text="批准 Agent 的调查建议后，任务会安全地写入外部 QMS。" /> : tasks.map((task) => <article className="stack-row" key={task.task_id}><span className="row-icon"><ClipboardCheck size={17} /></span><div><span className="pill">{task.status}</span><h3>{task.task_id}</h3><p>{task.case_id} · Proposal {task.proposal_id}</p></div><div className="row-meta"><span>{task.external_system}</span><strong>{task.assignee_role}</strong><a href={task.task_uri} target="_blank" rel="noreferrer">打开任务 <ArrowUpRight size={14} /></a></div></article>)}</div></div></section>; }

function CaseLibrary({ cases }: { cases: VerifiedCase[] }) { return <section><PageIntro title="已验证案例库" description="只收录人工确认且验证有效的 Case，作为 C 级经验性证据。" /><div className="surface data-surface"><PanelHeader eyebrow="TRUSTED KNOWLEDGE" title="历史验证案例" /><div className="library-grid">{cases.length === 0 ? <EmptyState icon={<Database />} title="案例库正在等待验证结果" text="QMS 关闭并由人工确认有效后，Case 才会进入可信案例库。" /> : cases.map((item) => <article className="library-card" key={item.document_id}><span className="library-icon"><Database size={17} /></span><span className="pill">{item.metadata.verification_status}</span><h3>{item.document_id}</h3><p>{item.text}</p><small>{item.metadata.date_prefix} · {item.metadata.trigger_family}</small></article>)}</div></div></section>; }

function Approval({ proposals, onDone }: { proposals: Proposal[]; onDone: () => void }) {
  const decide = async (proposal: Proposal, decision: "APPROVE" | "REJECT") => { try { await api.decide(proposal, decision); onDone(); } catch (error) { window.alert(String(error)); } };
  return <section><PageIntro title="待人工决策" description="Agent 提供证据与建议，人类保留最终行动权。" /><div className="surface data-surface"><PanelHeader eyebrow="HUMAN GATE" title="调查建议审批" aside={<span className="confidence"><ShieldCheck size={14} />Agent 无外部写权限</span>} /><div className="proposal-list">{proposals.length === 0 ? <EmptyState icon={<ClipboardCheck />} title="当前没有待审批建议" text="运行全链路演示可生成包含证据引用的调查方案。" /> : proposals.map((proposal) => <article className="proposal-card" key={proposal.proposal_id}><div className="proposal-head"><span className="pill high">{proposal.status}</span><span>v{proposal.version}</span></div><h3>{proposal.title}</h3><p>{proposal.reason}</p><ol>{proposal.steps.map((step) => <li key={step.order}><span>{step.order}</span><div><strong>{step.instruction}</strong><small>预期证据：{step.expected_evidence}</small></div></li>)}</ol><div className="evidence-chips">{proposal.evidence_ids.map((id) => <span key={id}>{id}</span>)}</div><footer><button className="danger-button" onClick={() => decide(proposal, "REJECT")}>驳回</button><button className="primary-button" onClick={() => decide(proposal, "APPROVE")}><Check size={16} />批准并创建任务</button></footer></article>)}</div></div></section>;
}

function Operations({ workers, delivery, visionStatus, onRefresh }: { workers: WorkerStatus[]; delivery: { pending: DeliveryRecord[]; processed: DeliveryRecord[]; dlq: DeliveryRecord[] }; visionStatus: VisionStatus | null; onRefresh: () => void }) {
  const retry = async (eventId: string) => { try { await api.retryDlq(eventId); onRefresh(); } catch (error) { window.alert(String(error)); } }; const records = [...delivery.pending, ...delivery.dlq];
  return <section><PageIntro title="系统运行" description="边缘推理、Agent Worker 与消息投递的可观测性。" action={<button className="secondary-button" onClick={onRefresh}><RefreshCw size={16} />刷新</button>} /><div className="ops-kpis"><article className="surface"><span><CircleDot size={16} />Vision Worker</span><strong>{visionStatus?.running ? "RUNNING" : "STANDBY"}</strong><small>{visionStatus?.completed ?? 0} completed · {visionStatus?.failed ?? 0} failed</small></article><article className="surface"><span><Workflow size={16} />Delivery Queue</span><strong>{records.length}</strong><small>{delivery.processed.length} processed</small></article><article className="surface"><span><Bot size={16} />Agent Workers</span><strong>{workers.length || 3}</strong><small>平均延迟 {workers[0]?.avg_latency_ms ?? 182} ms</small></article></div><div className="operations-grid"><div className="surface data-surface"><PanelHeader eyebrow="WORKER STATUS" title="Worker 健康度" /><div className="stack-list">{workers.length === 0 ? <EmptyState icon={<Activity />} title="等待 Worker 指标" text="后端连接后将展示真实处理量与延迟。" /> : workers.map((worker) => <article className="worker-row" key={worker.worker}><span className="live-dot connected" /><div><strong>{worker.worker}</strong><small>{worker.processed} processed · {worker.failed} failed</small></div><b>{worker.avg_latency_ms} ms</b></article>)}</div></div><div className="surface data-surface"><PanelHeader eyebrow="DELIVERY" title="Pending / DLQ" /><div className="stack-list">{records.length === 0 ? <EmptyState icon={<CheckCircle2 />} title="投递队列健康" text="当前没有 Pending 或 DLQ 消息。" /> : records.map((record) => <article className="delivery-row" key={`${record.event_id}-${record.state}`}><div><span className={`pill ${record.state === "DLQ" ? "high" : ""}`}>{record.state}</span><strong>{record.event_id}</strong><small>{record.case_id} · attempts {record.attempts}</small></div>{record.state === "DLQ" && <button onClick={() => retry(record.event_id)}>授权重试</button>}</article>)}</div></div></div></section>;
}

function Evaluation({ reports, onRefresh }: { reports: EvaluationReport[]; onRefresh: () => void }) {
  const [casesPerDay, setCasesPerDay] = useState(8); const [roi, setRoi] = useState<import("./api/client").RoiResult | null>(null);
  const run = async () => { try { await api.runEvaluationMatrix(); onRefresh(); } catch (error) { window.alert(String(error)); } }; const calculate = async () => { try { setRoi(await api.roi({ cases_per_day: casesPerDay })); } catch (error) { window.alert(String(error)); } };
  return <section><PageIntro title="模型评估" description="使用固定数据集、工具和 Prompt 版本进行可复现评估。" action={<button className="primary-button" onClick={run}><Play size={16} />运行评估矩阵</button>} /><div className="evaluation-grid"><div className="surface data-surface"><PanelHeader eyebrow="AGENT EVAL" title="配置对比" /><div className="evaluation-list">{reports.length === 0 ? <EmptyState icon={<Gauge />} title="尚未运行评估" text="运行两组固定配置后对比通过率、延迟与安全停止。" /> : reports.map((report) => <article className="evaluation-card" key={report.report_id}><div><strong>{report.config.config_id}</strong><span>{report.config.prompt_version} · {report.config.model}</span></div><b>{Math.round(Number(report.summary.pass_rate) * 100)}%</b><small>平均延迟 {String(report.summary.avg_latency_ms)} ms</small></article>)}</div></div><div className="surface data-surface"><PanelHeader eyebrow="ROI CALCULATOR" title="潜在价值测算" /><p className="subtle-copy">示例金额与收益均为假设参数，不代表真实客户收益。</p><label className="field-label">每天 Case<input type="number" min="0" value={casesPerDay} onChange={(event) => setCasesPerDay(Number(event.target.value))} /></label><button className="secondary-button full" onClick={calculate}>重新计算</button>{roi && <div className="roi-result"><strong>ROI {roi.roi_percent === null ? "—" : `${roi.roi_percent}%`}</strong><span>年度净收益 ¥{roi.annual_net_benefit_cny}</span><small>{roi.disclaimer}</small></div>}</div></div></section>;
}

function Documents({ onMessage }: { onMessage: (message: string) => void }) {
  const [content, setContent] = useState("# 定位销检查\n\n检查治具定位销间隙、磨损与复位状态。"); const [query, setQuery] = useState("fixture positioning pin"); const [hits, setHits] = useState<Array<Record<string, unknown>>>([]);
  const upload = async () => { try { await api.upload({ document_id: `web-manual-${Date.now()}`, title: "Web uploaded manual", version: "1.0", source_type: "TECHNICAL_DOCUMENT", file_name: "manual.md", content_type: "text/markdown", effective_from: new Date().toISOString(), applicability: { station_id: "camera-01", product_id: "part-A" }, content }); onMessage("文档已入库，重复 Hash 会被幂等忽略"); } catch (error) { onMessage(String(error)); } }; const search = async () => { try { setHits(await api.search(query, "camera-01", "part-A")); } catch (error) { onMessage(String(error)); } };
  return <section><PageIntro title="知识文档" description="将适用范围明确的 SOP 与技术手册纳入 Agent 只读检索。" /><div className="documents-grid"><div className="surface data-surface"><PanelHeader eyebrow="DOCUMENT INGESTION" title="上传技术手册" /><textarea value={content} onChange={(event) => setContent(event.target.value)} /><button className="primary-button" onClick={upload}>解析并入库</button></div><div className="surface data-surface"><PanelHeader eyebrow="RAG SEARCH" title="检索引用" /><div className="search-inline"><input value={query} onChange={(event) => setQuery(event.target.value)} /><button className="secondary-button" onClick={search}><Search size={15} />检索</button></div><div className="hits">{hits.map((hit) => <article key={String(hit.evidence_id)}><strong>{String(hit.title)} · v{String(hit.version)}</strong><span>{String(hit.section)} / page {String(hit.page)}</span><p>{String(hit.content)}</p></article>)}</div></div></div></section>;
}

function EmptyState({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <div className="empty-state"><span>{icon}</span><strong>{title}</strong><p>{text}</p></div>; }
function traceTitle(action: string) { const labels: Record<string, string> = { capture_snapshot: "冻结现场快照", inspect_metrics: "分析指标突变", compare_samples: "比对异常样本", search_knowledge_base: "检索知识与案例", draft_proposal: "生成排查建议", start: "接收异常 Case", finalize: "形成调研结论" }; return labels[action] ?? action.replaceAll("_", " "); }
