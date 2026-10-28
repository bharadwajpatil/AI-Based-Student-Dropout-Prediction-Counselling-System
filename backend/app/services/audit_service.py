from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from backend.app.core.clock import Clock, default_clock
from backend.app.db.mongo import get_database


class AuditService:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or default_clock

    async def log_action(
        self,
        action: str,
        target_type: str,
        target_id: str | None = None,
        actor_id: str | ObjectId | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip: str | None = None,
    ) -> None:
        """Inserts an append-only audit log entry."""
        db = get_database()
        now = self.clock.now()

        actor_oid = None
        if actor_id is not None:
            if isinstance(actor_id, ObjectId):
                actor_oid = actor_id
            elif isinstance(actor_id, str) and ObjectId.is_valid(actor_id):
                actor_oid = ObjectId(actor_id)

        entry = {
            "actor_id": actor_oid,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "before": before,
            "after": after,
            "ip": ip,
            "at": now,
        }
        await db.audit_logs.insert_one(entry)


audit_service = AuditService()
