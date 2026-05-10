from pathlib import Path
from uuid import uuid4

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _snake_gdd_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "GDD_Sample_Snake_Escape.docx"


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


def test_project_trigger_context_and_gdd_document_apis() -> None:
    gdd_path = _snake_gdd_path()
    if not gdd_path.exists():
        pytest.skip("Root-level Snake Escape GDD is not available.")

    client = TestClient(app)
    project_name = f"API Versioned Game {uuid4().hex[:8]}"

    new_trigger = client.post(
        "/api/v1/runs/trigger",
        json={"project_name": project_name, "gdd_file_ref": str(gdd_path)},
    )
    assert new_trigger.status_code == 200
    new_trigger_data = new_trigger.json()["data"]
    assert new_trigger_data["mode"] == "NEW_GAME"

    project_id = new_trigger_data["project_id"]
    project_response = client.get(f"/api/v1/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["data"]["name"] == project_name

    projects_response = client.get("/api/v1/projects")
    assert projects_response.status_code == 200
    assert any(project["id"] == project_id for project in projects_response.json()["data"])

    first_context = client.post(
        f"/api/v1/runs/{new_trigger_data['run_id']}/context",
        json={"description": "Uploaded by API test."},
    )
    assert first_context.status_code == 200
    first_document = first_context.json()["data"]["gdd_document"]
    assert first_document["version_id"] == "v1"
    assert first_document["description_status"] == "USER_PROVIDED"

    hil0_questions = client.get(f"/api/v1/runs/{new_trigger_data['run_id']}/hil-0/questions")
    assert hil0_questions.status_code == 200
    question_id = hil0_questions.json()["data"][0]["id"]
    hil0_resolution = client.post(
        f"/api/v1/runs/{new_trigger_data['run_id']}/hil-0/resolutions",
        json={"question_id": question_id, "action": "proceed_with_flag"},
    )
    assert hil0_resolution.status_code == 200
    assert hil0_resolution.json()["data"]["action"] == "proceed_with_flag"

    delta_trigger = client.post(
        "/api/v1/runs/trigger",
        json={"project_id": project_id, "gdd_file": str(gdd_path)},
    )
    assert delta_trigger.status_code == 200
    delta_trigger_data = delta_trigger.json()["data"]
    assert delta_trigger_data["mode"] == "DELTA"

    second_context = client.post(f"/api/v1/runs/{delta_trigger_data['run_id']}/context")
    assert second_context.status_code == 200
    second_context_data = second_context.json()["data"]
    assert second_context_data["gdd_document"]["version_id"] == "v2"
    assert second_context_data["gdd_document"]["parent_document_id"] == first_document["id"]
    assert second_context_data["delta_report"]["status"] == "READY"

    documents_response = client.get(f"/api/v1/projects/{project_id}/gdd-documents")
    assert documents_response.status_code == 200
    assert [doc["version_id"] for doc in documents_response.json()["data"]] == ["v2", "v1"]
