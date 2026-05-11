from pathlib import Path
from uuid import uuid4

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.api.v1.dependencies import settings_dependency  # noqa: E402
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

    features = client.get(f"/api/v1/runs/{run_id}/features")
    tasks = client.get(f"/api/v1/runs/{run_id}/tasks")
    test_cases = client.get(f"/api/v1/runs/{run_id}/test-cases")
    assert features.json()["data"][0]["lane"] == "AUTO"
    assert {task["lane"] for task in tasks.json()["data"]} >= {"AUTO", "BATCH"}
    assert {case["lane"] for case in test_cases.json()["data"]} >= {"AUTO", "BATCH"}


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


def test_epics_endpoint_returns_generated_epics() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.get(f"/api/v1/runs/{run_id}/epics")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 5


def test_stories_endpoint_returns_generated_stories() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.get(f"/api/v1/runs/{run_id}/stories")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 5


def test_agent_runs_endpoint_returns_agent_snapshots() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.get(f"/api/v1/runs/{run_id}/agent-runs")

    assert response.status_code == 200
    assert [agent["stage"] for agent in response.json()["data"]] == [
        "S2_AGENT_A",
        "S4_AGENT_B",
        "S6_AGENT_C",
    ]


def test_sync_events_endpoint_shows_sync_a_b_c_phases() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.get(f"/api/v1/runs/{run_id}/sync-events")

    assert response.status_code == 200
    phases = [event["payload"]["sync_phase"] for event in response.json()["data"]]
    assert phases.count("Sync-A") == 10
    assert phases.count("Sync-B") == 9
    assert phases.count("Sync-C") == 36
    tasks = client.get(f"/api/v1/runs/{run_id}/tasks").json()["data"]
    task_status = {task["task_id"]: task["status"] for task in tasks}
    assert task_status["T-001"] == "Test Cases Ready"
    assert task_status["T-007"] == "Ready for Test Cases"


def test_risk_events_endpoint_returns_validator_escalations() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.get(f"/api/v1/runs/{run_id}/risk-events")

    assert response.status_code == 200
    assert any(
        event["code"] == "uncovered_actionable_section"
        for event in response.json()["data"]
    )


def test_review_decisions_endpoint_returns_hil_decisions() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)
    created = client.post(
        "/api/v1/review-decisions",
        json={
            "run_id": run_id,
            "target_type": "task",
            "target_id": "T-007",
            "decision": "APPROVED",
        },
    )
    assert created.status_code == 200

    response = client.get(f"/api/v1/runs/{run_id}/review-decisions")

    assert response.status_code == 200
    assert response.json()["data"][0]["target_id"] == "T-007"


def test_review_queue_endpoint_groups_items_by_reviewer_feature_and_epic() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    hil1 = client.get(f"/api/v1/runs/{run_id}/review-queues/HIL-1")
    hil3 = client.get(f"/api/v1/runs/{run_id}/review-queues/HIL-3")
    response = client.get(f"/api/v1/runs/{run_id}/review-queues/HIL-2")

    assert hil1.status_code == 200
    assert hil1.json()["data"]["item_count"] == 2
    assert hil3.status_code == 200
    assert hil3.json()["data"]["item_count"] == 8
    assert response.status_code == 200
    queue = response.json()["data"]
    assert queue["hil_tier"] == "HIL-2"
    assert queue["item_count"] == 2
    assert queue["group_by"] == ["reviewer", "feature_id", "epic_id"]
    assert {group["reviewer"] for group in queue["groups"]} == {"Linh", "Minh"}
    assert all(group["feature_id"] and group["epic_id"] for group in queue["groups"])


def test_review_decision_approval_updates_lane_and_removes_item_from_queue() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)
    before = client.get(f"/api/v1/runs/{run_id}/tasks").json()["data"]
    task_before = next(task for task in before if task["task_id"] == "T-007")
    assert task_before["lane"] == "BATCH"
    assert task_before["review_status"] == "NEEDS_REVIEW"

    approved = client.post(
        "/api/v1/review-decisions",
        json={
            "run_id": run_id,
            "target_type": "task",
            "target_id": "T-007",
            "decision": "APPROVED",
            "reviewer": "Minh",
        },
    )
    assert approved.status_code == 200

    after = client.get(f"/api/v1/runs/{run_id}/tasks").json()["data"]
    task_after = next(task for task in after if task["task_id"] == "T-007")
    assert task_after["lane"] == "AUTO"
    assert task_after["review_status"] == "APPROVED"

    queue = client.get(f"/api/v1/runs/{run_id}/review-queues/HIL-2").json()["data"]
    queued_ids = {
        item["target_id"]
        for group in queue["groups"]
        for item in group["items"]
    }
    assert "T-007" not in queued_ids


def test_sign_off_endpoint_updates_run_and_coverage_report() -> None:
    client = TestClient(app)
    run_id = _create_demo_run(client)

    response = client.post(
        f"/api/v1/runs/{run_id}/sign-off",
        json={"reviewer": "QA Lead"},
    )
    coverage = client.get(f"/api/v1/runs/{run_id}/coverage")

    assert response.status_code == 200
    assert response.json()["data"]["signed_off_by"] == "QA Lead"
    assert coverage.json()["data"]["sign_off"]["signed_off"] is True


def test_provider_status_endpoint_reports_credential_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("NOTION_PROVIDER", "real")
    monkeypatch.setenv("NOTION_TOKEN", "")
    monkeypatch.setenv("REPOSITORY_PROVIDER", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    settings_dependency.cache_clear()

    try:
        response = TestClient(app).get("/api/v1/providers/status")
    finally:
        settings_dependency.cache_clear()

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["ai"] == {"provider": "mock", "credentials_ready": True}
    assert data["notion"] == {"provider": "real", "credentials_ready": False}
    assert data["repository"] == {"provider": "supabase", "credentials_ready": True}


def _create_demo_run(client: TestClient) -> str:
    response = client.post(
        "/api/v1/demo-runs",
        json={"preset": "snake_escape", "mode": "NEW_GAME", "auto_approve": True},
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]
