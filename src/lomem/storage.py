import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    mechanism_version TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    tester_id TEXT NOT NULL DEFAULT 'anonymous',
                    task_completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )
            self._ensure_feedback_columns(connection)

    def _ensure_feedback_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(feedback)").fetchall()
        }
        if "tester_id" not in existing_columns:
            connection.execute(
                "ALTER TABLE feedback ADD COLUMN tester_id TEXT NOT NULL DEFAULT 'anonymous'"
            )
        if "task_completed" not in existing_columns:
            connection.execute(
                "ALTER TABLE feedback ADD COLUMN task_completed INTEGER NOT NULL DEFAULT 0"
            )

    def record_event(self, run_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events (run_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event_type, json.dumps(payload), _now_iso()),
            )

    def save_run(
        self,
        run_id: str,
        mechanism_version: str,
        dataset_id: str,
        scenario_id: str,
        inputs: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, mechanism_version, dataset_id,
                    scenario_id, input_json, output_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    _now_iso(),
                    mechanism_version,
                    dataset_id,
                    scenario_id,
                    json.dumps(inputs),
                    json.dumps(output),
                    "completed",
                ),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id, created_at, mechanism_version, dataset_id, scenario_id,
                       input_json, output_json, status
                FROM runs WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "mechanism_version": row["mechanism_version"],
            "dataset_id": row["dataset_id"],
            "scenario_id": row["scenario_id"],
            "inputs": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]),
            "status": row["status"],
        }

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, created_at, mechanism_version, dataset_id, scenario_id, status
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "run_id": row["run_id"],
                "created_at": row["created_at"],
                "mechanism_version": row["mechanism_version"],
                "dataset_id": row["dataset_id"],
                "scenario_id": row["scenario_id"],
                "status": row["status"],
            }
            for row in rows
        ]

    def list_runs_detailed(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, created_at, mechanism_version, dataset_id, scenario_id,
                       input_json, output_json, status
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "run_id": row["run_id"],
                "created_at": row["created_at"],
                "mechanism_version": row["mechanism_version"],
                "dataset_id": row["dataset_id"],
                "scenario_id": row["scenario_id"],
                "inputs": json.loads(row["input_json"]),
                "output": json.loads(row["output_json"]),
                "status": row["status"],
            }
            for row in rows
        ]

    def save_feedback(
        self,
        run_id: str,
        rating: int,
        comment: str,
        tester_id: str = "anonymous",
        task_completed: bool = False,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback (run_id, rating, comment, tester_id, task_completed, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, rating, comment, tester_id, int(task_completed), _now_iso()),
            )

    def get_feedback_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            aggregate = connection.execute(
                """
                SELECT
                    COUNT(*) AS feedback_count,
                    COALESCE(AVG(rating), 0) AS average_rating,
                    COALESCE(AVG(task_completed), 0) AS task_success_rate
                FROM feedback
                """
            ).fetchone()
            by_tester_rows = connection.execute(
                """
                SELECT
                    tester_id,
                    COUNT(*) AS submissions,
                    ROUND(AVG(rating), 3) AS average_rating,
                    ROUND(AVG(task_completed), 3) AS task_success_rate
                FROM feedback
                GROUP BY tester_id
                ORDER BY submissions DESC, tester_id ASC
                """
            ).fetchall()

        return {
            "feedback_count": int(aggregate["feedback_count"]),
            "average_rating": round(float(aggregate["average_rating"]), 3),
            "task_success_rate": round(float(aggregate["task_success_rate"]), 3),
            "by_tester": [
                {
                    "tester_id": row["tester_id"],
                    "submissions": int(row["submissions"]),
                    "average_rating": float(row["average_rating"]),
                    "task_success_rate": float(row["task_success_rate"]),
                }
                for row in by_tester_rows
            ],
        }
