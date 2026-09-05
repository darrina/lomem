# LoMem

Prototype incremental-view update agentic memory system.

## Phase 1 MVP

This repository now includes a Phase 1 MVP vertical slice with:

- A pluggable placeholder validation engine.
- A minimal web UI for scenario execution and output inspection.
- Strict input validation and explicit API error responses.
- Run telemetry and feedback capture persisted to SQLite.
- Baseline tests for deterministic engine behavior and core API/UI paths.

## Quick start

```bash
python -m pip install -e ".[dev]"
python run.py
```

Open `http://127.0.0.1:5000` in a browser.

## Data and persistence

- Dataset catalog: `data/scenarios.json`
- Local run/telemetry database: `data/lomem.db`

## API contracts (prototype)

### `GET /api/datasets`
Returns the dataset/scenario catalog used by the UI and test runs.

### `POST /api/runs`
Executes a scenario run.

Required payload shape:

```json
{
  "dataset_id": "minimal-baseline",
  "scenario_id": "alpha-stability",
  "inputs": {
    "memory_load": 42,
    "signal_strength": 77,
    "noise_level": 18,
    "adaptation_bias": 0.2
  }
}
```

Input constraints:

- `memory_load`: 0-100
- `signal_strength`: 0-100
- `noise_level`: 0-100
- `adaptation_bias`: -1.0 to 1.0

### `GET /api/runs`
Lists recent run metadata (supports `?limit=1..100`).

### `GET /api/runs/<run_id>`
Returns run details including normalized inputs and engine output.

### `POST /api/feedback`
Stores structured feedback for a run.

Required payload shape:

```json
{
  "run_id": "<uuid>",
  "rating": 4,
  "comment": "Clear enough for phase 1."
}
```
