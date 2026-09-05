# LoMem

Prototype incremental-view update agentic memory system.

## Phase 3 prototype

This repository now includes a Phase 3 near-functional prototype with:

- A pluggable placeholder validation engine.
- A richer web UI for single runs, batch experiment sweeps, detailed run browsing, and pairwise run comparison.
- Strict input validation and explicit API error responses.
- Run telemetry and structured feedback capture persisted to SQLite.
- Feedback summary metrics for usability tracking by tester and task completion rate.
- Stability analytics summarizing mean and variance of run scores by scenario.
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

### `GET /api/runs/detailed`
Lists recent run records with full inputs and outputs (supports `?limit=1..500`).

### `GET /api/runs/<run_id>`
Returns run details including normalized inputs and engine output.

### `POST /api/runs/compare`
Compares 2 to 5 runs using the first run as baseline.

Required payload shape:

```json
{
  "run_ids": ["<baseline-run-id>", "<candidate-run-id>"]
}
```

### `POST /api/runs/batch`
Runs a set of input variants for one dataset/scenario and returns summary statistics.

Required payload shape:

```json
{
  "label": "memory-load-sweep",
  "dataset_id": "minimal-baseline",
  "scenario_id": "alpha-stability",
  "variants": [
    {
      "memory_load": 10,
      "signal_strength": 72,
      "noise_level": 22,
      "adaptation_bias": 0.2
    },
    {
      "memory_load": 30,
      "signal_strength": 72,
      "noise_level": 22,
      "adaptation_bias": 0.2
    }
  ]
}
```

### `POST /api/feedback`
Stores structured feedback for a run.

Required payload shape:

```json
{
  "run_id": "<uuid>",
  "rating": 4,
  "comment": "Clear enough for phase 2.",
  "tester_id": "pilot-user-1",
  "task_completed": true
}
```

### `GET /api/feedback/summary`
Returns aggregate usability metrics:

- total feedback count
- average rating
- task completion success rate
- per-tester submission and quality summary

### `GET /api/analytics/stability`
Returns a phase-3 stability snapshot:

- total run count
- per-scenario mean/standard deviation for primary score
- per-scenario mean confidence
- overall primary-score mean and standard deviation
