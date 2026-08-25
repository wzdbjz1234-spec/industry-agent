const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

export type Evidence = {
  evidence_id: string;
  evidence_class: "A" | "B" | "C";
  evidence_type: string;
  reference: string;
  claim: string;
};

export type Proposal = {
  proposal_id: string;
  case_id: string;
  title: string;
  reason: string;
  version: number;
  status: string;
  steps: Array<{ order: number; instruction: string; expected_evidence: string }>;
  evidence_ids: string[];
};

export type AnalysisRun = {
  analysis_run_id: string;
  case_id: string;
  snapshot_id: string;
  status: string;
  trace_event_count: number;
  proposal_id?: string;
  summary?: string;
  termination_reason?: string;
  required_information?: string[];
  evidence_classes?: string[];
};

export type AgentTraceEvent = {
  sequence: number;
  event_type: "STARTED" | "TOOL_CALL" | "TOOL_RESULT" | "FINAL" | "TERMINATED";
  iteration: number;
  action: string;
  arguments: Record<string, unknown>;
  summary: string;
  duration_ms?: number | null;
  evidence_ids: string[];
};

export type Hypothesis = {
  hypothesis_id: string;
  title: string;
  description: string;
  confidence: number;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  missing_evidence: string[];
};

export type AnalysisOutput = {
  analysis: {
    analysis_run_id: string;
    case_id: string;
    snapshot_id: string;
    status: string;
    summary: string;
    evidence: Evidence[];
    hypotheses: Hypothesis[];
    limitations: string[];
    required_information: string[];
    termination_reason: string;
  };
  proposal?: Proposal | null;
  trace: { analysis_run_id: string; events: AgentTraceEvent[] };
};

export type VisionEvent = {
  event_id: string;
  event_type: string;
  occurred_at: string;
  frame_id?: string;
  fault_kind?: string;
  detector_type?: string;
  model_version?: string;
  anomaly_score?: number | null;
  threshold?: number | null;
  details?: Record<string, string | number | boolean>;
};

export type VisionStatus = {
  worker: string;
  running: boolean;
  queued: number;
  completed: number;
  failed: number;
  registered_schemes: string[];
};

export type WorkerStatus = {
  worker: string;
  processed: number;
  failed: number;
  pending: number;
  dlq: number;
  error_count: number;
  avg_latency_ms: number;
  last_error_type?: string | null;
  last_error?: string | null;
  last_event_id?: string | null;
  last_processed_at?: string | null;
};

export type DeliveryRecord = {
  event_id: string;
  event_type: string;
  case_id: string;
  consumer_group: string;
  attempts: number;
  state: "PENDING" | "PROCESSED" | "DLQ";
  last_error?: string | null;
  last_error_type?: string | null;
  last_error_at?: string | null;
  updated_at: string;
};

export type TimelineEntry = {
  event_id: string;
  event_type: string;
  occurred_at: string;
  case_id?: string | null;
  trace_id?: string | null;
  source: string;
  state?: string | null;
  summary: string;
};

export type EvaluationCaseResult = {
  scenario_id: string;
  passed: boolean;
  status: string;
  required_tool_coverage: number;
  evidence_reference_coverage: number;
  safety_stop_correct: boolean;
  tool_call_count: number;
  estimated_tokens: number;
  estimated_cost_cny: number;
  latency_ms: number;
  failure_reasons: string[];
};

export type EvaluationReport = {
  report_id: string;
  dataset_version: string;
  config: { config_id: string; prompt_version: string; model: string; tool_version: string };
  cases: EvaluationCaseResult[];
  summary: Record<string, number | string>;
};

export type RoiResult = {
  classification: "ILLUSTRATIVE";
  annual_benefit_cny: number;
  annual_cost_cny: number;
  annual_net_benefit_cny: number;
  roi_percent: number | null;
  payback_months: number | null;
  annual_labor_hours_saved: number;
  disclaimer: string;
};

export type QmsTask = {
  task_id: string;
  case_id: string;
  proposal_id: string;
  external_system: string;
  status: "OPEN" | "IN_PROGRESS" | "CLOSED";
  assignee_role: string;
  created_by: string;
  created_at: string;
  task_uri: string;
};

export type QualityCase = {
  case_id: string;
  case_status: string;
  episode_status: string;
  proposal_id?: string | null;
  qms_task_id?: string | null;
  qms_task_uri?: string | null;
  qms_task_status?: string | null;
  qms_external_system?: string | null;
};

export type VerifiedCase = {
  document_id: string;
  text: string;
  metadata: Record<string, string>;
  content_sha256: string;
  archive_uri?: string | null;
};

export type MonitoringSignal = {
  signal_type: "EWMA" | "CUSUM" | "PSI" | "KS" | "DATA_QUALITY";
  statistic: number;
  threshold: number;
  severity: "INFO" | "WARNING" | "HIGH" | "CRITICAL";
  message: string;
};

export type MonitoringDecision = {
  decision_id: string;
  evaluated_at: string;
  dimension_key: [string, string, string, string];
  model_version: string;
  window_start: string;
  status: "NORMAL" | "PROCESS_SHIFT" | "MODEL_DRIFT" | "DATA_QUALITY_BLOCK" | "BASELINE_MISSING";
  severity: "INFO" | "WARNING" | "HIGH" | "CRITICAL";
  action: "NONE" | "OPEN_CASE" | "MERGE_CASE" | "BLOCK";
  baseline_version?: string | null;
  signals: MonitoringSignal[];
  data_quality_warnings: string[];
  cooldown_minutes: number;
};

export type MonitoringReport = {
  schema_version: "1.0";
  evaluated_at: string;
  window_count: number;
  baseline_count: number;
  decisions: MonitoringDecision[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export const api = {
  pending: () => request<Proposal[]>("/proposals/pending"),
  runs: () => request<AnalysisRun[]>("/analysis/runs"),
  analysisOutput: (analysisRunId: string) => request<AnalysisOutput>(`/analysis/runs/${encodeURIComponent(analysisRunId)}`),
  visionEvents: () => request<VisionEvent[]>("/vision/events"),
  visionStatus: () => request<VisionStatus>("/vision/status"),
  visionSchemes: () => request<{ registered: string[]; default_input: string; anomlib_input: string }>("/vision/schemes"),
  cases: () => request<QualityCase[]>("/cases"),
  caseLibrary: () => request<VerifiedCase[]>("/case-library"),
  qmsTasks: () => request<{ items: QmsTask[] }>("/qms/tasks"),
  seedDemo: () => request<Record<string, unknown>>("/demo/fixture-offset", { method: "POST" }),
  seedRepeatDemo: () => request<Record<string, unknown>>("/demo/fixture-offset/repeat", { method: "POST" }),
  seedIlluminationDemo: () => request<Record<string, unknown>>("/demo/illumination-drift", { method: "POST" }),
  seedInsufficientDemo: () => request<Record<string, unknown>>("/demo/insufficient-evidence", { method: "POST" }),
  replayPublicDataset: (payload: { dataset: "MVTec AD" | "VisA" | "BTAD"; category: string; model: "EfficientAD" | "PatchCore" | "PaDiM" | "DRAEM"; seed: number; fps: number }) =>
    request<Record<string, unknown>>("/demo/public-dataset-replay", { method: "POST", body: JSON.stringify(payload) }),
  workers: () => request<{ workers: WorkerStatus[]; qms_pending: number; qms_dlq: number; qms_processed: number }>("/operations/workers"),
  delivery: () => request<{ pending: DeliveryRecord[]; processed: DeliveryRecord[]; dlq: DeliveryRecord[] }>("/operations/delivery"),
  timeline: (caseId?: string) => request<TimelineEntry[]>(`/operations/timeline${caseId ? `?case_id=${encodeURIComponent(caseId)}` : ""}`),
  retryPending: () => request<unknown[]>("/operations/retry-pending", { method: "POST", headers: { "X-Operator-Id": "web-operator" } }),
  retryDlq: (eventId: string) => request<unknown>(`/operations/retry-dlq/${encodeURIComponent(eventId)}`, { method: "POST", headers: { "X-Operator-Id": "web-operator" } }),
  evaluationReports: () => request<EvaluationReport[]>("/evaluation/reports"),
  runEvaluationMatrix: () => request<EvaluationReport[]>("/evaluation/matrix", { method: "POST", body: JSON.stringify([
    { config_id: "baseline", model: "deterministic-investigation-1", prompt_version: "prompt-v1", tool_version: "readonly-tools-v2", max_iterations: 8 },
    { config_id: "safe-v2", model: "deterministic-investigation-1", prompt_version: "prompt-v2", tool_version: "readonly-tools-v2", max_iterations: 8 },
  ]) }),
  roi: (payload: Record<string, number>) => request<RoiResult>("/roi/calculate", { method: "POST", body: JSON.stringify(payload) }),
  search: (query: string, stationId: string, productId: string) =>
    request<Array<Record<string, unknown>>>(
      `/knowledge/search?query=${encodeURIComponent(query)}&station_id=${encodeURIComponent(stationId)}&product_id=${encodeURIComponent(productId)}`,
    ),
  upload: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/knowledge/documents/upload", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  monitoringHealth: (windowMinutes = 1) => request<MonitoringReport>(`/monitoring/health?window_minutes=${windowMinutes}`),
  buildMonitoringBaseline: (windowMinutes = 1, baselineVersion = "web-v1") =>
    request<{ baseline_count: number; baselines: Array<Record<string, unknown>> }>(
      `/monitoring/baseline?window_minutes=${windowMinutes}&baseline_version=${encodeURIComponent(baselineVersion)}`,
      { method: "POST" },
    ),
  decide: (proposal: Proposal, decision: "APPROVE" | "REJECT") =>
    request<Record<string, unknown>>(`/proposals/${proposal.proposal_id}/decisions`, {
      method: "POST",
      body: JSON.stringify({
        decision_id: crypto.randomUUID(),
        proposal_id: proposal.proposal_id,
        case_id: proposal.case_id,
        decision,
        decided_by: "web-demo-user",
        decided_at: new Date().toISOString(),
        comment: decision === "REJECT" ? "需要补充现场证据" : "批准排查步骤",
      }),
    }),
};
