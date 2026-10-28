import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

# Set testing environment variables before importing app
os.environ["APP_ENV"] = "testing"
os.environ["APP_DEBUG"] = "true"
os.environ["JWT_SECRET"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
os.environ["MONGODB_URI"] = "mongodb://localhost:27017"
os.environ["MONGODB_DATABASE"] = "test_student_dropout_db"

from backend.app.core.clock import TestClock
from backend.app.core.rate_limit import InMemoryRateLimiter
from backend.app.db.indexes import create_indexes
from backend.app.db.mongo import db_manager
from backend.app.integrations.dns_checker import FakeDNSChecker
from backend.app.integrations.email_sender import FakeEmailSender
from backend.app.integrations.sms_sender import FakeSMSSender
from backend.app.main import create_app
from backend.app.services.auth_service import AuthService


@pytest.fixture
def test_clock() -> TestClock:
    """Fixture providing a controllable clock for deterministic time tests."""
    return TestClock()


@pytest.fixture
def fake_email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def fake_sms_sender() -> FakeSMSSender:
    return FakeSMSSender()


@pytest.fixture
def fake_dns_checker() -> FakeDNSChecker:
    return FakeDNSChecker()


@pytest.fixture
def test_limiter(test_clock: TestClock) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(clock=test_clock)


@pytest.fixture
async def mock_db():
    """Provides an isolated in-memory MongoMock database instance."""
    client = AsyncMongoMockClient()
    db = client["test_student_dropout_db"]
    # Bind to db_manager so global get_database() accesses mock_db
    original_client = db_manager.client
    original_db = db_manager.db
    db_manager.client = client
    db_manager.db = db

    await create_indexes(db)
    yield db

    # Restore
    db_manager.client = original_client
    db_manager.db = original_db


@pytest.fixture
def auth_service(
    mock_db,
    test_clock: TestClock,
    fake_email_sender: FakeEmailSender,
    fake_sms_sender: FakeSMSSender,
    fake_dns_checker: FakeDNSChecker,
    test_limiter: InMemoryRateLimiter,
) -> AuthService:
    """Provides an AuthService wired with mock dependencies for scenarios A1-A23."""
    return AuthService(
        clock=test_clock,
        email_sender=fake_email_sender,
        sms_sender=fake_sms_sender,
        dns_checker=fake_dns_checker,
        limiter=test_limiter,
    )


@pytest.fixture
async def async_client(mock_db) -> AsyncGenerator[AsyncClient, None]:
    """Provides an asynchronous HTTP test client for the FastAPI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
