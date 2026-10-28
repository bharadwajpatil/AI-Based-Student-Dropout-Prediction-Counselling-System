import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from backend.app.core.clock import Clock, SystemClock
from backend.app.db.mongo import get_database
from backend.app.integrations.email_sender import EmailSender, SMTPEmailSender
from backend.app.realtime.broker import event_broker
from backend.app.realtime.events import AppEvent

logger = logging.getLogger("student-dropout-system.services.notification")


class NotificationService:
    """
    Manages in-app notifications and real-time SSE broadcasts.
    Supports email dispatches for critical risk alerts (Scenario S1).
    """

    def __init__(
        self,
        clock: Clock | None = None,
        email_sender: EmailSender | None = None,
    ) -> None:
        self.clock = clock or SystemClock()
        self.email_sender = email_sender or SMTPEmailSender()

    def _get_db(self):
        return get_database()

    async def create_notification(
        self,
        user_id: str | ObjectId,
        notification_type: str,
        payload: dict[str, Any],
        send_email: bool = False,
        email_to: str | None = None,
        email_subject: str | None = None,
        email_body: str | None = None,
    ) -> dict[str, Any]:
        """Creates an in-app notification, emits SSE event, and optionally sends an email."""
        db = self._get_db()
        u_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        now = self.clock.now()

        notif_doc = {
            "user_id": u_oid,
            "type": notification_type,
            "payload": payload,
            "read_at": None,
            "created_at": now,
        }

        res = await db.notifications.insert_one(notif_doc)
        notif_doc["_id"] = res.inserted_id

        # Real-time SSE dispatch
        event = AppEvent(
            event_type="notification.new",
            target_user_ids={str(u_oid)},
            data={
                "id": str(res.inserted_id),
                "type": notification_type,
                "payload": payload,
                "created_at": now.isoformat(),
            },
        )
        await event_broker.publish(event)

        # Optional Email dispatch
        if send_email and email_to:
            try:
                subject = email_subject or f"Academic Alert: {notification_type}"
                body = email_body or f"Notification Alert:\n\n{payload}"
                await self.email_sender.send_email(
                    to_email=email_to,
                    subject=subject,
                    html_content=f"<p>{body}</p>",
                    text_content=body,
                )
            except Exception as exc:
                logger.error("Failed to send notification email to %s: %s", email_to, exc)

        return notif_doc

    async def list_notifications(
        self,
        user_id: str | ObjectId,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Lists notifications for a user, returning (items, unread_count, total)."""
        db = self._get_db()
        u_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        query: dict[str, Any] = {"user_id": u_oid}
        if unread_only:
            query["read_at"] = None

        total = await db.notifications.count_documents(query)
        unread_count = await db.notifications.count_documents({"user_id": u_oid, "read_at": None})

        cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
        items = [doc async for doc in cursor]

        return items, unread_count, total

    async def mark_as_read(self, notification_id: str, user_id: str | ObjectId) -> dict[str, Any]:
        """Marks a single notification as read by the owner."""
        db = self._get_db()
        try:
            n_oid = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notification ID.")

        u_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        now = self.clock.now()

        res = await db.notifications.find_one_and_update(
            {"_id": n_oid, "user_id": u_oid},
            {"$set": {"read_at": now}},
            return_document=True,
        )
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

        return res

    async def mark_all_as_read(self, user_id: str | ObjectId) -> int:
        """Marks all unread notifications as read for a user."""
        db = self._get_db()
        u_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        now = self.clock.now()

        res = await db.notifications.update_many(
            {"user_id": u_oid, "read_at": None},
            {"$set": {"read_at": now}},
        )
        return res.modified_count

    async def get_unread_count(self, user_id: str | ObjectId) -> int:
        """Fast count of unread notifications."""
        db = self._get_db()
        u_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        return await db.notifications.count_documents({"user_id": u_oid, "read_at": None})


notification_service = NotificationService()
