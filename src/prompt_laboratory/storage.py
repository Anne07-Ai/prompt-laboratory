"""Persistence for users, workspaces, evaluation reports, and workbench experiments."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from prompt_laboratory.evaluation import EvaluationReport


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
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


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    prompt_id: Mapped[str] = mapped_column(String(255), index=True)
    prompt_version: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20))
    rendered_prompt: Mapped[str] = mapped_column(Text)
    request_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)


class RunStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    def create_schema(self) -> None:
        """Upgrade a new or existing database to the latest Alembic revision."""
        config_path = Path(os.getenv("PROMPT_LAB_ALEMBIC_INI", "alembic.ini")).resolve()
        if not config_path.exists():
            raise RuntimeError(f"Alembic configuration not found: {config_path}")

        config = Config(str(config_path))
        config.set_main_option("script_location", str(config_path.parent / "migrations"))
        config.set_main_option("sqlalchemy.url", self.database_url.replace("%", "%%"))

        existing_tables = set(inspect(self.engine).get_table_names())
        legacy_tables = {"users", "workspaces", "workspace_memberships", "evaluation_runs"}
        if "alembic_version" not in existing_tables and legacy_tables.issubset(existing_tables):
            command.stamp(config, "0001")
        elif existing_tables and "alembic_version" not in existing_tables:
            unexpected = ", ".join(sorted(existing_tables))
            raise RuntimeError(f"Database has an unsupported unmigrated schema: {unexpected}")

        command.upgrade(config, "head")

    def create_user_with_workspace(
        self, email: str, display_name: str, password_hash: str, workspace_name: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        now = datetime.now(UTC)
        user = User(
            id=str(uuid4()),
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            created_at=now,
        )
        workspace = Workspace(id=str(uuid4()), name=workspace_name.strip(), created_at=now)
        membership = WorkspaceMembership(
            id=str(uuid4()), workspace_id=workspace.id, user_id=user.id, role="owner"
        )
        with Session(self.engine, expire_on_commit=False) as session:
            session.add_all([user, workspace, membership])
            session.commit()

        return self._user_dict(user), self._workspace_dict(workspace, "owner")

    def find_user_by_email(self, email: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            row = session.scalar(select(User).where(User.email == email.strip().lower()))
            return self._user_dict(row, include_password=True) if row else None

    def get_user(self, user_id: str) -> dict[str, object] | None:
        with Session(self.engine) as session:
            row = session.get(User, user_id)
            return self._user_dict(row) if row else None

    def list_workspaces(self, user_id: str) -> list[dict[str, object]]:
        statement = (
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(Workspace.created_at)
        )
        with Session(self.engine) as session:
            return [self._workspace_dict(row, role) for row, role in session.execute(statement)]

    def create_workspace(self, user_id: str, name: str) -> dict[str, object]:
        workspace = Workspace(id=str(uuid4()), name=name.strip(), created_at=datetime.now(UTC))
        membership = WorkspaceMembership(
            id=str(uuid4()), workspace_id=workspace.id, user_id=user_id, role="owner"
        )
        with Session(self.engine, expire_on_commit=False) as session:
            session.add_all([workspace, membership])
            session.commit()
        return self._workspace_dict(workspace, "owner")

    def membership(self, user_id: str, workspace_id: str) -> dict[str, object] | None:
        statement = select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        with Session(self.engine) as session:
            row = session.scalar(statement)
            return (
                {"workspace_id": row.workspace_id, "user_id": row.user_id, "role": row.role}
                if row
                else None
            )

    def save(self, report: EvaluationReport, workspace_id: str | None = None) -> str:
        run_id = str(uuid4())
        row = EvaluationRun(
            id=run_id,
            workspace_id=workspace_id,
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

    def get(self, run_id: str, workspace_id: str | None = None) -> EvaluationReport | None:
        statement = select(EvaluationRun).where(EvaluationRun.id == run_id)
        if workspace_id is not None:
            statement = statement.where(EvaluationRun.workspace_id == workspace_id)
        with Session(self.engine) as session:
            row = session.scalar(statement)
            return EvaluationReport.model_validate_json(row.report_json) if row else None

    def list(
        self, limit: int = 100, workspace_id: str | None = None
    ) -> list[dict[str, object]]:
        statement = select(EvaluationRun)
        if workspace_id is not None:
            statement = statement.where(EvaluationRun.workspace_id == workspace_id)
        statement = statement.order_by(EvaluationRun.created_at.desc()).limit(limit)
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

    def save_experiment(
        self,
        *,
        workspace_id: str,
        user_id: str,
        prompt_id: str,
        prompt_version: str,
        mode: str,
        rendered_prompt: str,
        request: dict[str, object],
        result: dict[str, object],
    ) -> str:
        experiment_id = str(uuid4())
        row = Experiment(
            id=experiment_id,
            workspace_id=workspace_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            mode=mode,
            rendered_prompt=rendered_prompt,
            request_json=json.dumps(request, separators=(",", ":"), sort_keys=True),
            result_json=json.dumps(result, separators=(",", ":"), sort_keys=True),
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
        return experiment_id

    def list_experiments(self, workspace_id: str, limit: int = 100) -> list[dict[str, object]]:
        statement = (
            select(Experiment)
            .where(Experiment.workspace_id == workspace_id)
            .order_by(Experiment.created_at.desc())
            .limit(limit)
        )
        with Session(self.engine) as session:
            return [
                self._experiment_dict(row, include_payload=False)
                for row in session.scalars(statement)
            ]

    def get_experiment(self, experiment_id: str, workspace_id: str) -> dict[str, object] | None:
        statement = select(Experiment).where(
            Experiment.id == experiment_id,
            Experiment.workspace_id == workspace_id,
        )
        with Session(self.engine) as session:
            row = session.scalar(statement)
            return self._experiment_dict(row, include_payload=True) if row else None

    @staticmethod
    def _user_dict(row: User, include_password: bool = False) -> dict[str, object]:
        value: dict[str, object] = {
            "id": row.id,
            "email": row.email,
            "display_name": row.display_name,
            "created_at": row.created_at,
        }
        if include_password:
            value["password_hash"] = row.password_hash
        return value

    @staticmethod
    def _workspace_dict(row: Workspace, role: str) -> dict[str, object]:
        return {"id": row.id, "name": row.name, "role": role, "created_at": row.created_at}

    @staticmethod
    def _experiment_dict(row: Experiment, include_payload: bool) -> dict[str, object]:
        value: dict[str, object] = {
            "id": row.id,
            "workspace_id": row.workspace_id,
            "user_id": row.user_id,
            "created_at": row.created_at,
            "prompt_id": row.prompt_id,
            "prompt_version": row.prompt_version,
            "mode": row.mode,
        }
        if include_payload:
            value.update(
                {
                    "rendered_prompt": row.rendered_prompt,
                    "request": json.loads(row.request_json),
                    "result": json.loads(row.result_json),
                }
            )
        return value
