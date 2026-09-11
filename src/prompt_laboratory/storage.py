"""Persistence boundary for evaluation reports.

The service uses SQLite for zero-configuration development and PostgreSQL in Docker/production.
Only this module knows about SQLAlchemy, keeping evaluation logic storage-independent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from prompt_laboratory.evaluation import EvaluationReport


class Base(DeclarativeBase):
    pass


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    prompt_id: Mapped[str] = mapped_column(String(255), index=True)
    prompt_version: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(255), index=True)
    pass_rate: Mapped[float] = mapped_column(Float)
    average_score: Mapped[float] = mapped_column(Float)
    total_latency_ms: Mapped[float] = mapped_column(Float)
    estimated_cost_usd: Mapped[float] = mapped_column(Float)
    total_cases: Mapped[int] = mapped_column(Integer)
    report_json: Mapped[str] = mapped_column(Text)


class RunStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def save(self, report: EvaluationReport) -> str:
        run_id = str(uuid4())
        row = EvaluationRun(
            id=run_id,
            created_at=report.created_at.astimezone(UTC),
            prompt_id=report.prompt_id,
            prompt_version=report.prompt_version,
            provider=report.provider,
            pass_rate=report.summary.pass_rate,
            average_score=report.summary.average_score,
            total_latency_ms=report.summary.total_latency_ms,
            estimated_cost_usd=report.summary.estimated_cost_usd,
            total_cases=report.summary.total_cases,
            report_json=report.model_dump_json(),
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
        return run_id

    def get(self, run_id: str) -> EvaluationReport | None:
        with Session(self.engine) as session:
            row = session.get(EvaluationRun, run_id)
            return EvaluationReport.model_validate_json(row.report_json) if row else None

    def list(self, limit: int = 100) -> list[dict[str, object]]:
        statement = select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit)
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
            return [
                {
                    "id": row.id,
                    "created_at": row.created_at,
                    "prompt_id": row.prompt_id,
                    "prompt_version": row.prompt_version,
                    "provider": row.provider,
                    "pass_rate": row.pass_rate,
                    "average_score": row.average_score,
                    "total_latency_ms": row.total_latency_ms,
                    "estimated_cost_usd": row.estimated_cost_usd,
                    "total_cases": row.total_cases,
                }
                for row in rows
            ]
