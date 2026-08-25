-- Phase 19 immutable baseline snapshots, keyed by dimension and detector model.
CREATE TABLE IF NOT EXISTS monitoring_baselines (
    baseline_key VARCHAR(512) PRIMARY KEY,
    dimension_key VARCHAR(512) NOT NULL,
    model_version VARCHAR(128) NOT NULL,
    baseline_version VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_monitoring_baselines_dimension
    ON monitoring_baselines (dimension_key, model_version, baseline_version);
