"""DeepSeek V4 Flash adapter for bounded investigation decisions.

The adapter deliberately uses DeepSeek's OpenAI-compatible JSON output mode
instead of persisting or displaying reasoning content. The application remains
the only process allowed to invoke investigation tools.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

import httpx

from quality_case_agent.application.ports.llm import LLMDecision, LLMRequest, LLMResponse


class DeepSeekConfigurationError(ValueError):
    """Raised when the DeepSeek runtime configuration is incomplete."""


class DeepSeekProviderError(RuntimeError):
    """Raised for a failed or invalid DeepSeek provider response."""


class DeepSeekInvestigationLLM:
    """Map DeepSeek V4 Flash JSON decisions to the provider-neutral LLM port."""

    provider = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout_s: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is required for provider=deepseek")
        if not model.strip():
            raise DeepSeekConfigurationError("QUALITY_LLM_MODEL must not be empty")
        self.model = model.strip()
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s))
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def from_env(cls) -> DeepSeekInvestigationLLM:
        timeout_raw = os.getenv("QUALITY_LLM_TIMEOUT_S", "30")
        try:
            timeout_s = float(timeout_raw)
        except ValueError as exc:
            raise DeepSeekConfigurationError("QUALITY_LLM_TIMEOUT_S must be a number") from exc
        if timeout_s <= 0:
            raise DeepSeekConfigurationError("QUALITY_LLM_TIMEOUT_S must be positive")
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            model=os.getenv("QUALITY_LLM_MODEL", "deepseek-v4-flash"),
            base_url=os.getenv("QUALITY_LLM_BASE_URL", "https://api.deepseek.com"),
            timeout_s=timeout_s,
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json=self._payload(request),
            )
        except httpx.HTTPError as exc:
            raise DeepSeekProviderError("DeepSeek request failed") from exc
        if response.status_code >= 400:
            raise DeepSeekProviderError(f"DeepSeek request failed with HTTP {response.status_code}")
        try:
            raw = response.json()
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DeepSeekProviderError("DeepSeek response has no JSON decision content") from exc
        if not isinstance(content, str) or not content.strip():
            raise DeepSeekProviderError("DeepSeek returned an empty decision")
        return LLMResponse(model=str(raw.get("model") or self.model), decision=self._decision(content, request))

    def _payload(self, request: LLMRequest) -> dict[str, object]:
        decision_contract = {
            "kind": "TOOL_CALL | FINAL | STOP",
            "action": "one allowed tool name, submit_investigation_analysis, or stop reason label",
            "arguments": "object; required for TOOL_CALL, otherwise {}",
            "summary": "short, factual Chinese or English audit summary without hidden reasoning",
        }
        system = (
            "You are the bounded decision module of an industrial quality investigation Agent. "
            "Return exactly one valid JSON object and no markdown. "
            "Never request a tool outside allowed_actions. Use TOOL_CALL for one allowed action, "
            "FINAL only when the available observations are sufficient, and STOP when evidence is "
            "insufficient or unsafe. Do not reveal private chain-of-thought; summary is an auditable "
            "outcome statement only. JSON contract: "
            f"{json.dumps(decision_contract, ensure_ascii=False)}"
        )
        user = {
            "run_id": request.run_id,
            "iteration": request.iteration,
            "allowed_actions": list(request.available_tools),
            "system_instruction": request.system_instruction,
            "context": request.context,
        }
        return {
            "model": self.model,
            "stream": False,
            # Tool decisions only; do not receive or persist reasoning_content.
            "thinking": {"type": "disabled"},
            "temperature": 0.1,
            "max_tokens": 600,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
            ],
        }

    @staticmethod
    def _decision(content: str, request: LLMRequest) -> LLMDecision:
        try:
            raw: Any = json.loads(content)
        except json.JSONDecodeError as exc:
            raise DeepSeekProviderError("DeepSeek decision is not valid JSON") from exc
        if not isinstance(raw, Mapping):
            raise DeepSeekProviderError("DeepSeek decision must be a JSON object")
        kind = raw.get("kind")
        action = raw.get("action")
        arguments = raw.get("arguments", {})
        summary = raw.get("summary", "")
        if kind not in {"TOOL_CALL", "FINAL", "STOP"}:
            raise DeepSeekProviderError("DeepSeek decision has an unsupported kind")
        if not isinstance(action, str) or not action.strip():
            raise DeepSeekProviderError("DeepSeek decision action is missing")
        if not isinstance(arguments, dict):
            raise DeepSeekProviderError("DeepSeek decision arguments must be an object")
        if not isinstance(summary, str) or not summary.strip():
            raise DeepSeekProviderError("DeepSeek decision summary is missing")
        if kind == "TOOL_CALL" and action not in request.available_tools:
            raise DeepSeekProviderError("DeepSeek requested a tool outside the allowlist")
        if kind == "FINAL":
            action = "submit_investigation_analysis"
            arguments = {}
        return LLMDecision(
            kind=kind,
            action=action,
            arguments=arguments,
            summary=summary[:2_000],
        )
