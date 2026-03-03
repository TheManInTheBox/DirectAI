from app.routes.audio_transcriptions import router as audio_router
from app.routes.chat_completions import router as chat_router
from app.routes.embeddings import router as embeddings_router
from app.routes.models import router as models_router
from app.routes.native_deployments import router as native_deployments_router
from app.routes.native_models import router as native_models_router
from app.routes.native_system import router as native_system_router

__all__ = [
    "chat_router",
    "embeddings_router",
    "audio_router",
    "models_router",
    "native_deployments_router",
    "native_models_router",
    "native_system_router",
]
