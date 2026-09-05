from pathlib import Path

import pytest

from lomem import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "LOMEM_DB_BACKEND": "sqlite",
            "LOMEM_DB_PATH": str(tmp_path / "lomem-test.db"),
            "LOMEM_DB_URL": None,
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


def test_batch_runs_and_stability_analytics(client):
    batch_response = client.post(
        "/api/runs/batch",
        json={
            "label": "test-sweep",
            "dataset_id": "minimal-baseline",
            "scenario_id": "alpha-stability",
            "variants": [
                {
                    "memory_load": 15,
                    "signal_strength": 80,
                    "noise_level": 10,
                    "adaptation_bias": 0.2,
                },
                {
                    "memory_load": 45,
                    "signal_strength": 80,
                    "noise_level": 10,
                    "adaptation_bias": 0.2,
                },
                {
                    "memory_load": 75,
                    "signal_strength": 80,
                    "noise_level": 10,
                    "adaptation_bias": 0.2,
                },
            ],
        },
    )
    batch_body = batch_response.get_json()

    assert batch_response.status_code == 201
    assert batch_body["summary"]["label"] == "test-sweep"
    assert batch_body["summary"]["run_count"] == 3
    assert len(batch_body["runs"]) == 3

    detailed_runs_response = client.get("/api/runs/detailed?limit=10")
    detailed_runs_body = detailed_runs_response.get_json()
    assert detailed_runs_response.status_code == 200
    assert len(detailed_runs_body["runs"]) == 3
    assert "output" in detailed_runs_body["runs"][0]

    stability_response = client.get("/api/analytics/stability?limit=10")
    stability_body = stability_response.get_json()
    assert stability_response.status_code == 200
    assert stability_body["run_count"] == 3
    assert len(stability_body["scenario_metrics"]) == 1
    assert stability_body["scenario_metrics"][0]["scenario_id"] == "alpha-stability"


def test_ui_smoke(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"LoMem Phase 3 Near-Functional Prototype" in response.data


def test_persistence_export_and_replace_import(client):
    run_response = client.post(
        "/api/runs",
        json={
            "dataset_id": "minimal-baseline",
            "scenario_id": "alpha-stability",
            "inputs": {
                "memory_load": 50,
                "signal_strength": 70,
                "noise_level": 20,
                "adaptation_bias": 0.1,
            },
        },
    )
    run_id = run_response.get_json()["run_id"]
    client.post(
        "/api/feedback",
        json={
            "run_id": run_id,
            "rating": 5,
            "comment": "Good run.",
            "tester_id": "phase3-user",
            "task_completed": True,
        },
    )

    info_response = client.get("/api/persistence/info")
    info_body = info_response.get_json()
    assert info_response.status_code == 200
    assert info_body["backend"] == "sqlite"

    export_response = client.get("/api/persistence/export")
    export_body = export_response.get_json()
    assert export_response.status_code == 200
    assert export_body["format"] == "lomem-persistence-bundle"
    assert export_body["counts"]["runs"] == 1
    assert export_body["counts"]["feedback"] == 1

    client.post(
        "/api/runs",
        json={
            "dataset_id": "minimal-baseline",
            "scenario_id": "beta-stress",
            "inputs": {
                "memory_load": 40,
                "signal_strength": 70,
                "noise_level": 10,
                "adaptation_bias": 0.0,
            },
        },
    )
    runs_before_import = client.get("/api/runs?limit=10").get_json()["runs"]
    assert len(runs_before_import) == 2

    import_response = client.post(
        "/api/persistence/import",
        json={"mode": "replace", "bundle": export_body},
    )
    import_body = import_response.get_json()
    assert import_response.status_code == 201
    assert import_body["status"] == "imported"
    assert import_body["counts"]["runs"] == 1

    runs_after_import = client.get("/api/runs?limit=10").get_json()["runs"]
    assert len(runs_after_import) == 1
