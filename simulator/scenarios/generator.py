"""Fixed-seed synthetic inspection scenarios for Phase 2."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from random import Random

from quality_case_agent.contracts.inspection import (
    DefectRegionContract,
    DetectorContract,
    InspectionResultBatchContract,
    InspectionResultContract,
)


class ScenarioName(StrEnum):
    NORMAL = "normal"
    FIXTURE_OFFSET = "fixture_offset"
    ILLUMINATION_DRIFT = "illumination_drift"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("start_at must include a timezone")
    return value.astimezone(UTC)


def _region(label: str) -> DefectRegionContract:
    coordinates = {
        "upper_right": (0.72, 0.24),
        "upper_left": (0.24, 0.24),
        "lower_right": (0.72, 0.76),
        "lower_left": (0.24, 0.76),
        "center": (0.50, 0.50),
    }
    x_normalized, y_normalized = coordinates[label]
    return DefectRegionContract(
        x_normalized=x_normalized,
        y_normalized=y_normalized,
        area_ratio=0.08,
        region_label=label,
    )


def _scenario_result(
    scenario: ScenarioName,
    minute: int,
    position: int,
    inspected_at: datetime,
    rng: Random,
    seed: int,
    replay_id: str | None = None,
) -> InspectionResultContract:
    if scenario is ScenarioName.NORMAL:
        is_ng = rng.random() < 0.05
        region_label = rng.choice(["upper_left", "upper_right", "lower_left", "lower_right"])
        score = 0.78 if is_ng else 0.18 + rng.random() * 0.18
    elif scenario is ScenarioName.FIXTURE_OFFSET:
        abnormal = 2 <= minute <= 4
        recovery = minute >= 5
        is_ng = position < 6 if abnormal else (position == 0 and recovery)
        region_label = "upper_right" if abnormal else "lower_left"
        score = 0.84 if is_ng else 0.20 + rng.random() * 0.12
    elif scenario is ScenarioName.ILLUMINATION_DRIFT:
        abnormal = 2 <= minute <= 5
        is_ng = position < 5 if abnormal else position == 0
        region_label = ["upper_left", "upper_right", "lower_left", "lower_right", "center"][
            position % 5
        ]
        score = 0.76 if is_ng else 0.28 + rng.random() * 0.18
    else:
        is_ng = minute == 1 and position == 0
        region_label = "upper_right"
        score = 0.82 if is_ng else 0.22

    result_prefix = f"{scenario.value}-{replay_id}" if replay_id else scenario.value
    result_id = f"ir-{result_prefix}-{minute:02d}-{position:02d}"
    return InspectionResultContract(
        result_id=result_id,
        inspected_at=inspected_at,
        factory_id="factory-01",
        line_id="line-01",
        station_id="camera-01",
        product_id="part-A",
        unit_id=f"unit-{result_prefix}-{minute:02d}-{position:02d}",
        batch_id=f"batch-{result_prefix}-{minute:02d}",
        is_ng=is_ng,
        anomaly_score=score,
        threshold=0.50,
        defect_type="surface_anomaly" if is_ng else None,
        defect_region=_region(region_label) if is_ng else None,
        image_uri=(
            f"s3://inspection/simulated/{scenario.value}/{result_id}.png" if is_ng else None
        ),
        anomaly_map_uri=(
            f"s3://inspection/simulated/{scenario.value}/{result_id}-map.png" if is_ng else None
        ),
        detector=DetectorContract(
            type="efficientad-compatible",
            model_version=(
                "sim-detector-legacy-0.9"
                if scenario is ScenarioName.INSUFFICIENT_EVIDENCE and position == 1
                else "sim-detector-1.0"
            ),
            adapter_version="replay-1.0",
        ),
        metadata={"simulated": True, "scenario": scenario.value, "seed": seed},
    )


def generate_scenario_batches(
    scenario: ScenarioName | str,
    *,
    seed: int = 7,
    start_at: datetime = datetime(2026, 8, 22, 2, 0, tzinfo=UTC),
    batch_size: int = 10,
    replay_id: str | None = None,
) -> tuple[InspectionResultBatchContract, ...]:
    """Generate deterministic batches with the same contract as a detector adapter."""

    scenario_name = ScenarioName(scenario)
    if batch_size < 1 or batch_size > 100:
        raise ValueError("batch_size must be between 1 and 100")
    start_at = _ensure_utc(start_at)
    rng = Random(seed)
    minutes = 7 if scenario_name is ScenarioName.FIXTURE_OFFSET else 6
    positions_per_minute = 2 if scenario_name is ScenarioName.INSUFFICIENT_EVIDENCE else 10
    results: list[InspectionResultContract] = []
    for minute in range(minutes):
        for position in range(positions_per_minute):
            inspected_at = start_at + timedelta(minutes=minute, seconds=position * 5)
            results.append(
                _scenario_result(
                    scenario_name,
                    minute,
                    position,
                    inspected_at,
                    rng,
                    seed,
                    replay_id,
                )
            )

    batches: list[InspectionResultBatchContract] = []
    for batch_number, offset in enumerate(range(0, len(results), batch_size), start=1):
        records = results[offset : offset + batch_size]
        batches.append(
            InspectionResultBatchContract(
                batch_message_id=(
                    f"ib-{scenario_name.value}-{replay_id}-{batch_number:04d}"
                    if replay_id
                    else f"ib-{scenario_name.value}-{batch_number:04d}"
                ),
                producer_id=(
                    f"replay-{scenario_name.value}-{replay_id}"
                    if replay_id
                    else f"replay-{scenario_name.value}"
                ),
                produced_at=records[-1].inspected_at,
                records=records,
            )
        )
    return tuple(batches)
