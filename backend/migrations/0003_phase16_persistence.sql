-- Phase 16 durable state. The SQLAlchemy adapter creates the same tables for
-- SQLite CI and PostgreSQL runtime; this migration documents the deploy shape.
-- JSON payloads preserve the canonical domain snapshot while indexed columns
-- provide idempotency and deterministic ordering.

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id VARCHAR(256) PRIMARY KEY,
    event_type VARCHAR(256) NOT NULL,
    aggregate_id VARCHAR(128),
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS inbox_events (
    consumer_group VARCHAR(128) NOT NULL,
    event_id VARCHAR(256) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (consumer_group, event_id)
);
