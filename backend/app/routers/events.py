from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.app.core.security import decode_access_token
from backend.app.db.mongo import get_database
from backend.app.realtime.broker import event_broker

router = APIRouter(tags=["Events"])


async def get_sse_user(
    token: str | None = Query(default=None, description="Access token for EventSource authentication"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """
    Authenticates user for SSE streaming.
    Supports either standard Authorization header or query parameter ?token=...
    (which is required for browser EventSource API).
    """
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1]
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token for event stream.",
        )

    try:
        payload = decode_access_token(raw_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired event stream token.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
        )

    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    return user


@router.get("/events")
async def sse_event_stream(
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: str | None = Query(default=None, alias="last_event_id"),
    current_user: dict[str, Any] = Depends(get_sse_user),
):
    """
    Server-Sent Events (SSE) live connection stream.
    - Real-time updates for risk changes, counselling, import progress, and notifications
    - Automatic reconnection replay with Last-Event-ID
    - 25-second keepalive heartbeats
    - Dynamic authorization scoping at delivery time
    """
    effective_last_id = last_event_id or last_event_id_query

    return StreamingResponse(
        event_broker.subscribe(user=current_user, last_event_id=effective_last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
