from functools import lru_cache

from app.config import Settings, get_settings
from app.repositories.factory import build_repository
from app.repositories.workflow_repository import WorkflowRepository
from app.services.pipeline import PipelineService


@lru_cache
def settings_dependency() -> Settings:
    return get_settings()


@lru_cache
def repository_dependency() -> WorkflowRepository:
    return build_repository(settings_dependency())


def pipeline_dependency() -> PipelineService:
    settings = settings_dependency()
    return PipelineService(
        repository=repository_dependency(),
        fixture_path=settings.fixture_path,
        snake_gdd_path=settings.snake_gdd_path,
        upload_dir=settings.upload_dir,
        max_upload_bytes=settings.max_upload_bytes,
    )
