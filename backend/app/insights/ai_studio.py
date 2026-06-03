"""Optional ECI AI Studio agent integration for natural-language insights."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.insights.nlq import NLAnswer
from app.metrics.definitions import metrics_for_industry

logger = logging.getLogger(__name__)


@dataclass
class AIStudioAgentResponse:
    answer: str
    explanation: str | None = None
    data: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class AIStudioAgentClient:
    """HTTP bridge for an AI Studio agent.

    The exact AI Studio agent contract can vary by workspace, so this client keeps the outbound
    payload explicit and accepts a few common inbound answer fields.
    """

    def __init__(
        self,
        agent_url: str | None = None,
        api_key: str | None = None,
        agent_id: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.agent_url = agent_url
        self.api_key = api_key
        self.agent_id = agent_id
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> "AIStudioAgentClient":
        return cls(
            agent_url=settings.ai_studio_agent_url,
            api_key=settings.ai_studio_api_key,
            agent_id=settings.ai_studio_agent_id,
            timeout_seconds=settings.ai_studio_timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return bool(self.agent_url)

    def ask(
        self,
        *,
        tenant_id: str,
        question: str,
        local_answer: NLAnswer,
        industry: str | None,
    ) -> AIStudioAgentResponse | None:
        if not self.configured:
            return None

        payload = {
            "agent_id": self.agent_id,
            "tenant_id": tenant_id,
            "question": question,
            "context": {
                "local_answer": local_answer.as_dict(),
                "metric_catalog": [m.as_dict() for m in metrics_for_industry(industry)],
                "instructions": (
                    "Use the governed local_answer and metric_catalog as source-of-truth business "
                    "context. Do not invent metrics or data outside this payload."
                ),
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(str(self.agent_url), json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # pragma: no cover - exact transport exceptions vary by runtime
            logger.warning("AI Studio agent request failed: %s", exc)
            return None

        if not isinstance(body, dict):
            logger.warning("AI Studio agent returned non-object JSON: %r", body)
            return None

        answer = _first_text(body, ("answer", "output", "message", "content", "text", "response"))
        if not answer:
            logger.warning("AI Studio agent response did not include an answer field: %r", body)
            return None

        data = body.get("data")
        if not isinstance(data, list):
            data = local_answer.data

        return AIStudioAgentResponse(
            answer=answer,
            explanation=_first_text(body, ("explanation", "reasoning", "summary")),
            data=data,
            raw=body,
        )


def answer_with_optional_ai_studio(
    *,
    tenant_id: str,
    question: str,
    local_answer: NLAnswer,
    industry: str | None,
    client: AIStudioAgentClient | None = None,
) -> dict[str, Any]:
    """Return the local NLQ answer, optionally enhanced by an AI Studio agent."""

    client = client or AIStudioAgentClient.from_settings()
    base = local_answer.as_dict()
    base["source"] = "local"

    agent_response = client.ask(
        tenant_id=tenant_id,
        question=question,
        local_answer=local_answer,
        industry=industry,
    )
    if agent_response is None:
        base["agent"] = {
            "provider": "eci_ai_studio",
            "status": "not_configured" if not client.configured else "fallback",
        }
        return base

    base.update(
        {
            "answer": agent_response.answer,
            "data": agent_response.data,
            "explanation": agent_response.explanation
            or "Answered by the configured ECI AI Studio agent using governed metric context.",
            "source": "eci_ai_studio",
            "agent": {
                "provider": "eci_ai_studio",
                "status": "answered",
                "agent_id": client.agent_id,
            },
        }
    )
    return base


def _first_text(body: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            nested = _first_text(value, keys)
            if nested:
                return nested
    return None
