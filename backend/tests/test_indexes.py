from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.db.indexes import create_indexes


@pytest.mark.asyncio
async def test_create_indexes_idempotency_with_mock():
    """
    Verifies that create_indexes calls create_indexes on all required collections
    and is safe to invoke multiple times consecutively (idempotent).
    """
    mock_db = MagicMock()
    mock_db.users.create_indexes = AsyncMock()
    mock_db.students.create_indexes = AsyncMock()
    mock_db.performance.create_indexes = AsyncMock()
    mock_db.risk_results.create_indexes = AsyncMock()
    mock_db.counselling.create_indexes = AsyncMock()
    mock_db.auth_tokens.create_indexes = AsyncMock()
    mock_db.refresh_tokens.create_indexes = AsyncMock()
    mock_db.notifications.create_indexes = AsyncMock()
    mock_db.audit_logs.create_indexes = AsyncMock()
    mock_db.import_jobs.create_indexes = AsyncMock()
    mock_db.disposable_domains.create_indexes = AsyncMock()

    # First invocation
    await create_indexes(mock_db)

    # Second invocation (idempotency check)
    await create_indexes(mock_db)

    # Assert each collection index creation was called twice without error
    assert mock_db.users.create_indexes.call_count == 2
    assert mock_db.students.create_indexes.call_count == 2
    assert mock_db.performance.create_indexes.call_count == 2
    assert mock_db.risk_results.create_indexes.call_count == 2
    assert mock_db.counselling.create_indexes.call_count == 2
    assert mock_db.auth_tokens.create_indexes.call_count == 2
    assert mock_db.refresh_tokens.create_indexes.call_count == 2
    assert mock_db.notifications.create_indexes.call_count == 2
    assert mock_db.audit_logs.create_indexes.call_count == 2
    assert mock_db.import_jobs.create_indexes.call_count == 2
    assert mock_db.disposable_domains.create_indexes.call_count == 2


@pytest.mark.asyncio
async def test_create_indexes_live_atlas_idempotency():
    """
    Connects to the configured live MongoDB instance, runs create_indexes twice
    on a test database to prove idempotency against the real engine, then cleans up.
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    from backend.app.core.config import settings

    if not settings.MONGODB_URI.startswith(("mongodb://", "mongodb+srv://")):
        pytest.skip("No valid MongoDB URI configured for live test")

    try:
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
        test_db = client["_test_phase2_indexes_db"]
        await test_db.command("ping")
    except Exception:
        pytest.skip("MongoDB server is currently unreachable for live index testing")

    try:
        # Run 1
        await create_indexes(test_db)
        # Run 2 (verify no IndexKeySpecsConflict or duplicate index errors)
        await create_indexes(test_db)

        # Verify indexes exist on users collection
        indexes = await test_db.users.index_information()
        assert "idx_users_email_unique" in indexes
        assert "idx_users_phone_sparse_unique" in indexes
    finally:
        await client.drop_database("_test_phase2_indexes_db")
        client.close()
