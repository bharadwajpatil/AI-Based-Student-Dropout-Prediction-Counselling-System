from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class RiskLevel(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    INSUFFICIENT_DATA = "Insufficient Data"


class RiskFactor(MongoBaseModel):
    name: str = Field(..., min_length=1)
    risk: float = Field(..., ge=0.0, le=100.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    contribution: float = Field(..., ge=0.0, le=100.0)


class RiskResultInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    student_id: PyObjectId
    performance_id: PyObjectId | None = None
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    watchlist: bool = False
    factors: list[RiskFactor] = Field(default_factory=list)
    overrides_applied: list[str] = Field(default_factory=list)
    engine_version: str = "1.0.0"
    inputs_hash: str = Field(..., min_length=32, max_length=64)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_current: bool = True
