import json
from pathlib import Path
from typing import Any


def load_catalog(data_path: str) -> dict[str, Any]:
    with Path(data_path).open("r", encoding="utf-8") as data_file:
        catalog = json.load(data_file)

    if "datasets" not in catalog or not isinstance(catalog["datasets"], list):
        raise ValueError("Invalid dataset catalog: expected a datasets list.")

    return catalog


def build_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dataset_index: dict[str, dict[str, Any]] = {}
    for dataset in catalog["datasets"]:
        scenarios = {scenario["id"]: scenario for scenario in dataset.get("scenarios", [])}
        dataset_index[dataset["id"]] = {
            "dataset": dataset,
            "scenarios": scenarios,
        }
    return dataset_index
