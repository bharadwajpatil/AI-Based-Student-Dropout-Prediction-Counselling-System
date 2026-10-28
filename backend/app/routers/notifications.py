from typing import Any

from fastapi import APIRouter, Depends, Query, status

from backend.app.core.deps import get_current_user
from backend.app.schemas.notification import NotificationListResponse, NotificationResponse
from backend.app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _serialize_notification(doc: dict[str, Any]) -> NotificationResponse:
    return NotificationResponse(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        type=doc["type"],
        payload=doc.get("payload", {}),
        read_at=doc.get("read_at"),
        created_at=doc["created_at"],
    )


@router.get("", response_model=NotificationListResponse)
async def list_user_notifications(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List in-app notifications for the authenticated user."""
    items, unread_count, total = await notification_service.list_notifications(
        user_id=current_user["_id"],
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    serialized = [_serialize_notification(d) for d in items]
    return NotificationListResponse(items=serialized, unread_count=unread_count, total=total)


@router.get("/unread-count")
async def get_unread_notification_count(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Returns count of unread notifications for badge counter."""
    count = await notification_service.get_unread_count(user_id=current_user["_id"])
    return {"unread_count": count}


@router.patch("/{id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Marks a notification as read."""
    doc = await notification_service.mark_as_read(notification_id=id, user_id=current_user["_id"])
    return _serialize_notification(doc)


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Marks all user notifications as read."""
    count = await notification_service.mark_all_as_read(user_id=current_user["_id"])
    return {"marked_count": count}
