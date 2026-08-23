"""Versioned contracts for offline Agent evaluation and illustrative ROI math."""

from typing import Literal

from pydantic import Field

from .common import ContractModel


class EvaluationConfigContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    config_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=64)
    tool_version: str = Field(min_length=1, max_length=64)
    max_iterations: int = Field(default=8, ge=1, le=20)


class EvaluationScenarioContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str = Field(min_length=1, max_length=64)
    dataset_version: str = Field(min_length=1, max_length=64)
    scenario: Literal["fixture_offset", "illumination_drift", "insufficient_evidence"]
    seed: int = Field(ge=0)
    required_tools: list[str] = Field(min_length=1, max_length=20)
    expected_status: Literal["COMPLETED", "INSUFFICIENT_EVIDENCE"]
    expected_hypothesis_id: str | None = Field(default=None, max_length=64)
    expected_required_information: list[str] = Field(default_factory=list, max_length=20)
    forbid_hypotheses: bool = False
    hidden_truth: dict[str, str] = Field(default_factory=dict, max_length=20)


class EvaluationCaseResultContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    config_id: str
    dataset_version: str
    run_fingerprint: str
    status: str
    passed: bool
    schema_valid: bool
    required_tool_coverage: float = Field(ge=0.0, le=1.0)
    evidence_reference_coverage: float = Field(ge=0.0, le=1.0)
    applicability_accuracy: float = Field(ge=0.0, le=1.0)
    safety_stop_correct: bool
    forbidden_conclusion_violations: int = Field(default=0, ge=0)
    tool_call_count: int = Field(ge=0)
    retrieval_call_count: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    estimated_cost_cny: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    time_to_first_analysis_ms: int = Field(ge=0)
    failure_reasons: list[str] = Field(default_factory=list, max_length=20)


class EvaluationReportContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    dataset_version: str
    repeat_index: int = Field(ge=1)
    config: EvaluationConfigContract
    cases: list[EvaluationCaseResultContract] = Field(min_length=1, max_length=100)
    summary: dict[str, float | int | str]


class ROICalculationRequestContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    cases_per_day: float = Field(default=8.0, ge=0.0)
    production_days_per_year: float = Field(default=250.0, ge=0.0)
    manual_triage_minutes: float = Field(default=30.0, ge=0.0)
    assisted_review_minutes: float = Field(default=8.0, ge=0.0)
    labor_cost_per_hour_cny: float = Field(default=150.0, ge=0.0)
    cost_per_analysis_cny: float = Field(default=0.80, ge=0.0)
    annual_infrastructure_cost_cny: float = Field(default=20_000.0, ge=0.0)
    initial_investment_cny: float = Field(default=120_000.0, ge=0.0)
    avoided_downtime_cny: float = Field(default=0.0, ge=0.0)
    avoided_scrap_cny: float = Field(default=0.0, ge=0.0)
    reuse_value_cny: float = Field(default=0.0, ge=0.0)


class ROICalculationContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    classification: Literal["ILLUSTRATIVE"] = "ILLUSTRATIVE"
    annual_cases: float
    annual_labor_hours_saved: float
    annual_benefit_cny: float
    annual_cost_cny: float
    annual_net_benefit_cny: float
    roi_percent: float | None
    payback_months: float | None
    assumptions: dict[str, float]
    disclaimer: str = "示例测算：金额为 Illustrative，不代表真实客户收益。"
