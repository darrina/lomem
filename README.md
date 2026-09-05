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
- A pluggable SQLAlchemy-based persistence layer with backend switching between SQLite and IRIS.
- Liquibase-style export/import bundles for repeatable state migration.
- Baseline tests for deterministic engine behavior and core API/UI paths.

## Quick start

```bash
python -m pip install -e ".[dev]"
python run.py
```

Open `http://127.0.0.1:5000` in a browser.

## Persistence configuration

Configure persistence with environment variables:

- `LOMEM_DB_BACKEND`: `sqlite` (default) or `iris`
- `LOMEM_DB_PATH`: path for SQLite files (default `data/lomem.db`)
- `LOMEM_DB_URL`: optional full SQLAlchemy URL; required for IRIS

Examples:

```bash
# Default sqlite
LOMEM_DB_BACKEND=sqlite
LOMEM_DB_PATH=data/lomem.db

# IRIS via SQLAlchemy URL
LOMEM_DB_BACKEND=iris
LOMEM_DB_URL=iris://_SYSTEM:SYS@localhost:1972/USER
```

If you use IRIS, install optional dependencies:

```bash
python -m pip install -e ".[iris]"
```

## Test matrix

`tests/test_api.py` runs as a backend matrix (`sqlite` + `iris`) via a parametrized fixture, so each API test executes once per backend.

Run the full matrix:

```bash
uv run --python 3.12 --extra dev pytest -q
```

CI runs the same matrix in GitHub Actions via `.github/workflows/ci-test-matrix.yml`.
To enforce tests before merge, set branch protection for `main` and require the `CI Test Matrix / tests` status check.

## Data and persistence

- Dataset catalog: `data/scenarios.json`
- Local run/telemetry database: configured by `LOMEM_DB_BACKEND` + `LOMEM_DB_PATH`/`LOMEM_DB_URL`

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

### `GET /api/persistence/info`
Returns the active persistence backend and SQLAlchemy URL.

### `GET /api/persistence/export`
Exports database state as a portable bundle:

- format/version metadata
- row counts
- runs/events/feedback datasets

This is intended as a lightweight, Liquibase-like export artifact for migration and environment sync.

### `POST /api/persistence/import`
Imports a bundle into the active database.

Required payload shape:

```json
{
  "mode": "merge",
  "bundle": {
    "format": "lomem-persistence-bundle",
    "version": 1,
    "data": {
      "runs": [],
      "events": [],
      "feedback": []
    }
  }
}
```

`mode` options:

- `merge`: upsert rows by primary key
- `replace`: clear existing rows, then import bundle data
