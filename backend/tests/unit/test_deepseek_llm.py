import json

import httpx
import pytest
from quality_case_agent.adapters.llm.deepseek import (
    DeepSeekInvestigationLLM,
    DeepSeekProviderError,
)
from quality_case_agent.application.ports.llm import LLMRequest


def _request() -> LLMRequest:
    return LLMRequest(
        run_id="run-001",
        iteration=2,
        context={"snapshot": {"case_id": "case-001"}},
        available_tools=("get_case_snapshot", "compare_quality_metrics"),
        system_instruction="Use evidence only.",
    )


def test_deepseek_adapter_posts_json_mode_and_returns_allowlisted_tool() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "kind": "TOOL_CALL",
                                    "action": "compare_quality_metrics",
                                    "arguments": {"snapshot_id": "snapshot-001"},
                                    "summary": "比较异常窗口与基准指标",
                                }
                            )
                        }
                    }
                ],
            },
        )

    adapter = DeepSeekInvestigationLLM(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = adapter.complete(_request())

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert response.decision.action == "compare_quality_metrics"


def test_deepseek_adapter_rejects_unallowlisted_tool() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "kind": "TOOL_CALL",
                                    "action": "delete_all_cases",
                                    "arguments": {},
                                    "summary": "unsafe",
                                }
                            )
                        }
                    }
                ]
            },
        )

    adapter = DeepSeekInvestigationLLM(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(DeepSeekProviderError, match="allowlist"):
        adapter.complete(_request())
