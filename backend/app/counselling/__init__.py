from backend.app.counselling.client import (
    GeminiAPIError,
    GeminiClient,
    GeminiError,
    GeminiQuotaError,
    GeminiSafetyBlockError,
    GeminiTimeoutError,
    GeminiValidationError,
)
from backend.app.counselling.fallback import generate_template_recommendation
from backend.app.counselling.guardrails import detect_crisis, sanitize_clinical_language
from backend.app.counselling.prompt import build_counselling_user_prompt, generate_anonymous_token
from backend.app.counselling.schemas import (
    AICounsellingRecommendation,
    CounsellingListResponse,
    CounsellingNoteCreate,
    CounsellingNoteResponse,
    CounsellingResponse,
    CounsellingUpdate,
)
from backend.app.counselling.service import CounsellingService, counselling_service

__all__ = [
    "AICounsellingRecommendation",
    "CounsellingListResponse",
    "CounsellingNoteCreate",
    "CounsellingNoteResponse",
    "CounsellingResponse",
    "CounsellingService",
    "CounsellingUpdate",
    "GeminiAPIError",
    "GeminiClient",
    "GeminiError",
    "GeminiQuotaError",
    "GeminiSafetyBlockError",
    "GeminiTimeoutError",
    "GeminiValidationError",
    "build_counselling_user_prompt",
    "counselling_service",
    "detect_crisis",
    "generate_anonymous_token",
    "generate_template_recommendation",
    "sanitize_clinical_language",
]
