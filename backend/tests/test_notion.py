from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import get_settings
from app.domain.models import (
    Epic,
    Run,
    RunMode,
    SyncEvent,
    SyncStatus,
)
from app.repositories.workflow_repository import InMemoryWorkflowRepository
from app.services.notion import NotionSyncClient
from app.services.notion.factory import build_notion_sync_client
from app.services.notion.notion import HttpxNotionSyncClient
from app.services.pipeline import PipelineService


def test_build_notion_sync_client_requires_real_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in [
        "NOTION_PROVIDER",
        "NOTION_TOKEN",
        "NOTION_EPIC_DATABASE_ID",
        "NOTION_STORY_DATABASE_ID",
        "NOTION_TASK_DATABASE_ID",
        "NOTION_TEST_CASE_DATABASE_ID",
    ]:
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("NOTION_PROVIDER=real\nNOTION_TOKEN=secret\n", encoding="utf-8")
    settings = get_settings(env_file=env_file)

    with pytest.raises(ValueError, match="NOTION_EPIC_DATABASE_ID"):
        build_notion_sync_client(settings)


def test_httpx_notion_sync_client_creates_epic_by_external_id() -> None:
    http_client = _FakeNotionHTTPClient(
        [
            _response(200, _database_schema("epic")),
            _response(200, {"results": []}),
            _response(200, {"id": "page_epic_1", "url": "https://notion.so/page_epic_1"}),
        ]
    )
    client = _notion_client(http_client)

    event = client.upsert_epic(_epic())

    assert event.status == SyncStatus.SUCCESS
    assert event.provider == "notion"
    assert event.payload["operation"] == "created"
    assert event.payload["notion_page_id"] == "page_epic_1"
    assert http_client.requests[1]["json"]["filter"] == {
        "property": "external_id",
        "rich_text": {"equals": "snake-E-CORE"},
    }


def test_httpx_notion_sync_client_retries_429_before_create() -> None:
    http_client = _FakeNotionHTTPClient(
        [
            _response(200, _database_schema("epic")),
            _response(429, {"code": "rate_limited", "message": "slow down"}, {"Retry-After": "0"}),
            _response(200, {"results": []}),
            _response(200, {"id": "page_epic_1"}),
        ]
    )
    client = _notion_client(http_client, retry_count=1)

    event = client.upsert_epic(_epic())

    assert event.status == SyncStatus.SUCCESS
    assert event.retry_count == 1
    assert len(http_client.requests) == 4


def test_httpx_notion_sync_client_schema_mismatch_returns_failed_event() -> None:
    schema = _database_schema("epic")
    del schema["properties"]["external_id"]
    http_client = _FakeNotionHTTPClient([_response(200, schema)])
    client = _notion_client(http_client)

    event = client.upsert_epic(_epic())

    assert event.status == SyncStatus.FAILED
    assert event.payload["error_code"] == "notion_schema_mismatch"
    assert "Missing property 'external_id'." in event.payload["schema_errors"]


def test_pipeline_replay_sync_calls_adapter_and_marks_replayed(tmp_path: Path) -> None:
    repository = InMemoryWorkflowRepository()
    run = repository.create_run(Run(id="run_1", project_id="snake", mode=RunMode.NEW_GAME))
    epic = _epic()
    repository.set_epics(run.id, [epic])
    failed = repository.add_sync_events(
        [
            SyncEvent(
                run_id=run.id,
                target_type="epic",
                target_id=epic.epic_id,
                external_id=epic.external_id,
                action="upsert",
                status=SyncStatus.FAILED,
                payload={"sync_phase": "Sync-A1", "database": "epic"},
                error="temporary failure",
            )
        ]
    )[0]
    notion = _ReplayNotionClient()
    service = PipelineService(
        repository=repository,
        fixture_path=tmp_path / "fixture.json",
        snake_gdd_path=tmp_path / "gdd.docx",
        notion_sync_client=notion,
    )

    result = service.replay_sync(run.id)

    updated = result["events"][0]
    assert result["replayed_count"] == 1
    assert updated.id == failed.id
    assert updated.status == SyncStatus.REPLAYED
    assert updated.payload["notion_page_id"] == "page_replayed"
    assert notion.replayed_external_ids == [epic.external_id]


def test_pipeline_replay_sync_preserves_latest_failure_details(tmp_path: Path) -> None:
    repository = InMemoryWorkflowRepository()
    run = repository.create_run(Run(id="run_1", project_id="snake", mode=RunMode.NEW_GAME))
    epic = _epic()
    repository.set_epics(run.id, [epic])
    repository.add_sync_events(
        [
            SyncEvent(
                run_id=run.id,
                target_type="epic",
                target_id=epic.epic_id,
                external_id=epic.external_id,
                action="upsert",
                status=SyncStatus.FAILED,
                payload={"sync_phase": "Sync-A1", "database": "epic", "error_code": "old_error"},
                error="old failure",
            )
        ]
    )
    service = PipelineService(
        repository=repository,
        fixture_path=tmp_path / "fixture.json",
        snake_gdd_path=tmp_path / "gdd.docx",
        notion_sync_client=_FailingReplayNotionClient(),
    )

    result = service.replay_sync(run.id)

    updated = result["events"][0]
    assert updated.status == SyncStatus.FAILED
    assert updated.error == "Notion epic schema mismatch."
    assert updated.payload["error_code"] == "notion_schema_mismatch"
    assert updated.payload["schema_errors"] == ["Missing property 'external_id'."]
    assert updated.payload["last_replay_error_code"] == "notion_schema_mismatch"


def _notion_client(
    http_client: "_FakeNotionHTTPClient",
    *,
    retry_count: int = 3,
) -> HttpxNotionSyncClient:
    return HttpxNotionSyncClient(
        token="secret",
        epic_database_id="db_epic",
        story_database_id="db_story",
        task_database_id="db_task",
        test_case_database_id="db_case",
        http_client=http_client,
        retry_count=retry_count,
        retry_backoff_seconds=0,
    )


def _epic() -> Epic:
    return Epic(
        id="epic_1",
        run_id="run_1",
        epic_id="E-CORE",
        title="Core Gameplay",
        description="Core loop QA scope.",
        feature_ids=["F-001"],
        external_id="snake-E-CORE",
    )


def _database_schema(label: str) -> dict[str, Any]:
    if label != "epic":
        raise AssertionError(label)
    return {
        "properties": {
            "Title": {"type": "title"},
            "Description": {"type": "rich_text"},
            "Feature IDs": {"type": "rich_text"},
            "external_id": {"type": "rich_text"},
        }
    }


def _response(
    status_code: int,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        headers=headers,
        request=httpx.Request("GET", "https://api.notion.com/v1/test"),
    )


class _FakeNotionHTTPClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        self.requests.append({"method": method, "url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


class _ReplayNotionClient(NotionSyncClient):
    provider = "fake_notion"

    def __init__(self) -> None:
        self.replayed_external_ids: list[str] = []

    def upsert_epic(self, epic: Epic) -> SyncEvent:
        self.replayed_external_ids.append(epic.external_id)
        return SyncEvent(
            run_id=epic.run_id,
            target_type="epic",
            target_id=epic.epic_id,
            external_id=epic.external_id,
            action="upsert",
            provider=self.provider,
            payload={
                "sync_phase": "Sync-A1",
                "database": "epic",
                "operation": "updated",
                "notion_page_id": "page_replayed",
            },
        )

    def upsert_story(self, story: Any) -> SyncEvent:
        raise AssertionError(story)

    def upsert_task(self, task: Any, feature_name: str) -> SyncEvent:
        raise AssertionError((task, feature_name))

    def upsert_test_case(self, test_case: Any) -> SyncEvent:
        raise AssertionError(test_case)


class _FailingReplayNotionClient(NotionSyncClient):
    provider = "fake_notion"

    def upsert_epic(self, epic: Epic) -> SyncEvent:
        return SyncEvent(
            run_id=epic.run_id,
            target_type="epic",
            target_id=epic.epic_id,
            external_id=epic.external_id,
            action="upsert",
            provider=self.provider,
            status=SyncStatus.FAILED,
            payload={
                "sync_phase": "Sync-A1",
                "database": "epic",
                "error_code": "notion_schema_mismatch",
                "schema_errors": ["Missing property 'external_id'."],
            },
            error="Notion epic schema mismatch.",
        )

    def upsert_story(self, story: Any) -> SyncEvent:
        raise AssertionError(story)

    def upsert_task(self, task: Any, feature_name: str) -> SyncEvent:
        raise AssertionError((task, feature_name))

    def upsert_test_case(self, test_case: Any) -> SyncEvent:
        raise AssertionError(test_case)
