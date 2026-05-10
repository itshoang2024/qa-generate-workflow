import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_demo_run_api_produces_enveloped_response() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/demo-runs",
        json={"preset": "snake_escape", "mode": "NEW_GAME", "auto_approve": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "meta", "error"}
    assert body["error"] is None
    run_id = body["data"]["id"]

    coverage = client.get(f"/api/v1/runs/{run_id}/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["data"]["task_count"] == 11

