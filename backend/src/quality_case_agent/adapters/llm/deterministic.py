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
        plan_raw = request.context.get("investigation_plan", {})
        plan = plan_raw if isinstance(plan_raw, dict) else {}
        required_raw = plan.get("required_tools", ())
        required = [str(item) for item in required_raw if isinstance(item, str)] if isinstance(required_raw, (list, tuple)) else []
        if not required:
            required = ["compare_quality_metrics", "get_representative_samples", "search_knowledge_base"]
        for next_tool in required:
            if next_tool in completed or next_tool not in request.available_tools:
                continue
            if next_tool == "get_representative_samples":
                return self._tool(
                    next_tool,
                    {"snapshot_id": snapshot.get("snapshot_id", ""), "limit": 6},
                    "抽取异常和正常代表性样本",
                )
            if next_tool == "search_knowledge_base":
                query = str(plan.get("knowledge_query", "质量异常 排查步骤 工艺变化 检测模型"))
                return self._tool(
                    next_tool,
                    {
                        "query": query,
                        "source_types": ["TECHNICAL_DOCUMENT", "VERIFIED_CASE"],
                        "filters": {
                            "station_id": snapshot.get("station_id", "camera-01"),
                            "product_id": snapshot.get("product_id", "part-A"),
                            "trigger_family": snapshot.get("trigger_family", "DEFAULT"),
                        },
                        "snapshot_id": snapshot.get("snapshot_id", ""),
                        "top_k": 5,
                    },
                    "检索 Runbook 指定的适用技术手册和已验证历史案例",
                )
            return self._tool(
                next_tool,
                {"snapshot_id": snapshot.get("snapshot_id", "")},
                "执行 Runbook 规定的只读调查步骤",
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
