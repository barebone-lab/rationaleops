"""FastAPI surface for the RationaleOps interactive workflow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from rationaleops.datahub_mcp import DataHubMcpReader
from rationaleops.llm import DeepSeekConfigurationError, DeepSeekResponseError
from rationaleops.service import (
    DEFAULT_SESSION_ID,
    RationaleOpsService,
    WorkflowGuardError,
    WorkflowNotFoundError,
)
from rationaleops.storage import WorkflowStore

load_dotenv()


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActorRequest(StrictRequest):
    actor: str = Field(min_length=1)
    session_id: str = DEFAULT_SESSION_ID


class WriteBackRequest(ActorRequest):
    mode: Literal["fixture", "datahub"] = "fixture"


class AnswerRequest(StrictRequest):
    answer: str = Field(min_length=1, max_length=8000)
    mode: Literal["recorded", "live"] = "recorded"
    session_id: str = DEFAULT_SESSION_ID


def _default_store_path() -> Path:
    return Path(os.getenv("RATIONALEOPS_DB_PATH", ".rationaleops/state.db"))


def create_app(
    *,
    store_path: Path | None = None,
    artifact_root: Path | None = None,
) -> FastAPI:
    store_path = store_path or _default_store_path()
    artifact_root = artifact_root or store_path.parent / "sessions"
    service = RationaleOpsService(
        WorkflowStore(store_path),
        artifact_root=artifact_root,
    )
    application = FastAPI(
        title="RationaleOps API",
        version="0.2.0",
        description=(
            "Human-grounded decision contracts for business logic discovered "
            "through DataHub."
        ),
    )
    origins = os.getenv(
        "RATIONALEOPS_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "rationaleops",
            "version": application.version,
            "datahub_server": os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
            "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        }

    @application.get("/api/demo")
    def get_demo(session_id: str = DEFAULT_SESSION_ID) -> dict[str, object]:
        return service.get(session_id)

    @application.post("/api/demo/reset")
    def reset_demo(session_id: str = DEFAULT_SESSION_ID) -> dict[str, object]:
        return service.reset(session_id)

    @application.post("/api/decisions/{decision_id}/select")
    def select_decision(
        decision_id: str,
        session_id: str = DEFAULT_SESSION_ID,
    ) -> dict[str, object]:
        try:
            return service.select_decision(decision_id, session_id=session_id)
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/interviews/{decision_id}/answer")
    def answer_interview(
        decision_id: str,
        request: AnswerRequest,
    ) -> dict[str, object]:
        try:
            return service.answer_interview(
                decision_id,
                answer=request.answer,
                mode=request.mode,
                session_id=request.session_id,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (DeepSeekConfigurationError, DeepSeekResponseError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post("/api/contracts/{contract_id}/confirm")
    def confirm_contract(
        contract_id: str,
        request: ActorRequest,
    ) -> dict[str, object]:
        try:
            return service.confirm_contract(
                contract_id,
                actor=request.actor,
                session_id=request.session_id,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkflowGuardError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/artifacts/{artifact_id}/approve")
    def approve_artifact(
        artifact_id: str,
        request: ActorRequest,
    ) -> dict[str, object]:
        try:
            return service.approve_artifact(
                artifact_id,
                actor=request.actor,
                session_id=request.session_id,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkflowGuardError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/contracts/{contract_id}/writeback")
    def write_back(
        contract_id: str,
        request: WriteBackRequest,
    ) -> dict[str, object]:
        try:
            return service.write_back(
                contract_id,
                actor=request.actor,
                mode=request.mode,
                session_id=request.session_id,
            )
        except WorkflowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WorkflowGuardError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"DataHub write-back failed: {exc}",
            ) from exc

    @application.get("/api/datahub/context")
    async def datahub_context(
        dataset_urn: str,
    ) -> dict[str, object]:
        reader = DataHubMcpReader(
            server=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
            token=os.getenv("DATAHUB_GMS_TOKEN"),
        )
        try:
            context = await reader.get_query_context(dataset_urn)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"DataHub MCP read failed: {exc}",
            ) from exc
        return context.model_dump(mode="json")

    return application


app = create_app()


def run() -> None:
    """Run the local API server installed by the project entry point."""

    uvicorn.run(
        "rationaleops.api:app",
        host=os.getenv("RATIONALEOPS_HOST", "127.0.0.1"),
        port=int(os.getenv("RATIONALEOPS_PORT", "8000")),
        reload=False,
    )
