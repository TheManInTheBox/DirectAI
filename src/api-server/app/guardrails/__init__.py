"""
Guardrails — Content safety filtering for inference requests.

Intercepts input/output on all inference endpoints and runs text through
Azure AI Content Safety. Blocks or flags content that violates configured
severity thresholds.

Public surface:
  - ``ContentSafetyMiddleware`` — FastAPI middleware
  - ``ContentSafetyClient`` — Azure AI Content Safety API wrapper
  - ``GuardrailsConfig`` — configuration dataclass
"""

from app.guardrails.config import GuardrailsConfig
from app.guardrails.content_safety import ContentSafetyClient
from app.guardrails.middleware import ContentSafetyMiddleware

__all__ = [
    "ContentSafetyClient",
    "ContentSafetyMiddleware",
    "GuardrailsConfig",
]
