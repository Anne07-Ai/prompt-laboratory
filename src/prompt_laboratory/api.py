"""FastAPI surface for storing and inspecting Prompt Laboratory runs."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from prompt_laboratory.evaluation import EvaluationReport
from prompt_laboratory.storage import RunStore
from prompt_laboratory.workbench import (
    PromptCatalog,
    ProviderExecutionError,
    compare_prompt,
    execute_prompt,
    provider_options,
)


class RunCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str


class WorkbenchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str
    variables: dict[str, Any]
    provider: str = "mock/echo"


class WorkbenchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str
    prompt_version: str
    rendered_prompt: str
    output: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str
    variables: dict[str, Any]
    providers: list[str]


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str
    prompt_version: str
    rendered_prompt: str
    comparisons: list[dict[str, Any]]


def create_app(
    database_url: str | None = None,
    prompts_dir: str | Path | None = None,
) -> FastAPI:
    store = RunStore(database_url or os.getenv("DATABASE_URL", "sqlite:///prompt-lab.db"))
    catalog = PromptCatalog(prompts_dir or os.getenv("PROMPT_LAB_PROMPTS_DIR", "prompts"))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.create_schema()
        yield

    app = FastAPI(
        title="Prompt Laboratory API",
        version="0.8.0",
        description="Persistent evaluation-run API for prompt quality engineering.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.catalog = catalog

    def get_store() -> RunStore:
        return app.state.store

    StoreDependency = Annotated[RunStore, Depends(get_store)]

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/prompts", tags=["workbench"])
    def list_prompts() -> list[dict[str, Any]]:
        return [prompt.model_dump(mode="json", by_alias=True) for prompt in catalog.all()]

    @app.get("/api/v1/providers", tags=["workbench"])
    def list_providers() -> list[dict[str, Any]]:
        return provider_options()

    @app.post("/api/v1/workbench/execute", response_model=WorkbenchResponse, tags=["workbench"])
    def run_workbench(request: WorkbenchRequest) -> WorkbenchResponse:
        prompt = catalog.get(request.prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found")
        try:
            rendered, generated = execute_prompt(prompt, request.variables, request.provider)
        except ProviderExecutionError as exc:
            error_status = (
                429 if exc.code in {"quota_exceeded", "rate_limited"} else 502
            )
            raise HTTPException(
                status_code=error_status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return WorkbenchResponse(
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            rendered_prompt=rendered,
            output=generated.text,
            provider=generated.provider,
            model=generated.model,
            latency_ms=generated.latency_ms,
            input_tokens=generated.input_tokens,
            output_tokens=generated.output_tokens,
            estimated_cost_usd=generated.estimated_cost_usd,
        )

    @app.post("/api/v1/workbench/compare", response_model=ComparisonResponse, tags=["workbench"])
    def compare_workbench(request: ComparisonRequest) -> ComparisonResponse:
        prompt = catalog.get(request.prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found")
        configured = {item["id"] for item in provider_options() if item["configured"]}
        unavailable = [provider for provider in request.providers if provider not in configured]
        if unavailable:
            raise HTTPException(status_code=422, detail=f"Provider not configured: {unavailable[0]}")
        try:
            rendered, comparisons = compare_prompt(prompt, request.variables, request.providers)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ComparisonResponse(
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            rendered_prompt=rendered,
            comparisons=comparisons,
        )

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
