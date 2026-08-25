"""Worker entrypoint seam for publishing committed Outbox rows."""

from quality_case_agent.application.eventing.publisher import OutboxPublisher


def run_once(publisher: OutboxPublisher, *, limit: int = 100) -> int:
    return publisher.run_once(limit=limit)
