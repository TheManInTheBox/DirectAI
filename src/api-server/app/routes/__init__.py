from app.routes.chat_completions import router as chat_router
from app.routes.embeddings import router as embeddings_router
from app.routes.audio_transcriptions import router as audio_router
from app.routes.models import router as models_router

__all__ = ["chat_router", "embeddings_router", "audio_router", "models_router"]
