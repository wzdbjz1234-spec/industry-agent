-- Phase 5–7 logical migration reference.
-- The production Alembic adapter should apply this DDL with the deployment's PostgreSQL version.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    version VARCHAR(64) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    applicability JSONB NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    content_sha256 CHAR(64) NOT NULL UNIQUE,
    chunk_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    evidence_id VARCHAR(192) PRIMARY KEY,
    document_id VARCHAR(128) NOT NULL REFERENCES knowledge_documents(document_id),
    section VARCHAR(128) NOT NULL,
    page INTEGER,
    content TEXT NOT NULL,
    embedding vector(32) NOT NULL
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS investigation_runs (
    analysis_run_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    snapshot_id VARCHAR(128) NOT NULL,
    trigger_event_id VARCHAR(128) NOT NULL,
    idempotency_key VARCHAR(512) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    proposal_id VARCHAR(128),
    trace_event_count INTEGER NOT NULL DEFAULT 0,
    error_summary VARCHAR(512)
);

CREATE TABLE IF NOT EXISTS investigation_proposals (
    proposal_id VARCHAR(128) PRIMARY KEY,
    case_id VARCHAR(128) NOT NULL,
    analysis_run_id VARCHAR(128) NOT NULL,
    version INTEGER NOT NULL,
    original_proposal_id VARCHAR(128),
    status VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS proposal_decisions (
    decision_id VARCHAR(128) PRIMARY KEY,
    proposal_id VARCHAR(128) NOT NULL,
    case_id VARCHAR(128) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    decided_by VARCHAR(128) NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);
