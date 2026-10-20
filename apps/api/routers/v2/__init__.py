"""
ShivAI V2 Complete Routers Package.
"""
from apps.api.routers.v2.chat import router as v2_chat_router
from apps.api.routers.v2.models import router as v2_models_router
from apps.api.routers.v2.health import router as v2_health_router
from apps.api.routers.v2.memory import router as v2_memory_router
from apps.api.routers.v2.voice import router as v2_voice_router
from apps.api.routers.v2.research import router as v2_research_router
from apps.api.routers.v2.tools import router as v2_tools_router
from apps.api.routers.v2.agents import router as v2_agents_router
from apps.api.routers.v2.documents import router as v2_documents_router
from apps.api.routers.v2.admin import v2_admin_router
from apps.api.routers.v2.media import v2_media_router
from apps.api.routers.v2.jobs import router as v2_jobs_router
from apps.api.routers.v2.orchestration import router as v2_orchestration_router
from apps.api.routers.v2.studios import router as v2_studios_router

__all__ = [
    "v2_chat_router",
    "v2_models_router",
    "v2_health_router",
    "v2_memory_router",
    "v2_voice_router",
    "v2_research_router",
    "v2_tools_router",
    "v2_agents_router",
    "v2_documents_router",
    "v2_admin_router",
    "v2_media_router",
    "v2_jobs_router",
    "v2_orchestration_router",
    "v2_studios_router",
]
