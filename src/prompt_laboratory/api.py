"""FastAPI surface for storing and inspecting Prompt Laboratory runs."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from prompt_laboratory.evaluation import EvaluationReport
from prompt_laboratory.storage import RunStore


class RunCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str


def create_app(database_url: str | None = None) -> FastAPI:
    store = RunStore(database_url or os.getenv("DATABASE_URL", "sqlite:///prompt-lab.db"))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.create_schema()
        yield

    app = FastAPI(
        title="Prompt Laboratory API",
        version="0.5.0",
        description="Persistent evaluation-run API for prompt quality engineering.",
        lifespan=lifespan,
    )
    app.state.store = store

    def get_store() -> RunStore:
        return app.state.store

    StoreDependency = Annotated[RunStore, Depends(get_store)]

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/runs", response_model=RunCreated, status_code=status.HTTP_201_CREATED)
    def create_run(
        report: EvaluationReport,
        run_store: StoreDependency,
    ) -> RunCreated:
        return RunCreated(id=run_store.save(report))

    @app.get("/api/v1/runs")
    def list_runs(
        run_store: StoreDependency,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[dict[str, object]]:
        return run_store.list(limit)

    @app.get("/api/v1/runs/{run_id}", response_model=EvaluationReport)
    def get_run(
        run_id: str,
        run_store: StoreDependency,
    ) -> EvaluationReport:
        report = run_store.get(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return report

    return app


app = create_app()


def run() -> None:
    uvicorn.run("prompt_laboratory.api:app", host="0.0.0.0", port=8000)
