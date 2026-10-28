from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskSchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskFactorResponse(RiskSchemaBase):
    name: str
    risk: float
    weight: float
    contribution: float
    explanation: str | None = None


class RiskResultResponse(RiskSchemaBase):
    id: str
    student_id: str
    performance_id: str | None = None
    score: float | None = None
    level: str
    confidence: float
    watchlist: bool = False
    factors: list[RiskFactorResponse] = Field(default_factory=list)
    overrides_applied: list[str] = Field(default_factory=list)
    engine_version: str
    inputs_hash: str
    computed_at: datetime
    is_current: bool = True
    explanation_summary: str | None = None
    decision_support_advisory: str = Field(
        default="Risk assessments are advisory decision support and do not constitute automated decisions.",
        description="Fairness & ethics advisory indicating results are decision support.",
    )

