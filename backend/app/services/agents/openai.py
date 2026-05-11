from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain.models import GDDSection, QATask, RunMode, TestCase
from app.services.agents import AgentClient, AgentOutputValidationError
from app.services.agents.contracts import (
    AGENT_A_RESPONSE_SCHEMA,
    AGENT_A_SYSTEM_PROMPT,
    AGENT_B_RESPONSE_SCHEMA,
    AGENT_B_SYSTEM_PROMPT,
    AgentAOutput,
    AgentBOutput,
    agent_b_feature_context_by_id,
    build_agent_a_input,
    build_agent_b_input,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class OpenAIProviderHTTPError(RuntimeError):
    def __init__(self, operation_label: str, status_code: int, detail: str) -> None:
        super().__init__(f"{operation_label} request failed with HTTP {status_code}: {detail}")
        self.operation_label = operation_label
        self.status_code = status_code
        self.detail = detail


class OpenAIAgentClient(AgentClient):
    """OpenAI structured-output adapter with mock-backed Agent C until its contract ships."""

    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        fallback: AgentClient,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 60,
        retry_count: int = 2,
        retry_sleep_seconds: float = 0.5,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback = fallback
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.retry_sleep_seconds = retry_sleep_seconds
        self._last_provider_by_operation: dict[str, str] = {}

    def provider_for(self, operation: str) -> str:
        if operation in self._last_provider_by_operation:
            return self._last_provider_by_operation[operation]
        if operation in {"analyze_gdd", "plan_qa_tasks"}:
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
            ),
            system_prompt=AGENT_A_SYSTEM_PROMPT,
            schema_name="agent_a_output",
            schema=AGENT_A_RESPONSE_SCHEMA,
        )
        response_payload = self._post_response(request_payload, "OpenAI Agent A")
        agent_output = AgentAOutput.model_validate(
            _extract_structured_json(response_payload, "OpenAI Agent A")
        )
        self._last_provider_by_operation["analyze_gdd"] = self.provider
        return {
            "features": agent_output.to_domain_features(run_id),
            "coverage_report": agent_output.coverage_report.model_dump(mode="json"),
            "ambiguities": [
                ambiguity.model_dump(mode="json")
                for ambiguity in agent_output.ambiguities
            ],
        }

    def plan_qa_tasks(
        self,
        run_id: str,
        *,
        hil_context: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        request_payload = self._build_request_payload(
            build_agent_b_input(hil_context),
            system_prompt=AGENT_B_SYSTEM_PROMPT,
            schema_name="agent_b_output",
            schema=AGENT_B_RESPONSE_SCHEMA,
        )
        try:
            response_payload = self._post_response(request_payload, "OpenAI Agent B")
            agent_output = AgentBOutput.model_validate(
                _extract_structured_json(response_payload, "OpenAI Agent B")
            )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["plan_qa_tasks"] = "mock_after_openai_transient_error"
            return self.fallback.plan_qa_tasks(run_id, hil_context=hil_context)
        except httpx.HTTPError:
            self._last_provider_by_operation["plan_qa_tasks"] = "mock_after_openai_network_error"
            return self.fallback.plan_qa_tasks(run_id, hil_context=hil_context)
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["plan_qa_tasks"] = self.provider
            raise

        self._last_provider_by_operation["plan_qa_tasks"] = self.provider
        return agent_output.to_domain_plan(
            run_id,
            feature_context_by_id=agent_b_feature_context_by_id(hil_context),
        )

    def generate_test_cases(self, run_id: str, tasks: list[QATask]) -> list[TestCase]:
        return self.fallback.generate_test_cases(run_id, tasks)

    def _build_request_payload(
        self,
        agent_input: dict[str, Any],
        *,
        system_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(agent_input, ensure_ascii=False),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }

    def _post_response(self, payload: dict[str, Any], operation_label: str) -> dict[str, Any]:
        last_network_error: httpx.HTTPError | None = None
        for attempt_index in range(self.retry_count + 1):
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
                return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                detail = exc.response.text[:500]
                if status_code in TRANSIENT_STATUS_CODES and attempt_index < self.retry_count:
                    self._sleep_before_retry()
                    continue
                raise OpenAIProviderHTTPError(operation_label, status_code, detail) from exc
            except httpx.HTTPError as exc:
                last_network_error = exc
                if attempt_index < self.retry_count:
                    self._sleep_before_retry()
                    continue
                raise

        if last_network_error is not None:
            raise last_network_error
        raise AgentOutputValidationError(f"{operation_label} request did not return a response.")

    def _sleep_before_retry(self) -> None:
        if self.retry_sleep_seconds > 0:
            time.sleep(self.retry_sleep_seconds)


def _extract_structured_json(
    response_payload: dict[str, Any],
    operation_label: str = "OpenAI agent",
) -> dict[str, Any]:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return _decode_json(output_text, operation_label)

    text_chunks: list[str] = []
    for output_item in response_payload.get("output", []):
        for content_item in output_item.get("content", []):
            refusal = content_item.get("refusal")
            if refusal:
                raise RuntimeError(f"{operation_label} refused the request: {refusal}")
            if isinstance(content_item.get("text"), str):
                text_chunks.append(content_item["text"])

    if not text_chunks:
        raise AgentOutputValidationError(
            f"{operation_label} response did not include structured output text."
        )
    return _decode_json("".join(text_chunks), operation_label)


def _decode_json(value: str, operation_label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentOutputValidationError(f"{operation_label} response was not valid JSON.") from exc
    if not isinstance(decoded, dict):
        raise AgentOutputValidationError(f"{operation_label} response must be a JSON object.")
    return decoded
