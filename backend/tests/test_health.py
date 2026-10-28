from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verifies that the root endpoint returns app metadata and status."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "student-dropout-system"
    assert data["status"] == "online"
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_request_id_middleware_propagation(async_client: AsyncClient):
    """Verifies that incoming X-Request-ID is preserved and echoed back."""
    custom_request_id = "test-custom-request-id-12345"
    response = await async_client.get("/", headers={"X-Request-ID": custom_request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_request_id


@pytest.mark.asyncio
async def test_health_check_healthy(async_client: AsyncClient):
    """Verifies /health returns 200 and 'connected' when database ping succeeds."""
    with patch("backend.app.main.ping_database", return_value=True):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_unhealthy(async_client: AsyncClient):
    """Verifies /health returns 503 and 'disconnected' when database ping fails."""
    with patch("backend.app.main.ping_database", return_value=False):
        response = await async_client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_not_found_exception_structure(async_client: AsyncClient):
    """
    Verifies 404 responses conform to the structured error specification:
    {error: {code, message, details}}.
    """
    response = await async_client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert "Not Found" in data["error"]["message"]
