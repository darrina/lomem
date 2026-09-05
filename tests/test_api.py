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
        json={
            "run_id": run_body["run_id"],
            "rating": 4,
            "comment": "Clear enough for phase 2.",
            "tester_id": "pilot-user-1",
            "task_completed": True,
        },
    )
    feedback_body = feedback_response.get_json()

    assert feedback_response.status_code == 201
    assert feedback_body["status"] == "recorded"

    summary_response = client.get("/api/feedback/summary")
    summary_body = summary_response.get_json()
    assert summary_response.status_code == 200
    assert summary_body["feedback_count"] == 1
    assert summary_body["average_rating"] == 4.0
    assert summary_body["task_success_rate"] == 1.0
    assert summary_body["by_tester"][0]["tester_id"] == "pilot-user-1"


def test_compare_runs(client):
    baseline = client.post(
        "/api/runs",
        json={
            "dataset_id": "minimal-baseline",
            "scenario_id": "alpha-stability",
            "inputs": {
                "memory_load": 30,
                "signal_strength": 80,
                "noise_level": 15,
                "adaptation_bias": 0.2,
            },
        },
    ).get_json()
    candidate = client.post(
        "/api/runs",
        json={
            "dataset_id": "minimal-baseline",
            "scenario_id": "beta-stress",
            "inputs": {
                "memory_load": 85,
                "signal_strength": 60,
                "noise_level": 35,
                "adaptation_bias": -0.1,
            },
        },
    ).get_json()

    compare_response = client.post(
        "/api/runs/compare",
        json={"run_ids": [baseline["run_id"], candidate["run_id"]]},
    )
    compare_body = compare_response.get_json()

    assert compare_response.status_code == 200
    assert compare_body["baseline_run_id"] == baseline["run_id"]
    assert len(compare_body["comparisons"]) == 1
    assert compare_body["comparisons"][0]["run_id"] == candidate["run_id"]
    assert compare_body["comparisons"][0]["scenario_changed"] is True


def test_ui_smoke(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"LoMem Phase 2 Interactive Prototype" in response.data
