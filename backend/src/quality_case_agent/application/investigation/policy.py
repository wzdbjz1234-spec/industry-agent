"""Safety policy for turning a grounded draft into a public result."""

from dataclasses import dataclass

from .grounding import GroundingResult


@dataclass(frozen=True, slots=True)
class InvestigationPolicyDecision:
    allow_hypotheses: bool
    allow_proposal: bool
    status_override: str | None
    required_information: tuple[str, ...]
    limitations: tuple[str, ...]


class InvestigationSafetyPolicy:
    def decide(
        self,
        *,
        data_quality_warnings: tuple[str, ...],
        grounding: GroundingResult,
        complete: bool,
    ) -> InvestigationPolicyDecision:
        if data_quality_warnings:
            return InvestigationPolicyDecision(
                allow_hypotheses=False,
                allow_proposal=False,
                status_override="INSUFFICIENT_EVIDENCE",
                required_information=tuple(self._required_information(data_quality_warnings)),
                limitations=("数据质量检查阻断了根因分析，Agent 未生成确定性根因或行动 Proposal。",),
            )
        if not grounding.valid:
            return InvestigationPolicyDecision(
                allow_hypotheses=False,
                allow_proposal=False,
                status_override="INSUFFICIENT_EVIDENCE",
                required_information=(),
                limitations=("Evidence Grounding Validator 拒绝了未被当前证据支持的草案。", *grounding.errors),
            )
        return InvestigationPolicyDecision(
            allow_hypotheses=complete,
            allow_proposal=complete,
            status_override=None,
            required_information=(),
            limitations=(),
        )

    @staticmethod
    def _required_information(warnings: tuple[str, ...]) -> list[str]:
        result: list[str] = []
        if "INSUFFICIENT_SAMPLE_COUNT" in warnings:
            result.append("统一模型版本后的至少500条检测记录")
        if "MIXED_MODEL_VERSIONS" in warnings:
            result.append("统一模型版本后的检测记录")
        if "DATA_MISSING" in warnings:
            result.append("补齐原始检测记录与图像URI")
        return result
