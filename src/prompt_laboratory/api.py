"""Authenticated FastAPI surface for Prompt Laboratory."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from prompt_laboratory.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from prompt_laboratory.evaluation import EvaluationReport
from prompt_laboratory.storage import RunStore
from prompt_laboratory.workbench import (
    PromptCatalog,
    ProviderExecutionError,
    compare_prompt,
    execute_prompt,
    provider_options,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    email: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    workspace_name: str = Field(min_length=1, max_length=120)


class LoginRequest(StrictModel):
    email: str
    password: str


class WorkspaceRequest(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class AuthResponse(StrictModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]
    workspaces: list[dict[str, Any]]


class RunCreated(StrictModel):
    id: str


class WorkbenchRequest(StrictModel):
    prompt_id: str
    variables: dict[str, Any]
    provider: str = "mock/echo"


class WorkbenchResponse(StrictModel):
    experiment_id: str
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


class ComparisonRequest(StrictModel):
    prompt_id: str
    variables: dict[str, Any]
    providers: list[str]


class ComparisonResponse(StrictModel):
    experiment_id: str
    prompt_id: str
    prompt_version: str
    rendered_prompt: str
    comparisons: list[dict[str, Any]]


def create_app(
    database_url: str | None = None,
    prompts_dir: str | Path | None = None,
    auth_secret: str | None = None,
) -> FastAPI:
    store = RunStore(database_url or os.getenv("DATABASE_URL", "sqlite:///prompt-lab.db"))
    catalog = PromptCatalog(prompts_dir or os.getenv("PROMPT_LAB_PROMPTS_DIR", "prompts"))
    configured_secret = auth_secret or os.getenv("PROMPT_LAB_AUTH_SECRET", "")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.create_schema()
        yield

    app = FastAPI(
        title="Prompt Laboratory API",
        version="0.9.0",
        description="Authenticated, workspace-isolated prompt quality engineering API.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.catalog = catalog
    app.state.auth_secret = configured_secret
    bearer = HTTPBearer(auto_error=False)

    def get_store() -> RunStore:
        return app.state.store

    StoreDependency = Annotated[RunStore, Depends(get_store)]

    def require_secret() -> str:
        if len(app.state.auth_secret) < 32:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        return app.state.auth_secret

    def current_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        run_store: StoreDependency,
    ) -> dict[str, object]:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            claims = decode_access_token(credentials.credentials, require_secret())
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        user = run_store.get_user(claims.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User account no longer exists")
        return user

    UserDependency = Annotated[dict[str, object], Depends(current_user)]

    def current_workspace(
        user: UserDependency,
        run_store: StoreDependency,
        workspace_id: Annotated[str | None, Header(alias="X-Workspace-ID")] = None,
    ) -> str:
        if not workspace_id:
            raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
        if run_store.membership(str(user["id"]), workspace_id) is None:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        return workspace_id

    WorkspaceDependency = Annotated[str, Depends(current_workspace)]

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=201, tags=["auth"])
    def register(request: RegisterRequest, run_store: StoreDependency) -> AuthResponse:
        email = request.email.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        try:
            user, _ = run_store.create_user_with_workspace(
                email,
                request.display_name,
                hash_password(request.password),
                request.workspace_name,
            )
        except (IntegrityError, ValueError) as exc:
            if isinstance(exc, IntegrityError):
                raise HTTPException(status_code=409, detail="An account already exists") from exc
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        workspaces = run_store.list_workspaces(str(user["id"]))
        return AuthResponse(
            access_token=create_access_token(str(user["id"]), require_secret()),
            user=user,
            workspaces=workspaces,
        )

    @app.post("/api/v1/auth/login", response_model=AuthResponse, tags=["auth"])
    def login(request: LoginRequest, run_store: StoreDependency) -> AuthResponse:
        stored = run_store.find_user_by_email(request.email)
        if stored is None or not verify_password(request.password, str(stored["password_hash"])):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user = {key: value for key, value in stored.items() if key != "password_hash"}
        return AuthResponse(
            access_token=create_access_token(str(user["id"]), require_secret()),
            user=user,
            workspaces=run_store.list_workspaces(str(user["id"])),
        )

    @app.get("/api/v1/auth/me", tags=["auth"])
    def me(user: UserDependency, run_store: StoreDependency) -> dict[str, object]:
        return {"user": user, "workspaces": run_store.list_workspaces(str(user["id"]))}

    @app.get("/api/v1/workspaces", tags=["workspaces"])
    def list_workspaces(user: UserDependency, run_store: StoreDependency) -> list[dict[str, object]]:
        return run_store.list_workspaces(str(user["id"]))

    @app.post("/api/v1/workspaces", status_code=201, tags=["workspaces"])
    def create_workspace(
        request: WorkspaceRequest, user: UserDependency, run_store: StoreDependency
    ) -> dict[str, object]:
        return run_store.create_workspace(str(user["id"]), request.name)

    @app.get("/api/v1/prompts", tags=["workbench"])
    def list_prompts(_: UserDependency) -> list[dict[str, Any]]:
        return [prompt.model_dump(mode="json", by_alias=True) for prompt in catalog.all()]

    @app.get("/api/v1/providers", tags=["workbench"])
    def list_providers(_: UserDependency) -> list[dict[str, Any]]:
        return provider_options()

    @app.post("/api/v1/workbench/execute", response_model=WorkbenchResponse, tags=["workbench"])
    def run_workbench(
        request: WorkbenchRequest,
        run_store: StoreDependency,
        user: UserDependency,
        workspace_id: WorkspaceDependency,
    ) -> WorkbenchResponse:
        prompt = catalog.get(request.prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found")
        try:
            rendered, generated = execute_prompt(prompt, request.variables, request.provider)
        except ProviderExecutionError as exc:
            error_status = 429 if exc.code in {"quota_exceeded", "rate_limited"} else 502
            raise HTTPException(
                status_code=error_status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        result = {
            "output": generated.text,
            "provider": generated.provider,
            "model": generated.model,
            "latency_ms": generated.latency_ms,
            "input_tokens": generated.input_tokens,
            "output_tokens": generated.output_tokens,
            "estimated_cost_usd": generated.estimated_cost_usd,
        }
        experiment_id = run_store.save_experiment(
            workspace_id=workspace_id,
            user_id=str(user["id"]),
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            mode="single",
            rendered_prompt=rendered,
            request=request.model_dump(mode="json"),
            result=result,
        )
        return WorkbenchResponse(
            experiment_id=experiment_id,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            rendered_prompt=rendered,
            **result,
        )

    @app.post("/api/v1/workbench/compare", response_model=ComparisonResponse, tags=["workbench"])
    def compare_workbench(
        request: ComparisonRequest,
        run_store: StoreDependency,
        user: UserDependency,
        workspace_id: WorkspaceDependency,
    ) -> ComparisonResponse:
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

        experiment_id = run_store.save_experiment(
            workspace_id=workspace_id,
            user_id=str(user["id"]),
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            mode="comparison",
            rendered_prompt=rendered,
            request=request.model_dump(mode="json"),
            result={"comparisons": comparisons},
        )
        return ComparisonResponse(
            experiment_id=experiment_id,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            rendered_prompt=rendered,
            comparisons=comparisons,
        )

    @app.get("/api/v1/experiments", tags=["workbench"])
    def list_experiments(
        run_store: StoreDependency,
        _: UserDependency,
        workspace_id: WorkspaceDependency,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[dict[str, object]]:
        return run_store.list_experiments(workspace_id, limit)

    @app.get("/api/v1/experiments/{experiment_id}", tags=["workbench"])
    def get_experiment(
        experiment_id: str,
        run_store: StoreDependency,
        _: UserDependency,
        workspace_id: WorkspaceDependency,
    ) -> dict[str, object]:
        experiment = run_store.get_experiment(experiment_id, workspace_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return experiment

    @app.post("/api/v1/runs", response_model=RunCreated, status_code=status.HTTP_201_CREATED)
    def create_run(
        report: EvaluationReport,
        run_store: StoreDependency,
        _: UserDependency,
        workspace_id: WorkspaceDependency,
    ) -> RunCreated:
        return RunCreated(id=run_store.save(report, workspace_id))

    @app.get("/api/v1/runs")
    def list_runs(
        run_store: StoreDependency,
        _: UserDependency,
        workspace_id: WorkspaceDependency,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[dict[str, object]]:
        return run_store.list(limit, workspace_id)

    @app.get("/api/v1/runs/{run_id}", response_model=EvaluationReport)
    def get_run(
        run_id: str,
        run_store: StoreDependency,
        _: UserDependency,
        workspace_id: WorkspaceDependency,
    ) -> EvaluationReport:
        report = run_store.get(run_id, workspace_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return report

    return app


app = create_app()


def run() -> None:
    uvicorn.run("prompt_laboratory.api:app", host="0.0.0.0", port=8000)
