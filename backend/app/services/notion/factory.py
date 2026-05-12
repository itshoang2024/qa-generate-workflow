from __future__ import annotations

from app.config import Settings
from app.services.notion import NotionSyncClient
from app.services.notion.mock import MockNotionSyncClient
from app.services.notion.notion import HttpxNotionSyncClient

SUPPORTED_NOTION_PROVIDERS = ("mock", "real")


def build_notion_sync_client(settings: Settings) -> NotionSyncClient:
    provider = settings.notion_provider.strip().lower()
    if provider == "mock":
        return MockNotionSyncClient()
    if provider == "real":
        missing = _missing_real_notion_settings(settings)
        if missing:
            missing_names = ", ".join(missing)
            raise ValueError(f"NOTION_PROVIDER=real requires {missing_names}.")
        return HttpxNotionSyncClient(
            token=settings.notion_token or "",
            epic_database_id=settings.notion_epic_database_id or "",
            story_database_id=settings.notion_story_database_id or "",
            task_database_id=settings.notion_task_database_id or "",
            test_case_database_id=settings.notion_test_case_database_id or "",
            api_base_url=settings.notion_api_base_url,
            notion_version=settings.notion_version,
            retry_count=settings.notion_retry_count,
            retry_backoff_seconds=settings.notion_retry_backoff_seconds,
            timeout_seconds=settings.notion_timeout_seconds,
        )
    supported = ", ".join(SUPPORTED_NOTION_PROVIDERS)
    raise ValueError(
        f"Unsupported NOTION_PROVIDER '{settings.notion_provider}'. Supported: {supported}."
    )


def real_notion_settings_ready(settings: Settings) -> bool:
    return not _missing_real_notion_settings(settings)


def _missing_real_notion_settings(settings: Settings) -> list[str]:
    required = {
        "NOTION_TOKEN": settings.notion_token,
        "NOTION_EPIC_DATABASE_ID": settings.notion_epic_database_id,
        "NOTION_STORY_DATABASE_ID": settings.notion_story_database_id,
        "NOTION_TASK_DATABASE_ID": settings.notion_task_database_id,
        "NOTION_TEST_CASE_DATABASE_ID": settings.notion_test_case_database_id,
    }
    return [name for name, value in required.items() if not value]
