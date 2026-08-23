"""Investigation worker entry boundary for a Redis/Stream consumer replacement."""

from quality_case_agent.application.investigation.service import InvestigationService
from quality_case_agent.contracts.investigation import InvestigationOutputContract
from quality_case_agent.contracts.quality_case import QualityCaseOpenedEventContract


class InvestigationWorker:
    """Validate one Case-opened message before handing it to the application service."""

    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def handle(self, message: dict[str, object]) -> InvestigationOutputContract:
        event = QualityCaseOpenedEventContract.model_validate(message)
        return self._service.handle_case_opened(event)
