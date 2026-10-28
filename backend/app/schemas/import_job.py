from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportJobSchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportJobResponse(ImportJobSchemaBase):
    id: str
    created_by: str
    filename: str
    status: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
