"""Parameterised ROI calculator with an explicit illustrative boundary."""

from quality_case_agent.contracts.evaluation import (
    ROICalculationContract,
    ROICalculationRequestContract,
)


def calculate_roi(request: ROICalculationRequestContract) -> ROICalculationContract:
    annual_cases = request.cases_per_day * request.production_days_per_year
    minutes_saved = max(0.0, request.manual_triage_minutes - request.assisted_review_minutes)
    annual_labor_hours_saved = minutes_saved / 60.0 * annual_cases
    labor_benefit = annual_labor_hours_saved * request.labor_cost_per_hour_cny
    annual_benefit = labor_benefit + request.avoided_downtime_cny + request.avoided_scrap_cny + request.reuse_value_cny
    annual_cost = annual_cases * request.cost_per_analysis_cny + request.annual_infrastructure_cost_cny
    annual_net = annual_benefit - annual_cost
    roi_percent = (
        (annual_net - request.initial_investment_cny) / request.initial_investment_cny * 100.0
        if request.initial_investment_cny > 0
        else None
    )
    payback_months = (
        request.initial_investment_cny / annual_net * 12.0 if annual_net > 0 else None
    )
    return ROICalculationContract(
        annual_cases=round(annual_cases, 2),
        annual_labor_hours_saved=round(annual_labor_hours_saved, 2),
        annual_benefit_cny=round(annual_benefit, 2),
        annual_cost_cny=round(annual_cost, 2),
        annual_net_benefit_cny=round(annual_net, 2),
        roi_percent=round(roi_percent, 2) if roi_percent is not None else None,
        payback_months=round(payback_months, 2) if payback_months is not None else None,
        assumptions={
            "cases_per_day": request.cases_per_day,
            "production_days_per_year": request.production_days_per_year,
            "manual_triage_minutes": request.manual_triage_minutes,
            "assisted_review_minutes": request.assisted_review_minutes,
            "labor_cost_per_hour_cny": request.labor_cost_per_hour_cny,
            "cost_per_analysis_cny": request.cost_per_analysis_cny,
            "annual_infrastructure_cost_cny": request.annual_infrastructure_cost_cny,
            "initial_investment_cny": request.initial_investment_cny,
        },
    )
