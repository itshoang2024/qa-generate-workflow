from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_prefix: str
    ai_provider: str
    notion_provider: str
    repository_provider: str
    openai_api_key: str | None
    openai_model: str
    ai_model_agent_b1: str
    ai_model_agent_b2: str
    ai_model_agent_b3: str
    agent_b2_parallelism: int
    agent_b3_parallelism: int
    openai_timeout_read_seconds: float
    anthropic_api_key: str | None
    notion_token: str | None
    notion_api_base_url: str
    notion_version: str
    notion_epic_database_id: str | None
    notion_story_database_id: str | None
    notion_task_database_id: str | None
    notion_test_case_database_id: str | None
    notion_retry_count: int
    notion_retry_backoff_seconds: float
    notion_timeout_seconds: float
    supabase_url: str | None
    supabase_service_role_key: str | None
    project_root: Path
    workspace_root: Path
    fixture_path: Path
    snake_gdd_path: Path
    upload_dir: Path
    max_upload_bytes: int


def get_settings(env_file: Path | None = None) -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    project_root = backend_root.parent
    env_values = _load_env_file(env_file or backend_root / ".env")

    workspace_root = project_root.parent
    configured_gdd = _env_value("SNAKE_GDD_PATH", env_values)
    snake_gdd_path = (
        _resolve_configured_path(configured_gdd, project_root)
        if configured_gdd
        else _default_snake_gdd_path(project_root)
    )
    configured_upload_dir = _env_value("UPLOAD_DIR", env_values)
    upload_dir = Path(
        _resolve_configured_path(
            configured_upload_dir or str(backend_root / ".runtime" / "uploads"),
            project_root,
        )
    )

    return Settings(
        app_env=_env_value("APP_ENV", env_values, "local"),
        api_prefix=_env_value("API_PREFIX", env_values, "/api/v1"),
        ai_provider=_env_value("AI_PROVIDER", env_values, "mock").lower(),
        notion_provider=_env_value("NOTION_PROVIDER", env_values, "mock").lower(),
        repository_provider=_env_value("REPOSITORY_PROVIDER", env_values, "memory").lower(),
        openai_api_key=_env_value("OPENAI_API_KEY", env_values) or None,
        openai_model=_env_value("OPENAI_MODEL", env_values, "gpt-4.1-mini"),
        ai_model_agent_b1=_env_value("AI_MODEL_AGENT_B1", env_values, "gpt-4o"),
        ai_model_agent_b2=_env_value("AI_MODEL_AGENT_B2", env_values, "gpt-4o-mini"),
        ai_model_agent_b3=_env_value("AI_MODEL_AGENT_B3", env_values, "gpt-4o-mini"),
        agent_b2_parallelism=int(_env_value("AGENT_B2_PARALLELISM", env_values, "3")),
        agent_b3_parallelism=int(_env_value("AGENT_B3_PARALLELISM", env_values, "5")),
        openai_timeout_read_seconds=float(
            _env_value("OPENAI_TIMEOUT_READ_SECONDS", env_values, "120")
        ),
        anthropic_api_key=_env_value("ANTHROPIC_API_KEY", env_values) or None,
        notion_token=_env_value("NOTION_TOKEN", env_values) or None,
        notion_api_base_url=_env_value(
            "NOTION_API_BASE_URL",
            env_values,
            "https://api.notion.com/v1",
        ).rstrip("/"),
        notion_version=_env_value("NOTION_VERSION", env_values, "2022-06-28"),
        notion_epic_database_id=_env_value("NOTION_EPIC_DATABASE_ID", env_values) or None,
        notion_story_database_id=_env_value("NOTION_STORY_DATABASE_ID", env_values) or None,
        notion_task_database_id=_env_value("NOTION_TASK_DATABASE_ID", env_values) or None,
        notion_test_case_database_id=_env_value("NOTION_TEST_CASE_DATABASE_ID", env_values)
        or None,
        notion_retry_count=int(_env_value("NOTION_RETRY_COUNT", env_values, "3")),
        notion_retry_backoff_seconds=float(
            _env_value("NOTION_RETRY_BACKOFF_SECONDS", env_values, "1")
        ),
        notion_timeout_seconds=float(_env_value("NOTION_TIMEOUT_SECONDS", env_values, "20")),
        supabase_url=_env_value("SUPABASE_URL", env_values) or None,
        supabase_service_role_key=_env_value("SUPABASE_SERVICE_ROLE_KEY", env_values) or None,
        project_root=project_root,
        workspace_root=workspace_root,
        fixture_path=project_root / "data" / "snake_escape_fixture.json",
        snake_gdd_path=snake_gdd_path,
        upload_dir=upload_dir,
        max_upload_bytes=int(_env_value("MAX_UPLOAD_BYTES", env_values, "10485760")),
    )


def _load_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    return {key: value for key, value in dotenv_values(env_file).items() if value is not None}


def _env_value(key: str, env_values: dict[str, str], default: str = "") -> str:
    if key in os.environ:
        return os.environ[key].strip()
    return env_values.get(key, default).strip()


def _resolve_configured_path(
    value: str,
    project_root: Path,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def _default_snake_gdd_path(project_root: Path) -> Path:
    return project_root / "data" / "GDD_Sample_Snake_Escape.docx"
