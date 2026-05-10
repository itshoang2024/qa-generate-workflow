from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.api.v1.dependencies import settings_dependency  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

ENV_KEYS = [
    "APP_ENV",
    "API_PREFIX",
    "AI_PROVIDER",
    "NOTION_PROVIDER",
    "REPOSITORY_PROVIDER",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SNAKE_GDD_PATH",
    "UPLOAD_DIR",
    "MAX_UPLOAD_BYTES",
]


def test_get_settings_loads_backend_env_file_when_process_env_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "REPOSITORY_PROVIDER=supabase",
                "SUPABASE_URL=https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY=test-service-role",
            ]
        ),
        encoding="utf-8",
    )

    settings = get_settings(env_file=env_file)

    assert settings.repository_provider == "supabase"
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_role_key == "test-service-role"


def test_process_env_overrides_backend_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REPOSITORY_PROVIDER", "memory")
    env_file = tmp_path / ".env"
    env_file.write_text("REPOSITORY_PROVIDER=supabase", encoding="utf-8")

    settings = get_settings(env_file=env_file)

    assert settings.repository_provider == "memory"


def test_relative_snake_gdd_path_resolves_from_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SNAKE_GDD_PATH=data/GDD_Sample_Snake_Escape.docx",
        encoding="utf-8",
    )

    settings = get_settings(env_file=env_file)

    assert settings.snake_gdd_path == settings.project_root / "data" / "GDD_Sample_Snake_Escape.docx"
    assert settings.snake_gdd_path.exists()


def test_default_snake_gdd_path_uses_canonical_repo_data_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)

    settings = get_settings(env_file=tmp_path / ".env")

    assert settings.snake_gdd_path == settings.project_root / "data" / "GDD_Sample_Snake_Escape.docx"
    assert settings.snake_gdd_path.exists()


def test_configured_missing_snake_gdd_path_is_not_rewritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("SNAKE_GDD_PATH=data/missing.docx", encoding="utf-8")

    settings = get_settings(env_file=env_file)

    assert settings.snake_gdd_path == settings.project_root / "data" / "missing.docx"
    assert settings.snake_gdd_path.exists() is False


def test_health_reflects_provider_without_building_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPOSITORY_PROVIDER", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    settings_dependency.cache_clear()

    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        settings_dependency.cache_clear()

    assert response.status_code == 200
    assert response.json()["data"]["repository_provider"] == "supabase"


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
