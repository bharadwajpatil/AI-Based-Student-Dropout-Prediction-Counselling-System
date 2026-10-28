import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from backend.app.core.clock import TestClock
from backend.app.core.security import create_access_token
from backend.app.models.risk import RiskLevel
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole
from backend.app.realtime.broker import EventBroker, event_broker
from backend.app.realtime.events import AppEvent
from backend.app.risk.service import RiskService
from backend.app.services.notification_service import NotificationService


# -----------------------------------------------------------------------------
# 1. Unit Tests: AppEvent SSE Framing
# -----------------------------------------------------------------------------

def test_app_event_sse_formatting():
    """Verifies standard Server-Sent Events (SSE) data framing."""
    event = AppEvent(
        id="evt-12345",
        event_type="risk.changed",
        data={"student_id": "stu-1", "level": "High", "score": 85.0},
    )
    frame = event.to_sse_frame()
    assert "id: evt-12345\n" in frame
    assert "event: risk.changed\n" in frame
    assert 'data: {"student_id": "stu-1", "level": "High", "score": 85.0}\n\n' in frame


# -----------------------------------------------------------------------------
# 2. Broker Subscriptions & Reconnection Replay (Last-Event-ID)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_broker_publish_and_subscribe():
    """Verifies that published events are delivered to active subscriber queues."""
    broker = EventBroker(buffer_size=100)
    user = {"_id": ObjectId(), "role": UserRole.ADMIN.value}

    event1 = AppEvent(
        id="evt-1",
        event_type="system.alert",
        data={"msg": "First alert"},
    )

    # Subscribe generator
    gen = broker.subscribe(user)
    first_frame_task = asyncio.create_task(anext(gen))

    # Give loop a brief yield to register subscriber
    await asyncio.sleep(0.01)
    await broker.publish(event1)

    frame = await first_frame_task
    assert "id: evt-1\n" in frame
    assert "system.alert" in frame

    # Clean up generator
    await gen.aclose()


@pytest.mark.asyncio
async def test_event_broker_last_event_id_replay():
    """Verifies that reconnecting with Last-Event-ID replays missed buffered events in order."""
    broker = EventBroker(buffer_size=100)
    user = {"_id": ObjectId(), "role": UserRole.ADMIN.value}

    evt1 = AppEvent(id="1", event_type="test", data={"n": 1})
    evt2 = AppEvent(id="2", event_type="test", data={"n": 2})
    evt3 = AppEvent(id="3", event_type="test", data={"n": 3})

    await broker.publish(evt1)
    await broker.publish(evt2)
    await broker.publish(evt3)

    # Reconnect asking for events after id "1"
    gen = broker.subscribe(user, last_event_id="1")

    frame2 = await anext(gen)
    assert "id: 2\n" in frame2

    frame3 = await anext(gen)
    assert "id: 3\n" in frame3

    await gen.aclose()


@pytest.mark.asyncio
async def test_event_broker_heartbeat():
    """Verifies keep-alive heartbeat comment frame (: ping) after timeout."""
    # Fast heartbeat interval for test
    broker = EventBroker(buffer_size=10, heartbeat_interval=0.05)
    user = {"_id": ObjectId(), "role": UserRole.ADMIN.value}

    gen = broker.subscribe(user)
    heartbeat_frame = await anext(gen)
    assert heartbeat_frame == ": ping\n\n"
    await gen.aclose()


# -----------------------------------------------------------------------------
# 3. Scenario S9: Teacher Unassigned Mid-Session
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_s9_teacher_unassigned_mid_session(mock_db):
    """
    Scenario S9: Teacher is unassigned mid-session ->
    Broker's dynamic authorization check stops delivering that student's events to the teacher.
    """
    broker = EventBroker()
    teacher_id = ObjectId()
    teacher_user = {"_id": teacher_id, "role": UserRole.TEACHER.value, "name": "Prof. Assigned"}

    student_res = await mock_db.students.insert_one({
        "erp_id": "MID_UNASSIGN",
        "name": "Target Student",
        "assigned_teacher_ids": [teacher_id],  # Initially assigned
        "status": "active",
    })
    sid = str(student_res.inserted_id)

    event = AppEvent(
        id="evt-s9",
        event_type="risk.changed",
        student_id=sid,
        data={"student_id": sid, "level": "High"},
    )

    # 1. While assigned -> authorized
    assert await broker.is_authorized_for_event(teacher_user, event) is True

    # 2. Teacher is unassigned mid-session in DB
    await mock_db.students.update_one(
        {"_id": student_res.inserted_id},
        {"$set": {"assigned_teacher_ids": []}},
    )

    # 3. Dynamic check at delivery time -> NOT authorized anymore!
    assert await broker.is_authorized_for_event(teacher_user, event) is False


# -----------------------------------------------------------------------------
# 4. Scenarios S1 & S6: Risk Changed SSE & Notification Flapping Anti-Spam
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_s1_and_s6_risk_changed_events_and_antispam(mock_db):
    """
    Scenarios S1 & S6:
    - S1: Teacher updates attendance 82 -> 48 -> High risk -> SSE risk.changed emitted & notification created.
    - S6: Flapping edits (68 -> 70.5 -> 69 -> 68 -> 66) notify at most once per actual transition (anti-spam).
    """
    clock = TestClock()
    risk_service = RiskService(clock=clock)

    teacher_id = ObjectId()
    student_res = await mock_db.students.insert_one({
        "erp_id": "FLAP101",
        "name": "Flapping Student",
        "department": "Computer Science",
        "semester": 1,
        "batch": "2024-28",
        "assigned_teacher_ids": [teacher_id],
        "status": StudentStatus.ACTIVE.value,
        "created_at": clock.now(),
        "updated_at": clock.now(),
    })
    sid = student_res.inserted_id

    # 1. Initial State: Moderate performance -> Medium risk (backlogs 2 triggers floor 40.0)
    perf_res = await mock_db.performance.insert_one({
        "student_id": sid,
        "semester": 1,
        "academic_year": "2024-25",
        "attendance": 65.0,
        "classes_held": 100,
        "marks": 50.0,
        "backlogs": 2,
        "assignments": 50.0,
        "created_at": clock.now(),
        "updated_at": clock.now(),
    })
    res1 = await risk_service.recompute_student_risk(sid)
    assert res1["level"] == RiskLevel.MEDIUM.value

    # Check notification count after initial calculation (Medium level)
    notif_count1 = await mock_db.notifications.count_documents({"user_id": teacher_id})
    assert notif_count1 == 1  # First transition None -> Medium

    # 2. Update to High risk (Scenario S1: attendance drops to 45.0 -> override floor 80.0 High)
    await mock_db.performance.update_one(
        {"_id": perf_res.inserted_id},
        {"$set": {"attendance": 45.0, "updated_at": clock.now()}},
    )
    res2 = await risk_service.recompute_student_risk(sid)
    assert res2["level"] == RiskLevel.HIGH.value

    notif_count2 = await mock_db.notifications.count_documents({"user_id": teacher_id})
    assert notif_count2 == 2  # Second transition Medium -> High

    # 3. Flapping: Minor attendance improvement but hysteresis holds it in High (69.9 -> held at High)
    # Marks improved slightly but still within hysteresis buffer
    await mock_db.performance.update_one(
        {"_id": perf_res.inserted_id},
        {"$set": {"attendance": 50.0, "marks": 40.0, "updated_at": clock.now()}},
    )
    res3 = await risk_service.recompute_student_risk(sid)
    # Because of hysteresis buffer, level remains High (score 69.9 >= 67.0)
    assert res3["level"] == RiskLevel.HIGH.value
    notif_count3 = await mock_db.notifications.count_documents({"user_id": teacher_id})
    # Level did NOT change -> notifications are NOT spammed! (Scenario S6)
    assert notif_count3 == 2

    # 4. Decisive recovery below hysteresis margin (score < 37.0 -> drops to Low)
    await mock_db.performance.update_one(
        {"_id": perf_res.inserted_id},
        {"$set": {"attendance": 90.0, "marks": 85.0, "backlogs": 0, "updated_at": clock.now()}},
    )
    res4 = await risk_service.recompute_student_risk(sid)
    assert res4["level"] == RiskLevel.LOW.value

    notif_count4 = await mock_db.notifications.count_documents({"user_id": teacher_id})
    assert notif_count4 == 3  # Level transitioned to Low -> exactly 1 new notification


# -----------------------------------------------------------------------------
# 5. Notification Service & Read Status
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_service_operations(mock_db):
    """Verifies creating, listing, unread count, and marking notifications as read."""
    clock = TestClock()
    notif_srv = NotificationService(clock=clock)
    user_id = ObjectId()

    # 1. Create two notifications
    n1 = await notif_srv.create_notification(
        user_id=user_id,
        notification_type="risk.changed",
        payload={"msg": "Student High risk"},
    )
    n2 = await notif_srv.create_notification(
        user_id=user_id,
        notification_type="counselling.assigned",
        payload={"case_id": "c1"},
    )

    # 2. Check unread count
    assert await notif_srv.get_unread_count(user_id) == 2

    # 3. List notifications
    items, unread_cnt, total = await notif_srv.list_notifications(user_id)
    assert total == 2
    assert unread_cnt == 2
    assert len(items) == 2

    # 4. Mark n1 as read
    await notif_srv.mark_as_read(str(n1["_id"]), user_id)
    assert await notif_srv.get_unread_count(user_id) == 1

    # 5. Mark all as read
    marked = await notif_srv.mark_all_as_read(user_id)
    assert marked == 1
    assert await notif_srv.get_unread_count(user_id) == 0


# -----------------------------------------------------------------------------
# 6. Notifications API Endpoints
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_api_endpoints(async_client, mock_db):
    """Full HTTP endpoint verification for /notifications."""
    user_id = ObjectId()
    await mock_db.users.insert_one({
        "_id": user_id,
        "email": "notif.test@college.edu",
        "role": "teacher",
        "name": "Prof. Notif",
        "token_version": 1,
    })

    token = create_access_token(
        subject=str(user_id),
        role="teacher",
        token_version=1,
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Insert a notification
    n_res = await mock_db.notifications.insert_one({
        "user_id": user_id,
        "type": "risk.changed",
        "payload": {"info": "Test Alert"},
        "read_at": None,
        "created_at": datetime.now(UTC),
    })
    nid = str(n_res.inserted_id)

    # 1. GET /notifications
    list_resp = await async_client.get("/notifications", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["unread_count"] == 1

    # 2. GET /notifications/unread-count
    cnt_resp = await async_client.get("/notifications/unread-count", headers=headers)
    assert cnt_resp.status_code == 200
    assert cnt_resp.json()["unread_count"] == 1

    # 3. PATCH /notifications/{id}/read
    read_resp = await async_client.patch(f"/notifications/{nid}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["read_at"] is not None

    # 4. POST /notifications/read-all
    all_resp = await async_client.post("/notifications/read-all", headers=headers)
    assert all_resp.status_code == 200
