"""Evidence grounding validator for structured Agent drafts."""

from dataclasses import dataclass

from quality_case_agent.contracts.investigation import (
    InvestigationAnalysisContract,
    ProposalContract,
)


@dataclass(frozen=True, slots=True)
class GroundingResult:
    valid: bool
    errors: tuple[str, ...]
    supported_evidence_ids: tuple[str, ...]


class EvidenceGroundingValidator:
    def validate(
        self,
        analysis: InvestigationAnalysisContract,
        proposal: ProposalContract | None,
    ) -> GroundingResult:
        evidence_by_id = {item.evidence_id: item for item in analysis.evidence}
        errors: list[str] = []
        supported: set[str] = set()
        for hypothesis in analysis.hypotheses:
            for evidence_id in hypothesis.supporting_evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    errors.append(f"hypothesis {hypothesis.hypothesis_id} references unknown evidence {evidence_id}")
                elif evidence.evidence_class == "C":
                    errors.append(f"historical C evidence cannot support hypothesis {hypothesis.hypothesis_id}")
                elif evidence.applicability == "NOT_APPLICABLE":
                    errors.append(
                        f"non-applicable evidence cannot support hypothesis {hypothesis.hypothesis_id}"
                    )
                elif hypothesis.hypothesis_id in evidence.contradicts:
                    errors.append(
                        f"evidence {evidence_id} contradicts hypothesis {hypothesis.hypothesis_id}"
                    )
                else:
                    supported.add(evidence_id)
            for evidence_id in hypothesis.contradicting_evidence_ids:
                if evidence_id not in evidence_by_id:
                    errors.append(f"hypothesis {hypothesis.hypothesis_id} contradicts unknown evidence {evidence_id}")
        if proposal is not None:
            for evidence_id in proposal.evidence_ids:
                if evidence_id not in evidence_by_id:
                    errors.append(f"proposal references unknown evidence {evidence_id}")
            classes = {evidence_by_id[evidence_id].evidence_class for evidence_id in proposal.evidence_ids if evidence_id in evidence_by_id}
            if "A" not in classes:
                errors.append("proposal requires current A evidence")
            if "B" not in classes:
                errors.append("proposal requires applicable B evidence")
            if any(
                evidence_by_id[evidence_id].evidence_class == "B"
                and evidence_by_id[evidence_id].applicability != "APPLICABLE"
                for evidence_id in proposal.evidence_ids
                if evidence_id in evidence_by_id
            ):
                errors.append("proposal B evidence must be marked APPLICABLE")
        return GroundingResult(not errors, tuple(errors), tuple(sorted(supported)))
