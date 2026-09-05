from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunInputs:
    memory_load: float
    signal_strength: float
    noise_level: float
    adaptation_bias: float


class ValidationError(Exception):
    def __init__(self, message: str, errors: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


def _read_number(inputs: dict[str, Any], field: str, minimum: float, maximum: float) -> float:
    if field not in inputs:
        raise ValidationError("Input validation failed.", {field: "This field is required."})

    value = inputs[field]
    if not isinstance(value, (int, float)):
        raise ValidationError("Input validation failed.", {field: "Must be a number."})
    if not minimum <= float(value) <= maximum:
        raise ValidationError(
            "Input validation failed.",
            {field: f"Must be between {minimum} and {maximum}."},
        )
    return float(value)


def validate_run_payload(
    payload: dict[str, Any] | None,
    dataset_index: dict[str, dict[str, Any]],
) -> tuple[str, str, RunInputs]:
    if not payload:
        raise ValidationError("Request body must be a JSON object.")

    dataset_id = payload.get("dataset_id")
    scenario_id = payload.get("scenario_id")
    inputs = payload.get("inputs")
    errors: dict[str, str] = {}

    if not isinstance(dataset_id, str) or not dataset_id.strip():
        errors["dataset_id"] = "dataset_id is required."
    elif dataset_id not in dataset_index:
        errors["dataset_id"] = "Unknown dataset_id."

    if not isinstance(scenario_id, str) or not scenario_id.strip():
        errors["scenario_id"] = "scenario_id is required."
    elif isinstance(dataset_id, str) and dataset_id in dataset_index:
        if scenario_id not in dataset_index[dataset_id]["scenarios"]:
            errors["scenario_id"] = "Unknown scenario_id for dataset."

    if not isinstance(inputs, dict):
        errors["inputs"] = "inputs must be an object."

    if errors:
        raise ValidationError("Input validation failed.", errors)

    normalized = RunInputs(
        memory_load=_read_number(inputs, "memory_load", 0, 100),
        signal_strength=_read_number(inputs, "signal_strength", 0, 100),
        noise_level=_read_number(inputs, "noise_level", 0, 100),
        adaptation_bias=_read_number(inputs, "adaptation_bias", -1.0, 1.0),
    )

    return dataset_id, scenario_id, normalized


def validate_feedback_payload(payload: dict[str, Any] | None) -> tuple[str, int, str]:
    if not payload:
        raise ValidationError("Request body must be a JSON object.")

    run_id = payload.get("run_id")
    rating = payload.get("rating")
    comment = payload.get("comment", "")
    errors: dict[str, str] = {}

    if not isinstance(run_id, str) or not run_id.strip():
        errors["run_id"] = "run_id is required."

    if not isinstance(rating, int) or not 1 <= rating <= 5:
        errors["rating"] = "rating must be an integer between 1 and 5."

    if not isinstance(comment, str):
        errors["comment"] = "comment must be a string."
    elif len(comment) > 1000:
        errors["comment"] = "comment must be at most 1000 characters."

    if errors:
        raise ValidationError("Feedback validation failed.", errors)

    return run_id, rating, comment


def validate_feedback_v2_payload(
    payload: dict[str, Any] | None,
) -> tuple[str, int, str, str, bool]:
    if not payload:
        raise ValidationError("Request body must be a JSON object.")

    run_id = payload.get("run_id")
    rating = payload.get("rating")
    comment = payload.get("comment", "")
    tester_id = payload.get("tester_id", "anonymous")
    task_completed = payload.get("task_completed")
    errors: dict[str, str] = {}

    if not isinstance(run_id, str) or not run_id.strip():
        errors["run_id"] = "run_id is required."

    if not isinstance(rating, int) or not 1 <= rating <= 5:
        errors["rating"] = "rating must be an integer between 1 and 5."

    if not isinstance(comment, str):
        errors["comment"] = "comment must be a string."
    elif len(comment) > 1000:
        errors["comment"] = "comment must be at most 1000 characters."

    if not isinstance(tester_id, str) or not tester_id.strip():
        errors["tester_id"] = "tester_id must be a non-empty string."
    elif len(tester_id) > 128:
        errors["tester_id"] = "tester_id must be at most 128 characters."

    if not isinstance(task_completed, bool):
        errors["task_completed"] = "task_completed must be a boolean."

    if errors:
        raise ValidationError("Feedback validation failed.", errors)

    return run_id, rating, comment, tester_id.strip(), task_completed


def validate_compare_payload(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        raise ValidationError("Request body must be a JSON object.")

    run_ids = payload.get("run_ids")
    errors: dict[str, str] = {}

    if not isinstance(run_ids, list):
        errors["run_ids"] = "run_ids must be an array."
    else:
        if len(run_ids) < 2:
            errors["run_ids"] = "run_ids must include at least two run identifiers."
        elif len(run_ids) > 5:
            errors["run_ids"] = "run_ids must include at most five run identifiers."
        else:
            for index, run_id in enumerate(run_ids):
                if not isinstance(run_id, str) or not run_id.strip():
                    errors[f"run_ids[{index}]"] = "Each run_id must be a non-empty string."
        if len(set(run_ids)) != len(run_ids):
            errors["run_ids_unique"] = "run_ids must be unique."

    if errors:
        raise ValidationError("Run comparison validation failed.", errors)

    return [run_id.strip() for run_id in run_ids]
