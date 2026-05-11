from __future__ import annotations

import json
from typing import Any

import httpx

from app.domain.models import GDDSection, QATask, RunMode, TestCase
from app.services.agents import AgentClient, AgentOutputValidationError
from app.services.agents.contracts import (
    AGENT_A_RESPONSE_SCHEMA,
    AGENT_A_SYSTEM_PROMPT,
    AgentAOutput,
    build_agent_a_input,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIAgentClient(AgentClient):
    """Real Agent A adapter with mock-backed Agent B/C until those phases get real contracts."""

    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        fallback: AgentClient,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback = fallback
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds

    def provider_for(self, operation: str) -> str:
        if operation == "analyze_gdd":
            return self.provider
        return self.fallback.provider_for(operation)

    def analyze_gdd(
        self,
        run_id: str,
        sections: list[GDDSection],
        *,
        mode: RunMode = RunMode.NEW_GAME,
        delta_report: dict[str, Any] | None = None,
        validation_feedback: list[dict[str, Any]] | None = None,
        target_section_ids: list[str] | None = None,
    ) -> dict[str, object]:
        request_payload = self._build_request_payload(
            build_agent_a_input(
                mode=mode,
                sections=sections,
                delta_report=delta_report,
                validation_feedback=validation_feedback,
                target_section_ids=target_section_ids,
            )
        )
        response_payload = self._post_response(request_payload)
        agent_output = AgentAOutput.model_validate(_extract_structured_json(response_payload))
        return {
            "features": agent_output.to_domain_features(run_id),
            "coverage_report": agent_output.coverage_report.model_dump(mode="json"),
            "ambiguities": [
                ambiguity.model_dump(mode="json")
                for ambiguity in agent_output.ambiguities
            ],
        }

    def plan_qa_tasks(self, run_id: str) -> dict[str, list[Any]]:
        return self.fallback.plan_qa_tasks(run_id)

    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[TestCase]:
        return self.fallback.generate_test_cases(run_id, tasks)

    def _build_request_payload(self, agent_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": AGENT_A_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(agent_input, ensure_ascii=False),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_a_output",
                    "strict": True,
                    "schema": AGENT_A_RESPONSE_SCHEMA,
                }
            },
        }

    def _post_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.http_client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(
                f"OpenAI Agent A request failed with HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI Agent A request failed: {exc}") from exc
        return response.json()


def _extract_structured_json(response_payload: dict[str, Any]) -> dict[str, Any]:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return _decode_json(output_text)

    text_chunks: list[str] = []
    for output_item in response_payload.get("output", []):
        for content_item in output_item.get("content", []):
            refusal = content_item.get("refusal")
            if refusal:
                raise RuntimeError(f"OpenAI Agent A refused the request: {refusal}")
            if isinstance(content_item.get("text"), str):
                text_chunks.append(content_item["text"])

    if not text_chunks:
        raise AgentOutputValidationError(
            "OpenAI Agent A response did not include structured output text."
        )
    return _decode_json("".join(text_chunks))


def _decode_json(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentOutputValidationError("OpenAI Agent A response was not valid JSON.") from exc
    if not isinstance(decoded, dict):
        raise AgentOutputValidationError("OpenAI Agent A response must be a JSON object.")
    return decoded
