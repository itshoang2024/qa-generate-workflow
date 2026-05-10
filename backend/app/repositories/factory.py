from app.config import Settings, get_settings
from app.repositories.supabase_repository import SupabaseWorkflowRepository
from app.repositories.workflow_repository import InMemoryWorkflowRepository, WorkflowRepository

_memory_repository = InMemoryWorkflowRepository()


def build_repository(settings: Settings | None = None) -> WorkflowRepository:
    settings = settings or get_settings()
    if settings.repository_provider == "supabase":
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase storage requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return SupabaseWorkflowRepository(settings.supabase_url, settings.supabase_service_role_key)
    return _memory_repository

