from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _datetime_to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _normalize_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def build_database_url(backend: str, db_path: str, db_url: str | None) -> str:
    normalized_backend = backend.lower()
    if db_url:
        return db_url
    if normalized_backend == "sqlite":
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    if normalized_backend == "iris":
        raise ValueError("LOMEM_DB_URL is required when LOMEM_DB_BACKEND is set to iris.")
    raise ValueError(f"Unsupported LOMEM_DB_BACKEND: {backend}")


def _serialize_payload(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"))


def _deserialize_payload(value: str) -> dict[str, Any]:
    return json.loads(value)


class Base(DeclarativeBase):
    pass


class RunModel(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mechanism_version: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    feedback: Mapped[list["FeedbackModel"]] = relationship(back_populates="run")
    events: Mapped[list["EventModel"]] = relationship(back_populates="run")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.run_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[RunModel | None] = relationship(back_populates="events")


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(1000), nullable=False)
    tester_id: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    task_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[RunModel] = relationship(back_populates="feedback")


@dataclass
class PersistenceConfig:
    backend: str
    db_path: str
    db_url: str | None


class Storage:
    def __init__(self, config: PersistenceConfig) -> None:
        self.config = config
        self.database_url = build_database_url(config.backend, config.db_path, config.db_url)
        self.engine = create_engine(self.database_url, future=True)
        self.session_factory = sessionmaker(bind=self.engine, future=True)
        self.init_schema()

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def backend_info(self) -> dict[str, str]:
        return {
            "backend": self.config.backend.lower(),
            "database_url": self.database_url,
        }

    def record_event(self, run_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self.session_factory() as session:
            session.add(
                EventModel(
                    run_id=run_id,
                    event_type=event_type,
                    payload_json=_serialize_payload(payload),
                    created_at=_now_utc(),
                )
            )
            session.commit()

    def save_run(
        self,
        run_id: str,
        mechanism_version: str,
        dataset_id: str,
        scenario_id: str,
        inputs: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        with self.session_factory() as session:
            session.add(
                RunModel(
                    run_id=run_id,
                    created_at=_now_utc(),
                    mechanism_version=mechanism_version,
                    dataset_id=dataset_id,
                    scenario_id=scenario_id,
                    input_json=_serialize_payload(inputs),
                    output_json=_serialize_payload(output),
                    status="completed",
                )
            )
            session.commit()

    def _run_to_dict(self, row: RunModel) -> dict[str, Any]:
        return {
            "run_id": row.run_id,
            "created_at": _datetime_to_iso(row.created_at),
            "mechanism_version": row.mechanism_version,
            "dataset_id": row.dataset_id,
            "scenario_id": row.scenario_id,
            "inputs": _deserialize_payload(row.input_json),
            "output": _deserialize_payload(row.output_json),
            "status": row.status,
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(RunModel, run_id)
            if row is None:
                return None
            return self._run_to_dict(row)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = (
                session.query(RunModel)
                .order_by(RunModel.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "run_id": row.run_id,
                    "created_at": _datetime_to_iso(row.created_at),
                    "mechanism_version": row.mechanism_version,
                    "dataset_id": row.dataset_id,
                    "scenario_id": row.scenario_id,
                    "status": row.status,
                }
                for row in rows
            ]

    def list_runs_detailed(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = (
                session.query(RunModel)
                .order_by(RunModel.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._run_to_dict(row) for row in rows]

    def save_feedback(
        self,
        run_id: str,
        rating: int,
        comment: str,
        tester_id: str = "anonymous",
        task_completed: bool = False,
    ) -> None:
        with self.session_factory() as session:
            session.add(
                FeedbackModel(
                    run_id=run_id,
                    rating=rating,
                    comment=comment,
                    tester_id=tester_id,
                    task_completed=task_completed,
                    created_at=_now_utc(),
                )
            )
            session.commit()

    def get_feedback_summary(self) -> dict[str, Any]:
        with self.session_factory() as session:
            feedback_count, average_rating, task_success_rate = (
                session.query(
                    func.count(FeedbackModel.id),
                    func.coalesce(func.avg(FeedbackModel.rating), 0.0),
                    func.coalesce(func.avg(func.cast(FeedbackModel.task_completed, Float)), 0.0),
                ).one()
            )
            by_tester_rows = (
                session.query(
                    FeedbackModel.tester_id,
                    func.count(FeedbackModel.id).label("submissions"),
                    func.round(func.avg(FeedbackModel.rating), 3).label("average_rating"),
                    func.round(func.avg(func.cast(FeedbackModel.task_completed, Float)), 3).label(
                        "task_success_rate"
                    ),
                )
                .group_by(FeedbackModel.tester_id)
                .order_by(func.count(FeedbackModel.id).desc(), FeedbackModel.tester_id.asc())
                .all()
            )

        return {
            "feedback_count": int(feedback_count),
            "average_rating": round(float(average_rating), 3),
            "task_success_rate": round(float(task_success_rate), 3),
            "by_tester": [
                {
                    "tester_id": row.tester_id,
                    "submissions": int(row.submissions),
                    "average_rating": float(row.average_rating),
                    "task_success_rate": float(row.task_success_rate),
                }
                for row in by_tester_rows
            ],
        }

    def export_bundle(self) -> dict[str, Any]:
        with self.session_factory() as session:
            runs = session.query(RunModel).order_by(RunModel.created_at.asc(), RunModel.run_id.asc()).all()
            events = (
                session.query(EventModel)
                .order_by(EventModel.created_at.asc(), EventModel.id.asc())
                .all()
            )
            feedback = (
                session.query(FeedbackModel)
                .order_by(FeedbackModel.created_at.asc(), FeedbackModel.id.asc())
                .all()
            )

        payload = {
            "format": "lomem-persistence-bundle",
            "version": 1,
            "exported_at": _datetime_to_iso(_now_utc()),
            "database": self.backend_info(),
            "counts": {
                "runs": len(runs),
                "events": len(events),
                "feedback": len(feedback),
            },
            "data": {
                "runs": [
                    {
                        "run_id": row.run_id,
                        "created_at": _datetime_to_iso(row.created_at),
                        "mechanism_version": row.mechanism_version,
                        "dataset_id": row.dataset_id,
                        "scenario_id": row.scenario_id,
                        "input_json": _deserialize_payload(row.input_json),
                        "output_json": _deserialize_payload(row.output_json),
                        "status": row.status,
                    }
                    for row in runs
                ],
                "events": [
                    {
                        "id": row.id,
                        "run_id": row.run_id,
                        "event_type": row.event_type,
                        "payload_json": _deserialize_payload(row.payload_json),
                        "created_at": _datetime_to_iso(row.created_at),
                    }
                    for row in events
                ],
                "feedback": [
                    {
                        "id": row.id,
                        "run_id": row.run_id,
                        "rating": row.rating,
                        "comment": row.comment,
                        "tester_id": row.tester_id,
                        "task_completed": bool(row.task_completed),
                        "created_at": _datetime_to_iso(row.created_at),
                    }
                    for row in feedback
                ],
            },
        }
        return payload

    def import_bundle(self, bundle: dict[str, Any], mode: str = "merge") -> dict[str, int]:
        if mode not in {"merge", "replace"}:
            raise ValueError("mode must be merge or replace.")

        data = bundle["data"]
        run_rows = data.get("runs", [])
        event_rows = data.get("events", [])
        feedback_rows = data.get("feedback", [])

        with self.session_factory() as session:
            if mode == "replace":
                session.query(EventModel).delete()
                session.query(FeedbackModel).delete()
                session.query(RunModel).delete()
                session.flush()

            for row in run_rows:
                session.merge(
                    RunModel(
                        run_id=row["run_id"],
                        created_at=_normalize_timestamp(row["created_at"]),
                        mechanism_version=row["mechanism_version"],
                        dataset_id=row["dataset_id"],
                        scenario_id=row["scenario_id"],
                        input_json=_serialize_payload(row["input_json"]),
                        output_json=_serialize_payload(row["output_json"]),
                        status=row["status"],
                    )
                )

            for row in event_rows:
                session.merge(
                    EventModel(
                        id=row["id"],
                        run_id=row.get("run_id"),
                        event_type=row["event_type"],
                        payload_json=_serialize_payload(row["payload_json"]),
                        created_at=_normalize_timestamp(row["created_at"]),
                    )
                )

            for row in feedback_rows:
                session.merge(
                    FeedbackModel(
                        id=row["id"],
                        run_id=row["run_id"],
                        rating=row["rating"],
                        comment=row["comment"],
                        tester_id=row.get("tester_id", "anonymous"),
                        task_completed=bool(row.get("task_completed", False)),
                        created_at=_normalize_timestamp(row["created_at"]),
                    )
                )

            session.commit()

        return {
            "runs": len(run_rows),
            "events": len(event_rows),
            "feedback": len(feedback_rows),
        }
