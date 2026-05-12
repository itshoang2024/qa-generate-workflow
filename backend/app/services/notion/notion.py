from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.domain.models import Epic, QATask, Story, SyncEvent, SyncStatus, TestCase
from app.services.notion import NotionSyncClient
from app.services.notion.schema import EXPECTED_DATABASE_PROPERTIES

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RICH_TEXT_CHUNK_SIZE = 2000


class NotionSyncFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry_count: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_count = retry_count
        self.details = details or {}


class HttpxNotionSyncClient(NotionSyncClient):
    provider = "notion"

    def __init__(
        self,
        *,
        token: str,
        epic_database_id: str,
        story_database_id: str,
        task_database_id: str,
        test_case_database_id: str,
        api_base_url: str = "https://api.notion.com/v1",
        notion_version: str = "2022-06-28",
        http_client: httpx.Client | None = None,
        retry_count: int = 3,
        retry_backoff_seconds: float = 1,
        timeout_seconds: float = 20,
    ) -> None:
        self.database_ids = {
            "epic": epic_database_id,
            "story": story_database_id,
            "task": task_database_id,
            "test_case": test_case_database_id,
        }
        self.api_base_url = api_base_url.rstrip("/")
        self.notion_version = notion_version
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json",
        }
        self.page_id_by_external_id: dict[str, str] = {}
        self.epic_page_id_by_epic_id: dict[str, str] = {}
        self.story_page_id_by_story_id: dict[str, str] = {}
        self.task_page_id_by_task_id: dict[str, str] = {}
        self._schema_types_by_label: dict[str, dict[str, str]] = {}

    def prime_page_mappings(self, sync_events: list[SyncEvent]) -> None:
        for event in sync_events:
            if event.status not in {SyncStatus.SUCCESS, SyncStatus.REPLAYED}:
                continue
            page_id = event.payload.get("notion_page_id")
            if not isinstance(page_id, str) or not page_id:
                continue
            self.page_id_by_external_id[event.external_id] = page_id
            if event.target_type == "epic":
                self.epic_page_id_by_epic_id[event.target_id] = page_id
            elif event.target_type == "story":
                self.story_page_id_by_story_id[event.target_id] = page_id
            elif event.target_type == "task":
                self.task_page_id_by_task_id[event.target_id] = page_id

    def upsert_epic(self, epic: Epic) -> SyncEvent:
        return self._guarded_upsert(
            "epic",
            run_id=epic.run_id,
            target_type="epic",
            target_id=epic.epic_id,
            external_id=epic.external_id,
            sync_phase="Sync-A",
            properties_factory=lambda: self._epic_properties(epic),
            on_success=lambda page_id: self._store_epic_page(epic, page_id),
        )

    def upsert_story(self, story: Story) -> SyncEvent:
        epic_page_id = self.epic_page_id_by_epic_id.get(story.epic_id)
        if epic_page_id is None:
            return self._failed_event(
                run_id=story.run_id,
                target_type="story",
                target_id=story.story_id,
                external_id=story.external_id,
                sync_phase="Sync-A",
                database_label="story",
                failure=NotionSyncFailure(
                    "missing_notion_parent_page_id",
                    f"Missing Notion page id for epic {story.epic_id}.",
                ),
            )
        return self._guarded_upsert(
            "story",
            run_id=story.run_id,
            target_type="story",
            target_id=story.story_id,
            external_id=story.external_id,
            sync_phase="Sync-A",
            properties_factory=lambda: self._story_properties(story, epic_page_id),
            on_success=lambda page_id: self._store_story_page(story, page_id),
        )

    def upsert_task(self, task: QATask, feature_name: str) -> SyncEvent:
        epic_page_id = self.epic_page_id_by_epic_id.get(task.epic_id)
        story_page_id = self.story_page_id_by_story_id.get(task.story_id)
        if epic_page_id is None or story_page_id is None:
            missing = []
            if epic_page_id is None:
                missing.append(f"epic {task.epic_id}")
            if story_page_id is None:
                missing.append(f"story {task.story_id}")
            return self._failed_event(
                run_id=task.run_id,
                target_type="task",
                target_id=task.task_id,
                external_id=task.external_id,
                sync_phase="Sync-B",
                database_label="task",
                failure=NotionSyncFailure(
                    "missing_notion_parent_page_id",
                    f"Missing Notion page id for {', '.join(missing)}.",
                ),
            )
        return self._guarded_upsert(
            "task",
            run_id=task.run_id,
            target_type="task",
            target_id=task.task_id,
            external_id=task.external_id,
            sync_phase="Sync-B",
            properties_factory=lambda: self._task_properties(
                task,
                feature_name,
                epic_page_id,
                story_page_id,
            ),
            on_success=lambda page_id: self._store_task_page(task, page_id),
        )

    def upsert_test_case(self, test_case: TestCase) -> SyncEvent:
        task_page_id = self.task_page_id_by_task_id.get(test_case.related_task_id)
        if task_page_id is None:
            return self._failed_event(
                run_id=test_case.run_id,
                target_type="test_case",
                target_id=test_case.test_case_id,
                external_id=test_case.external_id,
                sync_phase="Sync-C",
                database_label="test_case",
                failure=NotionSyncFailure(
                    "missing_notion_parent_page_id",
                    f"Missing Notion page id for task {test_case.related_task_id}.",
                ),
            )
        return self._guarded_upsert(
            "test_case",
            run_id=test_case.run_id,
            target_type="test_case",
            target_id=test_case.test_case_id,
            external_id=test_case.external_id,
            sync_phase="Sync-C",
            properties_factory=lambda: self._test_case_properties(test_case, task_page_id),
        )

    def upsert_epics_batch(self, epics: list[Epic]) -> list[SyncEvent]:
        events = [self.upsert_epic(epic) for epic in epics]
        for event in events:
            event.payload = {**event.payload, "sync_phase": "Sync-A1"}
        return events

    def upsert_stories_for_epic(self, epic: Epic, stories: list[Story]) -> list[SyncEvent]:
        _ = epic
        events = [self.upsert_story(story) for story in stories]
        for event in events:
            event.payload = {**event.payload, "sync_phase": "Sync-A2"}
        return events

    def _guarded_upsert(
        self,
        database_label: str,
        *,
        run_id: str,
        target_type: str,
        target_id: str,
        external_id: str,
        sync_phase: str,
        properties_factory: Any,
        on_success: Any | None = None,
    ) -> SyncEvent:
        try:
            self._preflight_database(database_label)
            properties = properties_factory()
            result = self._upsert_record(database_label, external_id, properties)
            page_id = result["page_id"]
            if on_success is not None:
                on_success(page_id)
            self.page_id_by_external_id[external_id] = page_id
            return SyncEvent(
                run_id=run_id,
                target_type=target_type,
                target_id=target_id,
                external_id=external_id,
                action="upsert",
                provider=self.provider,
                payload={
                    "sync_phase": sync_phase,
                    "database": database_label,
                    "database_id": self.database_ids[database_label],
                    "operation": result["operation"],
                    "notion_page_id": page_id,
                    "notion_url": result.get("url"),
                    "properties": self._event_properties(properties),
                },
                retry_count=result["retry_count"],
            )
        except NotionSyncFailure as exc:
            return self._failed_event(
                run_id=run_id,
                target_type=target_type,
                target_id=target_id,
                external_id=external_id,
                sync_phase=sync_phase,
                database_label=database_label,
                failure=exc,
            )

    def _preflight_database(self, database_label: str) -> None:
        if database_label in self._schema_types_by_label:
            return
        database_id = self.database_ids[database_label]
        payload = self._request("GET", f"/databases/{database_id}")
        raw_properties = payload.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise NotionSyncFailure(
                "notion_schema_mismatch",
                f"Notion database {database_label} did not return properties.",
            )
        property_types = {
            name: spec.get("type")
            for name, spec in raw_properties.items()
            if isinstance(spec, dict) and isinstance(spec.get("type"), str)
        }
        errors = []
        for expected in EXPECTED_DATABASE_PROPERTIES[database_label]:
            actual_type = property_types.get(expected.name)
            if actual_type is None:
                errors.append(f"Missing property '{expected.name}'.")
            elif actual_type not in expected.allowed_types:
                allowed = ", ".join(sorted(expected.allowed_types))
                errors.append(
                    f"Property '{expected.name}' has type '{actual_type}', expected {allowed}."
                )
        if errors:
            raise NotionSyncFailure(
                "notion_schema_mismatch",
                f"Notion {database_label} schema mismatch.",
                details={"schema_errors": errors},
            )
        self._schema_types_by_label[database_label] = property_types

    def _upsert_record(
        self,
        database_label: str,
        external_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        database_id = self.database_ids[database_label]
        query_payload = {
            "filter": {
                "property": "external_id",
                "rich_text": {"equals": external_id},
            },
            "page_size": 1,
        }
        query = self._request("POST", f"/databases/{database_id}/query", json=query_payload)
        results = query.get("results", [])
        if results:
            page_id = results[0]["id"]
            page = self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})
            return {
                "operation": "updated",
                "page_id": page_id,
                "url": page.get("url"),
                "retry_count": query.get("_retry_count", 0) + page.get("_retry_count", 0),
            }
        page = self._request(
            "POST",
            "/pages",
            json={
                "parent": {"database_id": database_id},
                "properties": properties,
            },
        )
        return {
            "operation": "created",
            "page_id": page["id"],
            "url": page.get("url"),
            "retry_count": query.get("_retry_count", 0) + page.get("_retry_count", 0),
        }

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.api_base_url}{path}"
        retry_count = 0
        for attempt in range(self.retry_count + 1):
            try:
                response = self.http_client.request(method, url, headers=self.headers, json=json)
            except httpx.HTTPError as exc:
                if attempt >= self.retry_count:
                    raise NotionSyncFailure(
                        "notion_network_error",
                        str(exc),
                        retry_count=retry_count,
                    ) from exc
                self._sleep_before_retry(attempt, None)
                retry_count += 1
                continue

            if response.status_code in TRANSIENT_STATUS_CODES and attempt < self.retry_count:
                self._sleep_before_retry(attempt, response)
                retry_count += 1
                continue

            if response.status_code >= 400:
                raise NotionSyncFailure(
                    self._notion_error_code(response),
                    self._notion_error_message(response),
                    retry_count=retry_count,
                    details={"status_code": response.status_code},
                )

            payload = response.json()
            if isinstance(payload, dict):
                payload["_retry_count"] = retry_count
                return payload
            return {"_retry_count": retry_count}
        raise NotionSyncFailure("notion_retry_exhausted", "Notion request retry exhausted.")

    def _sleep_before_retry(self, attempt: int, response: httpx.Response | None) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        sleep_seconds = _retry_after_seconds(retry_after)
        if sleep_seconds is None:
            sleep_seconds = self.retry_backoff_seconds * (2**attempt)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def _notion_error_code(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "notion_http_error"
        code = payload.get("code") if isinstance(payload, dict) else None
        return str(code or "notion_http_error")

    def _notion_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            message = payload.get("message")
            if message:
                return str(message)
        return response.text

    def _epic_properties(self, epic: Epic) -> dict[str, Any]:
        return {
            "Title": _title(epic.title),
            "Description": _rich_text(epic.description),
            "Feature IDs": _rich_text(", ".join(epic.feature_ids)),
            "external_id": _rich_text(epic.external_id),
        }

    def _story_properties(self, story: Story, epic_page_id: str) -> dict[str, Any]:
        return {
            "Title": _title(story.title),
            "Description": _rich_text(story.description),
            "Acceptance criteria": _rich_text("\n".join(story.acceptance_criteria)),
            "Feature": _rich_text(story.feature_id),
            "Epic": _relation(epic_page_id),
            "external_id": _rich_text(story.external_id),
        }

    def _task_properties(
        self,
        task: QATask,
        feature_name: str,
        epic_page_id: str,
        story_page_id: str,
    ) -> dict[str, Any]:
        return {
            "Task title": _title(task.title),
            "Description": _rich_text(task.description),
            "Feature name": _rich_text(feature_name),
            "Epic": _relation(epic_page_id),
            "Story": _relation(story_page_id),
            "Priority": _select(task.priority.value),
            "Estimate": _select(task.estimate.value),
            "Suggested assignee": self._assignee_property(task.assignee),
            "Status": self._select_or_status("task", "Status", task.status),
            "external_id": _rich_text(task.external_id),
            "Source sections": _rich_text(", ".join(task.source_sections)),
            "Confidence": {"number": task.confidence},
        }

    def _test_case_properties(self, test_case: TestCase, task_page_id: str) -> dict[str, Any]:
        return {
            "Title": _title(test_case.title),
            "Type": _select(test_case.type.value),
            "Category": _select(test_case.category.value),
            "Priority": _select(test_case.priority.value),
            "Related task": _relation(task_page_id),
            "Preconditions": _rich_text("\n".join(test_case.preconditions)),
            "Test data": _rich_text(json.dumps(test_case.test_data, ensure_ascii=True, indent=2)),
            "Steps": _rich_text(_numbered_lines(test_case.steps)),
            "Expected result": _rich_text(test_case.expected_result),
            "Source sections": _rich_text(", ".join(test_case.source_sections)),
            "external_id": _rich_text(test_case.external_id),
            "Status": self._select_or_status("test_case", "Status", test_case.status),
        }

    def _assignee_property(self, assignee: str) -> dict[str, Any]:
        property_type = self._property_type("task", "Suggested assignee")
        if property_type == "select":
            return _select(assignee)
        if property_type == "people":
            return {"people": []}
        return _rich_text(assignee)

    def _select_or_status(self, database_label: str, property_name: str, value: str) -> dict[str, Any]:
        if self._property_type(database_label, property_name) == "status":
            return {"status": {"name": value}}
        return _select(value)

    def _property_type(self, database_label: str, property_name: str) -> str:
        return self._schema_types_by_label[database_label][property_name]

    def _failed_event(
        self,
        *,
        run_id: str,
        target_type: str,
        target_id: str,
        external_id: str,
        sync_phase: str,
        database_label: str,
        failure: NotionSyncFailure,
    ) -> SyncEvent:
        return SyncEvent(
            run_id=run_id,
            target_type=target_type,
            target_id=target_id,
            external_id=external_id,
            action="upsert",
            provider=self.provider,
            status=SyncStatus.FAILED,
            payload={
                "sync_phase": sync_phase,
                "database": database_label,
                "database_id": self.database_ids[database_label],
                "error_code": failure.code,
                **failure.details,
            },
            retry_count=failure.retry_count,
            error=failure.message,
        )

    def _store_epic_page(self, epic: Epic, page_id: str) -> None:
        self.epic_page_id_by_epic_id[epic.epic_id] = page_id

    def _store_story_page(self, story: Story, page_id: str) -> None:
        self.story_page_id_by_story_id[story.story_id] = page_id

    def _store_task_page(self, task: QATask, page_id: str) -> None:
        self.task_page_id_by_task_id[task.task_id] = page_id

    def _event_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in properties.items():
            result[name] = _plain_property_value(value)
        return result


def _title(value: str) -> dict[str, Any]:
    return {"title": _rich_text_fragments(value)}


def _rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": _rich_text_fragments(value)}


def _rich_text_fragments(value: str) -> list[dict[str, Any]]:
    text = value or ""
    chunks = [
        text[index : index + RICH_TEXT_CHUNK_SIZE]
        for index in range(0, len(text), RICH_TEXT_CHUNK_SIZE)
    ] or [""]
    return [{"text": {"content": chunk}} for chunk in chunks]


def _select(value: str) -> dict[str, Any]:
    return {"select": {"name": value}}


def _relation(page_id: str) -> dict[str, Any]:
    return {"relation": [{"id": page_id}]}


def _numbered_lines(values: list[str]) -> str:
    return "\n".join(f"{index}. {value}" for index, value in enumerate(values, start=1))


def _plain_property_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "title" in value or "rich_text" in value:
        fragments = value.get("title") or value.get("rich_text") or []
        return "".join(
            fragment.get("text", {}).get("content", "")
            for fragment in fragments
            if isinstance(fragment, dict)
        )
    if "select" in value:
        selected = value["select"]
        return selected.get("name") if isinstance(selected, dict) else selected
    if "status" in value:
        status = value["status"]
        return status.get("name") if isinstance(status, dict) else status
    if "relation" in value:
        return [
            relation.get("id")
            for relation in value["relation"]
            if isinstance(relation, dict) and relation.get("id")
        ]
    if "number" in value:
        return value["number"]
    if "people" in value:
        return value["people"]
    return value


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(float(value), 0)
    except ValueError:
        return None
