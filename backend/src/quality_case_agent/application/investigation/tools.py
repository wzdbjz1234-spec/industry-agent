"""Allowlisted, read-only quality and knowledge tools."""

from datetime import datetime

from quality_case_agent.application.ports.change_log import ChangeLogPort
from quality_case_agent.application.ports.equipment import EquipmentPort
from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.application.ports.knowledge import KnowledgeBase
from quality_case_agent.application.ports.metrics import QualityMetricsStore
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.domain.investigation.models import ToolObservation
from quality_case_agent.domain.knowledge.models import KnowledgeSearchQuery
from quality_case_agent.domain.quality_case.models import QualityCase


class ReadOnlyInvestigationTools:
    """Expose a small, validated tool surface to the investigation Agent."""

    def __init__(
        self,
        case_store: QualityCaseStore,
        metrics_store: QualityMetricsStore,
        knowledge_base: KnowledgeBase,
        inspection_store: InspectionResultStore | None = None,
        equipment: EquipmentPort | None = None,
        change_log: ChangeLogPort | None = None,
    ) -> None:
        self._case_store = case_store
        self._metrics_store = metrics_store
        self._knowledge_base = knowledge_base
        self._inspection_store = inspection_store
        self._equipment = equipment
        self._change_log = change_log

    @property
    def names(self) -> tuple[str, ...]:
        names = ["get_case_snapshot", "compare_quality_metrics"]
        names.append("check_data_quality")
        if self._inspection_store is not None:
            names.append("get_representative_samples")
        if self._equipment is not None:
            names.append("get_equipment_state")
        if self._change_log is not None:
            names.append("get_change_log")
        names.append("search_knowledge_base")
        return tuple(names)

    def invoke(self, name: str, arguments: dict[str, object]) -> ToolObservation:
        if name not in self.names:
            return ToolObservation(name, False, "工具不在只读 allowlist 中", {})
        try:
            if name == "get_case_snapshot":
                return self.get_case_snapshot(arguments)
            if name == "compare_quality_metrics":
                return self.compare_quality_metrics(arguments)
            if name == "check_data_quality":
                return self.check_data_quality(arguments)
            if name == "get_representative_samples":
                return self.get_representative_samples(arguments)
            if name == "get_equipment_state":
                return self.get_equipment_state(arguments)
            if name == "get_change_log":
                return self.get_change_log(arguments)
            return self.search_knowledge_base(arguments)
        except (KeyError, TypeError, ValueError) as exc:
            return ToolObservation(name, False, f"参数或数据错误：{exc}", {})

    def get_case_snapshot(self, arguments: dict[str, object]) -> ToolObservation:
        case_id = self._required_string(arguments, "case_id")
        snapshot_id = self._required_string(arguments, "snapshot_id")
        case = self._case_store.get_case(case_id)
        if case is None:
            raise KeyError(f"case not found: {case_id}")
        if case.snapshot.snapshot_id != snapshot_id:
            raise ValueError("snapshot_id does not match the Case")
        payload = case.snapshot.as_dict()
        payload["station_id"] = case.snapshot.observations[0].station_id
        payload["product_id"] = case.snapshot.observations[0].product_id
        return ToolObservation(
            "get_case_snapshot",
            True,
            "返回不可变 Snapshot 摘要",
            payload,
            (case.snapshot.snapshot_id,),
        )

    def compare_quality_metrics(self, arguments: dict[str, object]) -> ToolObservation:
        snapshot_id = self._required_string(arguments, "snapshot_id")
        case = self._case_for_snapshot(snapshot_id)
        windows = case.snapshot.observations
        if not windows:
            raise ValueError("snapshot has no observations")
        first = windows[0]
        latest = windows[-1]
        payload: dict[str, object] = {
            "snapshot_id": snapshot_id,
            "window_count": len(windows),
            "baseline": first.as_dict(),
            "latest": latest.as_dict(),
            "delta": {
                "ng_rate": latest.ng_rate - first.ng_rate,
                "score_mean": latest.score_mean - first.score_mean,
                "upper_right_share": latest.upper_right_share - first.upper_right_share,
            },
            "stored_metric_window_count": len(self._metrics_store.list_windows()),
        }
        return ToolObservation(
            "compare_quality_metrics",
            True,
            "返回 Snapshot 内首末窗口的指标差异",
            payload,
            (snapshot_id,),
        )

    def check_data_quality(self, arguments: dict[str, object]) -> ToolObservation:
        snapshot_id = self._required_string(arguments, "snapshot_id")
        case = self._case_for_snapshot(snapshot_id)
        warnings = list(case.snapshot.data_quality_warnings)
        required_information: list[str] = []
        if "INSUFFICIENT_SAMPLE_COUNT" in warnings:
            required_information.append("统一模型版本后的至少500条检测记录")
        if "MIXED_MODEL_VERSIONS" in warnings:
            required_information.append("统一模型版本后的检测记录")
        if "DATA_MISSING" in warnings:
            required_information.append("补齐原始检测记录与图像URI")
        blocked = bool(warnings)
        return ToolObservation(
            "check_data_quality",
            True,
            "数据质量不足，停止根因分析" if blocked else "数据质量检查通过",
            {
                "snapshot_id": snapshot_id,
                "blocked": blocked,
                "warnings": warnings,
                "required_information": required_information,
            },
            (snapshot_id,),
        )

    def search_knowledge_base(self, arguments: dict[str, object]) -> ToolObservation:
        query = self._required_string(arguments, "query")
        raw_source_types = arguments.get("source_types", ())
        if not isinstance(raw_source_types, (list, tuple)):
            raise TypeError("source_types must be a list")
        source_types = tuple(self._string_value(value, "source_type") for value in raw_source_types)
        raw_filters = arguments.get("filters", {})
        if not isinstance(raw_filters, dict):
            raise TypeError("filters must be an object")
        filters = {
            self._string_value(key, "filter key"): self._string_value(value, "filter value")
            for key, value in raw_filters.items()
        }
        top_k = arguments.get("top_k", 5)
        if not isinstance(top_k, int):
            raise TypeError("top_k must be an integer")
        snapshot = self._case_for_snapshot(self._required_string(arguments, "snapshot_id"))
        hits = self._knowledge_base.search(
            KnowledgeSearchQuery(
                query=query,
                source_types=source_types,
                filters=filters,
                top_k=top_k,
                effective_at=snapshot.snapshot.created_at,
            )
        )
        items = [
            {
                "evidence_id": hit.chunk.evidence_id,
                "document_id": hit.chunk.document_id,
                "title": hit.chunk.title,
                "version": hit.chunk.version,
                "source_type": hit.chunk.source_type,
                "section": hit.chunk.section,
                "page": hit.chunk.page,
                "content": hit.chunk.content,
                "retrieval_score": hit.score,
                "applicability": "APPLICABLE",
                "applicability_reasons": list(hit.applicability_reasons),
                "source_metadata": dict(hit.chunk.applicability),
                "archive_uri": hit.chunk.applicability.get("archive_uri"),
                "historical_case_disclaimer": (
                    "历史案例只能作为C级经验，不能证明当前Case的根因。"
                    if hit.chunk.source_type == "VERIFIED_CASE"
                    else None
                ),
            }
            for hit in hits
        ]
        historical_count = sum(item["source_type"] == "VERIFIED_CASE" for item in items)
        return ToolObservation(
            "search_knowledge_base",
            True,
            f"检索到 {len(items)} 条适用知识片段，其中 {historical_count} 条为已验证历史案例",
            {
                "items": items,
                "query": query,
                "count": len(items),
                "historical_case_count": historical_count,
                "query_filters": filters,
            },
            tuple(str(item["evidence_id"]) for item in items),
        )

    def get_representative_samples(self, arguments: dict[str, object]) -> ToolObservation:
        if self._inspection_store is None:
            raise ValueError("representative sample store is not configured")
        snapshot_id = self._required_string(arguments, "snapshot_id")
        limit = arguments.get("limit", 6)
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise TypeError("limit must be an integer between 1 and 20")
        case = self._case_for_snapshot(snapshot_id)
        if not case.snapshot.observations:
            raise ValueError("snapshot has no observations")
        first = case.snapshot.observations[0]
        matching = [
            result
            for result in self._inspection_store.list_results()
            if result.station_id == first.station_id
            and result.product_id == first.product_id
            and first.window_start <= result.inspected_at < case.snapshot.observations[-1].window_end
        ]
        ng = sorted(
            (result for result in matching if result.is_ng),
            key=lambda result: (-result.anomaly_score, result.result_id),
        )
        good = sorted(
            (result for result in matching if not result.is_ng),
            key=lambda result: (result.anomaly_score, result.result_id),
        )
        selected = (ng[: max(1, limit // 2)] + good[: max(1, limit - limit // 2)])[:limit]
        items = [
            {
                "sample_id": result.result_id,
                "is_ng": result.is_ng,
                "anomaly_score": result.anomaly_score,
                "image_uri": result.image_uri,
                "anomaly_map_uri": result.anomaly_map_uri,
                "defect_region": (
                    result.defect_region.region_label if result.defect_region is not None else None
                ),
            }
            for result in selected
        ]
        return ToolObservation(
            "get_representative_samples",
            True,
            f"返回 {len(items)} 个代表性样本",
            {"snapshot_id": snapshot_id, "items": items, "count": len(items)},
            tuple(f"sample:{item['sample_id']}" for item in items),
        )

    def get_equipment_state(self, arguments: dict[str, object]) -> ToolObservation:
        if self._equipment is None:
            raise ValueError("equipment adapter is not configured")
        station_id = self._required_string(arguments, "station_id")
        state = self._equipment.get_state(station_id)
        return ToolObservation(
            "get_equipment_state",
            True,
            "返回设备当前只读状态",
            {
                "station_id": state.station_id,
                "observed_at": state.observed_at.isoformat(),
                "state": state.state,
                "attributes": dict(state.attributes),
            },
            (f"equipment:{station_id}:{state.observed_at.isoformat()}",),
        )

    def get_change_log(self, arguments: dict[str, object]) -> ToolObservation:
        if self._change_log is None:
            raise ValueError("change-log adapter is not configured")
        station_id = self._required_string(arguments, "station_id")
        since_raw = self._required_string(arguments, "since")
        since = datetime.fromisoformat(since_raw)
        records = self._change_log.list_recent(station_id, since)
        items = [
            {
                "change_id": record.change_id,
                "station_id": record.station_id,
                "occurred_at": record.occurred_at.isoformat(),
                "change_type": record.change_type,
                "summary": record.summary,
                "metadata": dict(record.metadata),
            }
            for record in records
        ]
        return ToolObservation(
            "get_change_log",
            True,
            f"返回 {len(items)} 条只读变更记录",
            {"station_id": station_id, "since": since.isoformat(), "items": items},
            tuple(f"change:{item['change_id']}" for item in items),
        )

    def _case_for_snapshot(self, snapshot_id: str) -> QualityCase:
        for case in self._case_store.list_cases():
            if case.snapshot.snapshot_id == snapshot_id:
                return case
        raise KeyError(f"snapshot not found: {snapshot_id}")

    @staticmethod
    def _required_string(arguments: dict[str, object], key: str) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not value:
            raise TypeError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _string_value(value: object, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise TypeError(f"{label} must be a non-empty string")
        return value
