import asyncio
from collections import deque
from collections.abc import AsyncGenerator
import logging
import uuid
from typing import Any

from bson import ObjectId

from backend.app.db.mongo import get_database
from backend.app.models.user import UserRole
from backend.app.realtime.events import AppEvent

logger = logging.getLogger("student-dropout-system.realtime.broker")


class EventBroker:
    """
    In-memory Server-Sent Events (SSE) broker.
    Provides:
    - Bounded event replay buffer for reconnection (Last-Event-ID)
    - Dynamic authorization verification at delivery time (Scenario S9)
    - Keepalive heartbeat every 25 seconds
    - Multi-tab fan-out per user
    """

    def __init__(self, buffer_size: int = 1000, heartbeat_interval: float = 25.0) -> None:
        self.buffer_size = buffer_size
        self.heartbeat_interval = heartbeat_interval
        self._buffer: deque[AppEvent] = deque(maxlen=buffer_size)
        self._subscribers: dict[str, tuple[dict[str, Any], asyncio.Queue[AppEvent]]] = {}
        self._lock = asyncio.Lock()

    def _get_db(self):
        return get_database()

    async def is_authorized_for_event(self, user: dict[str, Any], event: AppEvent) -> bool:
        """
        Dynamically checks whether the user is authorized to receive this event.
        Guarantees Scenario S9: Teacher unassigned mid-session stops receiving student events.
        """
        user_id = str(user.get("_id"))
        role_val = user.get("role")
        if hasattr(role_val, "value"):
            role_val = role_val.value
        user_role = UserRole(role_val) if role_val else UserRole.TEACHER

        # 1. Direct recipient whitelist
        if event.target_user_ids is not None:
            if user_id not in event.target_user_ids:
                return False

        # 2. Role filtering
        if event.target_roles is not None:
            if user_role not in event.target_roles:
                return False

        # 3. Department filtering (HOD scoping)
        if event.target_department is not None:
            if user_role == UserRole.HOD:
                user_dept = user.get("department")
                if user_dept and user_dept != event.target_department:
                    return False

        # 4. Scenario S9: Dynamic Object-Level Verification for Teachers
        if event.student_id is not None and user_role == UserRole.TEACHER:
            db = self._get_db()
            try:
                stu_oid = ObjectId(event.student_id)
                student = await db.students.find_one({"_id": stu_oid}, {"assigned_teacher_ids": 1})
                if student:
                    assigned_teachers = [str(t) for t in student.get("assigned_teacher_ids", [])]
                    if user_id not in assigned_teachers:
                        # Teacher was unassigned mid-session! (Scenario S9)
                        return False
                else:
                    return False
            except Exception as exc:
                logger.debug("Failed dynamic teacher assignment check: %s", exc)
                return False

        # 5. Student object-level check
        if event.student_id is not None and user_role == UserRole.STUDENT:
            db = self._get_db()
            try:
                stu_oid = ObjectId(event.student_id)
                student = await db.students.find_one({"_id": stu_oid}, {"user_id": 1})
                if not student or str(student.get("user_id")) != user_id:
                    return False
            except Exception:
                return False

        return True

    async def publish(self, event: AppEvent) -> None:
        """Publishes an event to the replay buffer and dispatches to active matching subscribers."""
        async with self._lock:
            self._buffer.append(event)
            active_subs = list(self._subscribers.items())

        for sub_id, (user, queue) in active_subs:
            try:
                authorized = await self.is_authorized_for_event(user, event)
                if authorized:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning("Subscriber queue full for sub_id %s; dropping event", sub_id)
            except Exception as exc:
                logger.error("Error evaluating authorization for event %s on sub %s: %s", event.id, sub_id, exc)

    async def subscribe(
        self,
        user: dict[str, Any],
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Subscribes a user to the SSE stream.
        Replays missed events if last_event_id is provided, sends periodic heartbeats,
        and cleanly unregisters on disconnect.
        """
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue[AppEvent] = asyncio.Queue(maxsize=100)

        async with self._lock:
            self._subscribers[sub_id] = (user, queue)

            # Replay missed events if client reconnects with Last-Event-ID
            events_to_replay = []
            if last_event_id:
                replay = False
                for buffered_event in self._buffer:
                    if replay:
                        events_to_replay.append(buffered_event)
                    elif buffered_event.id == last_event_id:
                        replay = True

        try:
            # Yield replayed events first
            for event in events_to_replay:
                if await self.is_authorized_for_event(user, event):
                    yield event.to_sse_frame()

            # Main SSE event stream loop
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=self.heartbeat_interval)
                    yield event.to_sse_frame()
                except TimeoutError:
                    # Heartbeat keep-alive frame every 25 seconds
                    yield ": ping\n\n"
        finally:
            async with self._lock:
                self._subscribers.pop(sub_id, None)
            logger.debug("Closed SSE stream for sub_id %s", sub_id)


event_broker = EventBroker()
