import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.app.models.user import UserRole


@dataclass(frozen=True)
class AppEvent:
    """Represents a system event dispatched over SSE."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "message"  # e.g. "risk.changed", "counselling.assigned", "import.progress", "notification.new"
    data: dict[str, Any] = field(default_factory=dict)
    target_user_ids: set[str] | None = None  # Specific recipients (None = filtered by role/dept)
    target_roles: set[UserRole] | None = None  # Role-based recipients
    target_department: str | None = None  # Department-scoped recipients
    student_id: str | None = None  # For dynamic object-level verification (Scenario S9)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_sse_frame(self) -> str:
        """Formats the event as a standard Server-Sent Events (SSE) data frame."""
        import json
        payload_str = json.dumps(self.data)
        return f"id: {self.id}\nevent: {self.event_type}\ndata: {payload_str}\n\n"
