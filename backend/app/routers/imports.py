from typing import Any

from fastapi import APIRouter, Depends

from backend.app.core.deps import get_current_user, require_role
from backend.app.models.user import UserRole
from backend.app.schemas.import_job import ImportJobResponse
from backend.app.services.import_service import import_service

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_job_status(
    job_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD)),
):
    """Retrieves bulk import job progress, summary metrics, and row error reports."""
    return await import_service.get_import_job(job_id=job_id, current_user=current_user)
