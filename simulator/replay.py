"""Replay orchestration helpers."""

from collections.abc import Iterator
from datetime import datetime

from quality_case_agent.adapters.detector.replay import ReplayDetectorAdapter
from quality_case_agent.contracts.inspection import InspectionResultBatchContract

from simulator.scenarios import ScenarioName, generate_scenario_batches


def scenario_replay(
    scenario: ScenarioName | str,
    *,
    seed: int = 7,
    batch_size: int = 10,
    start_at: datetime | None = None,
    replay_id: str | None = None,
) -> Iterator[InspectionResultBatchContract]:
    """Yield a deterministic scenario through the replaceable detector adapter."""

    adapter = ReplayDetectorAdapter(
        generate_scenario_batches(
            scenario,
            seed=seed,
            batch_size=batch_size,
            **({"start_at": start_at} if start_at is not None else {}),
            replay_id=replay_id,
        )
    )
    yield from adapter.iter_batches()
