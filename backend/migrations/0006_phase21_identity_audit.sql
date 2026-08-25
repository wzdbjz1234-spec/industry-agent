-- Phase 21 identity and tamper-evident append-only audit records.
CREATE TABLE IF NOT EXISTS audit_events (
    event_id VARCHAR(160) PRIMARY KEY,
    event_type VARCHAR(128) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    roles JSONB NOT NULL,
    organization VARCHAR(256) NOT NULL,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(128) NOT NULL,
    resource_id VARCHAR(160) NOT NULL,
    correlation_id VARCHAR(160) NOT NULL,
    causation_id VARCHAR(160),
    trace_id VARCHAR(160),
    policy_version VARCHAR(64) NOT NULL,
    claims_digest VARCHAR(128) NOT NULL,
    metadata JSONB NOT NULL,
    previous_hash VARCHAR(128),
    event_hash VARCHAR(128) NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_audit_events_resource
    ON audit_events (resource_type, resource_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor
    ON audit_events (actor_id, occurred_at DESC);
