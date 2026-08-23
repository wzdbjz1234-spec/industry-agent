"""Inspection batch ingestion use case."""

from dataclasses import dataclass

from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.contracts.inspection import InspectionResultBatchContract
from quality_case_agent.domain.inspection.models import (
    DefectRegion,
    DetectorMetadata,
    InspectionBatch,
    InspectionResult,
)


@dataclass(frozen=True, slots=True)
class IngestionReceipt:
    batch_message_id: str
    accepted_count: int
    duplicate_count: int


class InspectionIngestionService:
    """Convert a boundary contract and persist it through a port."""

    def __init__(self, store: InspectionResultStore) -> None:
        self._store = store

    def submit_batch(self, batch: InspectionResultBatchContract) -> IngestionReceipt:
        domain_batch = self._to_domain(batch)
        accepted_count, duplicate_count = self._store.insert_batch(domain_batch)
        return IngestionReceipt(
            batch_message_id=batch.batch_message_id,
            accepted_count=accepted_count,
            duplicate_count=duplicate_count,
        )

    @staticmethod
    def _to_domain(batch: InspectionResultBatchContract) -> InspectionBatch:
        records = []
        for record in batch.records:
            region = record.defect_region
            records.append(
                InspectionResult(
                    result_id=record.result_id,
                    inspected_at=record.inspected_at,
                    factory_id=record.factory_id,
                    line_id=record.line_id,
                    station_id=record.station_id,
                    product_id=record.product_id,
                    unit_id=record.unit_id,
                    batch_id=record.batch_id,
                    is_ng=record.is_ng,
                    anomaly_score=record.anomaly_score,
                    threshold=record.threshold,
                    defect_type=record.defect_type,
                    defect_region=(
                        DefectRegion(
                            x_normalized=region.x_normalized,
                            y_normalized=region.y_normalized,
                            area_ratio=region.area_ratio,
                            region_label=region.region_label,
                        )
                        if region is not None
                        else None
                    ),
                    image_uri=record.image_uri,
                    anomaly_map_uri=record.anomaly_map_uri,
                    detector=DetectorMetadata(
                        detector_type=record.detector.type,
                        model_version=record.detector.model_version,
                        adapter_version=record.detector.adapter_version,
                    ),
                    metadata=record.metadata,
                )
            )
        return InspectionBatch(
            batch_message_id=batch.batch_message_id,
            producer_id=batch.producer_id,
            produced_at=batch.produced_at,
            records=tuple(records),
        )
