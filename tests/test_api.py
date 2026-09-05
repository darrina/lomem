from pathlib import Path

import pytest

from lomem import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "LOMEM_DB_PATH": str(tmp_path / "lomem-test.db"),
            "LOMEM_DATA_PATH": str(Path(__file__).resolve().parents[1] / "data" / "scenarios.json"),
        }
    )
    return app.test_client()


def test_run_validation_error_missing_inputs(client):
    response = client.post(
        "/api/runs",
        json={"dataset_id": "minimal-baseline", "scenario_id": "alpha-stability"},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "Input validation failed."
    assert "inputs" in body["errors"]


def test_run_success_and_feedback_capture(client):
    run_response = client.post(
        "/api/runs",
        json={
            "dataset_id": "minimal-baseline",
            "scenario_id": "alpha-stability",
            "inputs": {
                "memory_load": 42,
                "signal_strength": 77,
                "noise_level": 18,
                "adaptation_bias": 0.2,
            },
        },
    )
    run_body = run_response.get_json()

    assert run_response.status_code == 201
    assert run_body["dataset_id"] == "minimal-baseline"
    assert run_body["output"]["primary_score"] >= 0
    assert run_body["output"]["primary_score"] <= 1

    get_response = client.get(f"/api/runs/{run_body['run_id']}")
    assert get_response.status_code == 200

    feedback_response = client.post(
        "/api/feedback",
        json={"run_id": run_body["run_id"], "rating": 4, "comment": "Clear enough for phase 1."},
    )
    feedback_body = feedback_response.get_json()

    assert feedback_response.status_code == 201
    assert feedback_body["status"] == "recorded"


def test_ui_smoke(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"LoMem Phase 1 MVP" in response.data
