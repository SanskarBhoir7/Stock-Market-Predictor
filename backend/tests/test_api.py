import pytest
from httpx import AsyncClient, ASGITransport
# Since tests run in backend/, we can import main directly
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database_ready" in data

@pytest.mark.asyncio
async def test_register_weak_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "weak" # Needs length, digit, and special char
            }
        )
    assert response.status_code == 400
    assert "Password must be at least 8 characters long" in response.json()["detail"]
