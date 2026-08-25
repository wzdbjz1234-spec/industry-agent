"""Phase 18 trace, redaction and Prometheus contract tests."""

from quality_case_agent.adapters.observability.otel import InMemoryTelemetry
from quality_case_agent.adapters.observability.prometheus import PrometheusMetrics


def test_trace_context_and_sensitive_attributes_are_redacted() -> None:
    telemetry = InMemoryTelemetry()
    with telemetry.operation(
        "investigation.run",
        attributes={"case_id": "case-1", "token": "do-not-store", "note": "api_key=secret"},
    ) as operation:
        trace_id = telemetry.current_trace_id
        operation.set_attribute("analysis.status", "COMPLETED")
        with telemetry.operation("investigation.tool", attributes={"case_id": "case-1"}):
            assert telemetry.current_trace_id == trace_id
    assert trace_id is not None
    assert len(telemetry.spans) == 2
    assert telemetry.spans[0].trace_id == telemetry.spans[1].trace_id
    assert "token" not in telemetry.spans[0].attributes
    assert telemetry.spans[0].attributes["note"] == "api_key=[REDACTED]"
    assert telemetry.spans[0].status == "OK"


def test_prometheus_metrics_use_low_cardinality_labels() -> None:
    metrics = PrometheusMetrics()
    metrics.record_worker("investigation", status="PROCESSED", duration_ms=25)
    metrics.record_analysis(
        status="INSUFFICIENT_EVIDENCE",
        provider="deterministic",
        model="offline-v1",
        duration_ms=100,
        tool_call_count=2,
        retrieval_call_count=1,
        estimated_tokens=200,
        estimated_cost_cny=0.01,
    )
    metrics.record_stream(stream="quality-events", consumer_group="investigation", pending=3, oldest_age_seconds=4.2)
    text = metrics.render().decode("utf-8")
    assert "worker_events_total" in text
    assert 'worker="investigation"' in text
    assert "analysis_abstention_total" in text
    assert "case_id" not in text


def test_api_exposes_prometheus_scrape_endpoint() -> None:
    import asyncio

    from httpx import ASGITransport, AsyncClient

    async def run() -> None:
        from quality_case_agent.entrypoints.api.app import create_app

        async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
            response = await client.get("/metrics")
            assert response.status_code == 200
            assert "worker_events_total" in response.text

    asyncio.run(run())
