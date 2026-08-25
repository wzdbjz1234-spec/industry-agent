"""Low-cardinality Prometheus metrics for API and Worker operations."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class PrometheusMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.worker_events = Counter(
            "worker_events_total", "Worker event outcomes", ["worker", "status", "error_category"], registry=self.registry
        )
        self.worker_duration = Histogram(
            "worker_event_duration_seconds", "Worker event duration", ["worker"], registry=self.registry
        )
        self.stream_backlog = Gauge(
            "stream_backlog_count", "Unacknowledged stream deliveries", ["stream", "consumer_group"], registry=self.registry
        )
        self.stream_oldest_age = Gauge(
            "stream_oldest_pending_age_seconds", "Oldest pending delivery age", ["stream", "consumer_group"], registry=self.registry
        )
        self.outbox_unpublished = Gauge("outbox_unpublished_count", "Unpublished Outbox rows", registry=self.registry)
        self.analysis_runs = Counter(
            "analysis_runs_total", "Analysis run outcomes", ["status", "provider", "model"], registry=self.registry
        )
        self.analysis_duration = Histogram(
            "analysis_duration_seconds", "Analysis duration", ["provider", "model"], registry=self.registry
        )
        self.analysis_tool_calls = Counter(
            "analysis_tool_calls_total", "Analysis tool calls", ["tool", "status"], registry=self.registry
        )
        self.analysis_retrieval_calls = Counter(
            "analysis_retrieval_calls_total", "Analysis retrieval calls", ["status"], registry=self.registry
        )
        self.analysis_tokens = Counter(
            "analysis_tokens_total", "Estimated model tokens", ["provider", "model", "direction"], registry=self.registry
        )
        self.analysis_cost = Counter(
            "analysis_cost_cny_total", "Estimated analysis cost", ["provider", "model"], registry=self.registry
        )
        self.analysis_abstention = Counter(
            "analysis_abstention_total", "Analysis abstentions", ["reason"], registry=self.registry
        )
        self.qms_delivery = Counter(
            "qms_delivery_total", "QMS delivery outcomes", ["status", "error_category"], registry=self.registry
        )

    def record_worker(self, worker: str, *, status: str, duration_ms: int, error_category: str = "NONE") -> None:
        self.worker_events.labels(worker, status, error_category).inc()
        self.worker_duration.labels(worker).observe(max(0, duration_ms) / 1000)

    def record_analysis(self, *, status: str, provider: str, model: str, duration_ms: int,
                        tool_call_count: int, retrieval_call_count: int,
                        estimated_tokens: int, estimated_cost_cny: float) -> None:
        self.analysis_runs.labels(status, provider, model).inc()
        self.analysis_duration.labels(provider, model).observe(max(0, duration_ms) / 1000)
        self.analysis_tool_calls.labels("aggregate", status).inc(max(0, tool_call_count))
        self.analysis_retrieval_calls.labels(status).inc(max(0, retrieval_call_count))
        self.analysis_tokens.labels(provider, model, "total").inc(max(0, estimated_tokens))
        self.analysis_cost.labels(provider, model).inc(max(0.0, estimated_cost_cny))
        if status in {"INSUFFICIENT_EVIDENCE", "BUDGET_EXHAUSTED"}:
            self.analysis_abstention.labels(status).inc()

    def record_stream(self, *, stream: str, consumer_group: str, pending: int, oldest_age_seconds: float) -> None:
        self.stream_backlog.labels(stream, consumer_group).set(max(0, pending))
        self.stream_oldest_age.labels(stream, consumer_group).set(max(0.0, oldest_age_seconds))

    def render(self) -> bytes:
        return generate_latest(self.registry)
