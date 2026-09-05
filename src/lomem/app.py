import uuid
from dataclasses import asdict
from typing import Any

from flask import Flask, jsonify, render_template, request

from .config import Config
from .datasets import build_index, load_catalog
from .engine import execute_validation, to_dict
from .storage import Storage
from .validation import (
    ValidationError,
    validate_compare_payload,
    validate_feedback_v2_payload,
    validate_run_payload,
)


def _error_response(message: str, status_code: int, errors: dict[str, str] | None = None):
    payload: dict[str, Any] = {"error": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status_code


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    catalog = load_catalog(app.config["LOMEM_DATA_PATH"])
    dataset_index = build_index(catalog)
    storage = Storage(app.config["LOMEM_DB_PATH"])
    mechanism_version = app.config["LOMEM_MECHANISM_VERSION"]

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/datasets")
    def get_datasets():
        return jsonify(catalog)

    @app.post("/api/runs")
    def create_run():
        payload = request.get_json(silent=True)

        try:
            dataset_id, scenario_id, normalized_inputs = validate_run_payload(payload, dataset_index)
        except ValidationError as err:
            return _error_response(err.message, 400, err.errors)

        run_id = str(uuid.uuid4())
        scenario = dataset_index[dataset_id]["scenarios"][scenario_id]
        result = execute_validation(normalized_inputs, scenario)
        response_payload = {
            "run_id": run_id,
            "mechanism_version": mechanism_version,
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "inputs": asdict(normalized_inputs),
            "output": to_dict(result),
        }

        storage.save_run(
            run_id=run_id,
            mechanism_version=mechanism_version,
            dataset_id=dataset_id,
            scenario_id=scenario_id,
            inputs=response_payload["inputs"],
            output=response_payload["output"],
        )
        storage.record_event(run_id, "run_completed", response_payload)

        return jsonify(response_payload), 201

    @app.get("/api/runs")
    def list_runs():
        limit = request.args.get("limit", default=20, type=int)
        if limit is None or limit < 1 or limit > 100:
            return _error_response("limit must be between 1 and 100.", 400)
        return jsonify({"runs": storage.list_runs(limit)})

    @app.get("/api/runs/<run_id>")
    def get_run(run_id: str):
        run = storage.get_run(run_id)
        if run is None:
            return _error_response("Run not found.", 404)
        return jsonify(run)

    @app.post("/api/runs/compare")
    def compare_runs():
        payload = request.get_json(silent=True)
        try:
            run_ids = validate_compare_payload(payload)
        except ValidationError as err:
            return _error_response(err.message, 400, err.errors)

        runs = []
        for run_id in run_ids:
            run = storage.get_run(run_id)
            if run is None:
                return _error_response(f"Run not found: {run_id}", 404)
            runs.append(run)

        baseline = runs[0]
        baseline_score = baseline["output"]["primary_score"]
        comparisons = []
        for candidate in runs[1:]:
            candidate_score = candidate["output"]["primary_score"]
            comparisons.append(
                {
                    "run_id": candidate["run_id"],
                    "delta_primary_score": round(candidate_score - baseline_score, 6),
                    "delta_confidence": round(
                        candidate["output"]["confidence"] - baseline["output"]["confidence"], 6
                    ),
                    "dataset_changed": candidate["dataset_id"] != baseline["dataset_id"],
                    "scenario_changed": candidate["scenario_id"] != baseline["scenario_id"],
                }
            )

        response_payload = {
            "baseline_run_id": baseline["run_id"],
            "baseline_primary_score": baseline_score,
            "comparisons": comparisons,
        }
        storage.record_event(None, "runs_compared", response_payload)
        return jsonify(response_payload)

    @app.post("/api/feedback")
    def create_feedback():
        payload = request.get_json(silent=True)
        try:
            run_id, rating, comment, tester_id, task_completed = validate_feedback_v2_payload(
                payload
            )
        except ValidationError as err:
            return _error_response(err.message, 400, err.errors)

        run = storage.get_run(run_id)
        if run is None:
            return _error_response("Run not found for provided run_id.", 404)

        storage.save_feedback(run_id, rating, comment, tester_id, task_completed)
        storage.record_event(
            run_id,
            "feedback_submitted",
            {
                "rating": rating,
                "comment_length": len(comment),
                "tester_id": tester_id,
                "task_completed": task_completed,
            },
        )
        return jsonify({"status": "recorded", "run_id": run_id}), 201

    @app.get("/api/feedback/summary")
    def feedback_summary():
        return jsonify(storage.get_feedback_summary())

    return app
