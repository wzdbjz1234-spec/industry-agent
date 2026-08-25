"""Generic worker entrypoint seam; domain workers only supply handlers."""

from quality_case_agent.application.eventing.consumer import ReliableEventConsumer
from quality_case_agent.application.ports.event_bus import ConsumeResult, EventHandler


def run_once(consumer: ReliableEventConsumer, handler: EventHandler, *, limit: int = 10) -> ConsumeResult:
    return consumer.run_once(handler, limit=limit)
