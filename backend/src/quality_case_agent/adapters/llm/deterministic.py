"""Deterministic tool-calling LLM substitute for offline tests and demos."""

from quality_case_agent.application.ports.llm import LLMDecision, LLMRequest, LLMResponse


class DeterministicInvestigationLLM:
    """Choose a fixed investigation plan from completed tool names.

    It models the provider-neutral decision seam without pretending to be a
    production language model. No chain-of-thought is stored or returned.
    """

    model = "deterministic-investigation-1"
    provider = "deterministic"

    def complete(self, request: LLMRequest) -> LLMResponse:
        completed_raw = request.context.get("completed_tools", ())
        completed = (
            {str(item) for item in completed_raw}
            if isinstance(completed_raw, (list, tuple, set))
            else set()
        )
        snapshot_raw = request.context.get("snapshot", {})
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else {}
        if "get_case_snapshot" not in completed:
            return self._tool(
                "get_case_snapshot",
                {
                    "case_id": snapshot.get("case_id", ""),
                    "snapshot_id": snapshot.get("snapshot_id", ""),
                },
                "读取不可变 Case Snapshot",
            )
        warnings = snapshot.get("data_quality_warnings", [])
        if warnings and "check_data_quality" not in completed:
            return self._tool(
                "check_data_quality",
                {"snapshot_id": snapshot.get("snapshot_id", "")},
                "检查样本量、模型版本和原始证据完整性",
            )
        if warnings and "check_data_quality" in completed:
            return LLMResponse(
                model=self.model,
                decision=LLMDecision(
                    kind="STOP",
                    action="data_quality_blocked",
                    summary="DATA_QUALITY_BLOCKED: 当前证据不足，申请补充数据后再进行根因分析",
                ),
            )
        if "compare_quality_metrics" not in completed:
            return self._tool(
                "compare_quality_metrics",
                {"snapshot_id": snapshot.get("snapshot_id", "")},
                "比较异常窗口与基准指标",
            )
        if "get_representative_samples" in request.available_tools and "get_representative_samples" not in completed:
            return self._tool(
                "get_representative_samples",
                {"snapshot_id": snapshot.get("snapshot_id", ""), "limit": 6},
                "抽取异常和正常代表性样本",
            )
        if "search_knowledge_base" not in completed:
            trigger_family = snapshot.get("trigger_family", "FIXTURE_OFFSET")
            if trigger_family == "ILLUMINATION_DRIFT":
                query = "光照 漂移 曝光 亮度 光源角度 增益 校准 illumination drift exposure brightness"
            else:
                query = "夹具 定位销 偏移 检查步骤 fixture positioning pin offset inspection"
            return self._tool(
                "search_knowledge_base",
                {
                    "query": query,
                    "source_types": ["TECHNICAL_DOCUMENT", "VERIFIED_CASE"],
                    "filters": {
                        "station_id": snapshot.get("station_id", "camera-01"),
                        "product_id": snapshot.get("product_id", "part-A"),
                        "trigger_family": snapshot.get("trigger_family", "FIXTURE_OFFSET"),
                    },
                    "snapshot_id": snapshot.get("snapshot_id", ""),
                    "top_k": 5,
                },
                "检索适用技术手册和已验证历史案例",
            )
        return LLMResponse(
            model=self.model,
            decision=LLMDecision(
                kind="FINAL",
                action="submit_investigation_analysis",
                summary="已收集当前事实、指标对比和适用知识证据",
            ),
        )

    def _tool(self, name: str, arguments: dict[str, object], summary: str) -> LLMResponse:
        return LLMResponse(
            model=self.model,
            decision=LLMDecision(
                kind="TOOL_CALL", action=name, arguments=arguments, summary=summary
            ),
        )
