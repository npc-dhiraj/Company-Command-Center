from collections.abc import AsyncGenerator
from typing import Any

from fastapi.testclient import TestClient

from app.core.database import get_session
from app.main import app


def test_health_check() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_unavailable() -> None:
    class MockFailingSession:
        async def execute(self, *args: Any, **kwargs: Any) -> Any:
            raise Exception("Database connection failure")

    async def mock_failing_session() -> AsyncGenerator[MockFailingSession, None]:
        yield MockFailingSession()

    app.dependency_overrides[get_session] = mock_failing_session
    client = TestClient(app)
    response = client.get("/health/ready")
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "error"}
