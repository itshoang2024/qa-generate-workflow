from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain.models import Feature, GDDSection, QATask, RunMode, TestCase
from app.services.agents import AgentClient, AgentOutputValidationError
from app.services.agents.contracts import (
    AGENT_A_RESPONSE_SCHEMA,
    AGENT_A_SYSTEM_PROMPT,
    AGENT_B1_RESPONSE_SCHEMA,
    AGENT_B1_SYSTEM_PROMPT,
    AGENT_B2_RESPONSE_SCHEMA,
    AGENT_B2_SYSTEM_PROMPT,
    AGENT_B3_RESPONSE_SCHEMA,
    AGENT_B3_SYSTEM_PROMPT,
    AGENT_B_RESPONSE_SCHEMA,
    AGENT_B_SYSTEM_PROMPT,
    AGENT_C_RESPONSE_SCHEMA,
    AGENT_C_SYSTEM_PROMPT,
    AgentB1Output,
    AgentB2Output,
    AgentB3Output,
    AgentAOutput,
    AgentBOutput,
    AgentCOutput,
    agent_b_feature_context_by_id,
    build_agent_b1_input,
    build_agent_b2_input,
    build_agent_b3_input,
    build_agent_a_input,
    build_agent_b_input,
    build_agent_c_input,
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
    """OpenAI structured-output adapter for Agent A/B/C with mock transient fallback."""

    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        fallback: AgentClient,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 60,
        read_timeout_seconds: float | None = None,
        retry_count: int = 2,
        retry_sleep_seconds: float = 0.5,
        model_agent_b1: str | None = None,
        model_agent_b2: str | None = None,
        model_agent_b3: str | None = None,
        stream_agent_b_substages: bool = True,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.model_agent_b1 = model_agent_b1 or model
        self.model_agent_b2 = model_agent_b2 or model
        self.model_agent_b3 = model_agent_b3 or model
        self.fallback = fallback
        timeout = (
            httpx.Timeout(timeout_seconds, read=read_timeout_seconds)
            if read_timeout_seconds is not None
            else timeout_seconds
        )
        self.http_client = http_client or httpx.Client(timeout=timeout)
        self.timeout_seconds = timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.retry_count = retry_count
        self.retry_sleep_seconds = retry_sleep_seconds
        self.stream_agent_b_substages = stream_agent_b_substages
        self._last_provider_by_operation: dict[str, str] = {}

    def provider_for(self, operation: str) -> str:
        if operation in self._last_provider_by_operation:
            return self._last_provider_by_operation[operation]
        openai_operations = {
            "analyze_gdd",
            "plan_qa_tasks",
            "plan_epics",
            "plan_stories",
            "plan_tasks",
            "generate_test_cases",
        }
        if operation in openai_operations:
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
        try:
            response_payload = self._post_response(request_payload, "OpenAI Agent A")
            agent_output = AgentAOutput.model_validate(
                _extract_structured_json(response_payload, "OpenAI Agent A")
            )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["analyze_gdd"] = "mock_after_openai_transient_error"
            return self.fallback.analyze_gdd(
                run_id,
                sections,
                mode=mode,
                delta_report=delta_report,
                validation_feedback=validation_feedback,
                target_section_ids=target_section_ids,
            )
        except httpx.HTTPError:
            self._last_provider_by_operation["analyze_gdd"] = "mock_after_openai_network_error"
            return self.fallback.analyze_gdd(
                run_id,
                sections,
                mode=mode,
                delta_report=delta_report,
                validation_feedback=validation_feedback,
                target_section_ids=target_section_ids,
            )
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["analyze_gdd"] = self.provider
            raise

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

    def plan_epics(
        self,
        run_id: str,
        *,
        hil_context: dict[str, Any],
    ) -> dict[str, Any]:
        request_payload = self._build_request_payload(
            build_agent_b1_input(hil_context),
            system_prompt=AGENT_B1_SYSTEM_PROMPT,
            schema_name="agent_b1_output",
            schema=AGENT_B1_RESPONSE_SCHEMA,
            model=self.model_agent_b1,
        )
        try:
            response_payload = self._post_response(
                request_payload,
                "OpenAI Agent B1",
                stream=self.stream_agent_b_substages,
            )
            agent_output = AgentB1Output.model_validate(
                _extract_structured_json(response_payload, "OpenAI Agent B1")
            )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["plan_epics"] = "mock_after_openai_transient_error"
            return self.fallback.plan_epics(run_id, hil_context=hil_context)
        except httpx.HTTPError:
            self._last_provider_by_operation["plan_epics"] = "mock_after_openai_network_error"
            return self.fallback.plan_epics(run_id, hil_context=hil_context)
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["plan_epics"] = self.provider
            raise

        self._last_provider_by_operation["plan_epics"] = self.provider
        return {"epics": agent_output.to_domain_epics(run_id)}

    def plan_stories(
        self,
        run_id: str,
        *,
        epic: dict[str, Any],
        features: list[dict[str, Any]],
        source_text: dict[str, str],
        story_seq_offset: int,
    ) -> dict[str, Any]:
        request_payload = self._build_request_payload(
            build_agent_b2_input(
                epic=epic,
                features=features,
                source_text=source_text,
                story_seq_offset=story_seq_offset,
                project_id=str(epic.get("project_id") or "project"),
                mode=str(epic.get("mode") or RunMode.NEW_GAME.value),
            ),
            system_prompt=AGENT_B2_SYSTEM_PROMPT,
            schema_name="agent_b2_output",
            schema=AGENT_B2_RESPONSE_SCHEMA,
            model=self.model_agent_b2,
        )
        try:
            response_payload = self._post_response(
                request_payload,
                "OpenAI Agent B2",
                stream=self.stream_agent_b_substages,
            )
            agent_output = AgentB2Output.model_validate(
                _extract_structured_json(response_payload, "OpenAI Agent B2")
            )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["plan_stories"] = "mock_after_openai_transient_error"
            return self.fallback.plan_stories(
                run_id,
                epic=epic,
                features=features,
                source_text=source_text,
                story_seq_offset=story_seq_offset,
            )
        except httpx.HTTPError:
            self._last_provider_by_operation["plan_stories"] = "mock_after_openai_network_error"
            return self.fallback.plan_stories(
                run_id,
                epic=epic,
                features=features,
                source_text=source_text,
                story_seq_offset=story_seq_offset,
            )
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["plan_stories"] = self.provider
            raise

        self._last_provider_by_operation["plan_stories"] = self.provider
        return {"epic_id": agent_output.epic_id, "stories": agent_output.to_domain_stories(run_id)}

    def plan_tasks(
        self,
        run_id: str,
        *,
        story: dict[str, Any],
        feature: dict[str, Any],
        source_text: dict[str, str],
        task_seq_offset: int,
        past_corrections: list[dict[str, Any]] | None = None,
        existing_tasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        request_payload = self._build_request_payload(
            build_agent_b3_input(
                story=story,
                feature=feature,
                source_text=source_text,
                task_seq_offset=task_seq_offset,
                project_id=str(story.get("project_id") or "project"),
                mode=str(story.get("mode") or RunMode.NEW_GAME.value),
                past_corrections=past_corrections,
                existing_tasks=existing_tasks,
            ),
            system_prompt=AGENT_B3_SYSTEM_PROMPT,
            schema_name="agent_b3_output",
            schema=AGENT_B3_RESPONSE_SCHEMA,
            model=self.model_agent_b3,
        )
        try:
            response_payload = self._post_response(
                request_payload,
                "OpenAI Agent B3",
                stream=self.stream_agent_b_substages,
            )
            agent_output = AgentB3Output.model_validate(
                _extract_structured_json(response_payload, "OpenAI Agent B3")
            )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["plan_tasks"] = "mock_after_openai_transient_error"
            return self.fallback.plan_tasks(
                run_id,
                story=story,
                feature=feature,
                source_text=source_text,
                task_seq_offset=task_seq_offset,
                past_corrections=past_corrections,
                existing_tasks=existing_tasks,
            )
        except httpx.HTTPError:
            self._last_provider_by_operation["plan_tasks"] = "mock_after_openai_network_error"
            return self.fallback.plan_tasks(
                run_id,
                story=story,
                feature=feature,
                source_text=source_text,
                task_seq_offset=task_seq_offset,
                past_corrections=past_corrections,
                existing_tasks=existing_tasks,
            )
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["plan_tasks"] = self.provider
            raise

        self._last_provider_by_operation["plan_tasks"] = self.provider
        feature_context_by_id = {
            str(feature["feature_id"]): feature
        } if isinstance(feature.get("feature_id"), str) else {}
        return {
            "story_id": agent_output.story_id,
            "tasks": agent_output.to_domain_tasks(
                run_id,
                story=story,
                feature_context_by_id=feature_context_by_id,
            ),
        }

    def generate_test_cases(
        self,
        run_id: str,
        tasks: list[QATask],
        *,
        features: list[Feature] | None = None,
        sections: list[GDDSection] | None = None,
    ) -> list[TestCase]:
        feature_by_id = {
            feature.feature_id: feature.model_dump(mode="json")
            for feature in features or []
        }
        section_text_by_id = {
            section.section_id: section.text
            for section in sections or []
            if section.text
        }
        test_cases: list[TestCase] = []
        try:
            for task in tasks:
                feature_context = feature_by_id.get(
                    task.feature_id,
                    {
                        "feature_id": task.feature_id,
                        "source_sections": task.source_sections,
                    },
                )
                related_features = _related_features_for_agent_c(
                    task,
                    feature_by_id,
                )
                request_payload = self._build_request_payload(
                    build_agent_c_input(
                        task=task.model_dump(mode="json"),
                        feature_context=feature_context,
                        source_text={
                            source_id: section_text_by_id[source_id]
                            for source_id in task.source_sections
                            if source_id in section_text_by_id
                        },
                        related_features=related_features,
                        test_case_seq_offset=len(test_cases) + 1,
                    ),
                    system_prompt=AGENT_C_SYSTEM_PROMPT,
                    schema_name="agent_c_output",
                    schema=AGENT_C_RESPONSE_SCHEMA,
                )
                response_payload = self._post_response(request_payload, "OpenAI Agent C")
                agent_output = AgentCOutput.model_validate(
                    _extract_structured_json(response_payload, "OpenAI Agent C")
                )
                test_cases.extend(
                    agent_output.to_domain_test_cases(
                        run_id,
                        task=task,
                        test_case_seq_offset=len(test_cases) + 1,
                    )
                )
        except OpenAIProviderHTTPError as exc:
            if exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            self._last_provider_by_operation["generate_test_cases"] = (
                "mock_after_openai_transient_error"
            )
            return self.fallback.generate_test_cases(run_id, tasks)
        except httpx.HTTPError:
            self._last_provider_by_operation["generate_test_cases"] = (
                "mock_after_openai_network_error"
            )
            return self.fallback.generate_test_cases(run_id, tasks)
        except (AgentOutputValidationError, ValidationError):
            self._last_provider_by_operation["generate_test_cases"] = self.provider
            raise

        self._last_provider_by_operation["generate_test_cases"] = self.provider
        return test_cases

    def _build_request_payload(
        self,
        agent_input: dict[str, Any],
        *,
        system_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        return {
            "model": model or self.model,
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

    def _post_response(
        self,
        payload: dict[str, Any],
        operation_label: str,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        last_network_error: httpx.HTTPError | None = None
        for attempt_index in range(self.retry_count + 1):
            try:
                if stream:
                    return self._post_streaming_response(payload, operation_label)
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

    def _post_streaming_response(
        self,
        payload: dict[str, Any],
        operation_label: str,
    ) -> dict[str, Any]:
        if not hasattr(self.http_client, "stream"):
            return self._post_response(payload, operation_label, stream=False)

        streamed_payload = {**payload, "stream": True}
        delta_chunks: list[str] = []
        final_text_chunks: list[str] = []
        content_part_chunks: list[str] = []
        completed_payload: dict[str, Any] | None = None
        with self.http_client.stream(
            "POST",
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=streamed_payload,
            timeout=self.timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="ignore")
                data = line[6:].strip() if line.startswith("data: ") else line.strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                event_type = str(event.get("type", ""))
                delta = event.get("delta")
                if event_type == "response.output_text.delta" and isinstance(delta, str):
                    delta_chunks.append(delta)
                elif event_type == "response.output_text.done" and isinstance(
                    event.get("text"), str
                ):
                    final_text_chunks.append(event["text"])
                elif event_type == "response.content_part.done":
                    part = event.get("part")
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and isinstance(part.get("text"), str)
                    ):
                        content_part_chunks.append(part["text"])
                elif event_type == "response.completed" and isinstance(event.get("response"), dict):
                    completed_payload = event["response"]

        if final_text_chunks:
            return {"output_text": "".join(final_text_chunks)}
        if content_part_chunks:
            return {"output_text": "".join(content_part_chunks)}
        if delta_chunks:
            return {"output_text": "".join(delta_chunks)}
        if completed_payload is not None:
            return completed_payload
        raise AgentOutputValidationError(
            f"{operation_label} streaming response did not include output text."
        )

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


def _related_features_for_agent_c(
    task: QATask,
    feature_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    task_sources = set(task.source_sections)
    related: list[dict[str, Any]] = []
    for feature_id, feature in feature_by_id.items():
        if feature_id == task.feature_id:
            continue
        raw_sources = feature.get("source_sections", [])
        feature_sources = set(raw_sources if isinstance(raw_sources, list) else [])
        if task_sources & feature_sources:
            related.append(feature)
    return related
