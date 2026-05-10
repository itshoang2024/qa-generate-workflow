from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_prefix: str
    ai_provider: str
    notion_provider: str
    repository_provider: str
    supabase_url: str | None
    supabase_service_role_key: str | None
    project_root: Path
    workspace_root: Path
    fixture_path: Path
    snake_gdd_path: Path


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    workspace_root = project_root.parent
    configured_gdd = os.getenv("SNAKE_GDD_PATH")
    snake_gdd_path = (
        Path(configured_gdd)
        if configured_gdd
        else workspace_root / "GDD Sample_Snake Escape.docx"
    )

    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        ai_provider=os.getenv("AI_PROVIDER", "mock"),
        notion_provider=os.getenv("NOTION_PROVIDER", "mock"),
        repository_provider=os.getenv("REPOSITORY_PROVIDER", "memory"),
        supabase_url=os.getenv("SUPABASE_URL") or None,
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None,
        project_root=project_root,
        workspace_root=workspace_root,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=snake_gdd_path,
    )

