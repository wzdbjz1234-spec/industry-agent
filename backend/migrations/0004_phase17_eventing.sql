-- Redis Streams owns delivery state; these indexes support durable Outbox
-- recovery and Inbox idempotency when the publisher/worker process restarts.
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished
    ON outbox_events (occurred_at) WHERE published_at IS NULL;
