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
    upload_dir = Path(
        _resolve_configured_path(
            _env_value("UPLOAD_DIR", env_values, str(backend_root / ".runtime" / "uploads")),
            project_root,
        )
    )

    return Settings(
        app_env=_env_value("APP_ENV", env_values, "local"),
        api_prefix=_env_value("API_PREFIX", env_values, "/api/v1"),
        ai_provider=_env_value("AI_PROVIDER", env_values, "mock"),
        notion_provider=_env_value("NOTION_PROVIDER", env_values, "mock"),
        repository_provider=_env_value("REPOSITORY_PROVIDER", env_values, "memory"),
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
        return os.environ[key]
    return env_values.get(key, default)


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
