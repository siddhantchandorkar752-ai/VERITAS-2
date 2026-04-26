"""
VERITAS-Ω — FastAPI REST Interface

Endpoints
─────────
POST /verify         — full pipeline run
GET  /trace/{id}     — fetch audit trace by trace_id
GET  /health         — liveness probe
POST /verify/batch   — batch multiple claims (async)

All responses follow a standardised envelope:
  {
    "status": "ok" | "error",
    "data":   <payload>,
    "error":  null | "<message>"
  }
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from audit.audit_logger import load_trace
from core.pipeline import VeritasPipeline
from core.schemas import DomainMode, VeritasResult

logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VERITAS-Ω API",
    description="Auditable Multi-Agent Truth Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton pipeline (initialised at startup)
_pipeline: Optional[VeritasPipeline] = None


@app.on_event("startup")
async def startup_event():
    global _pipeline
    api_key = os.getenv("OPENAI_API_KEY")
    _pipeline = VeritasPipeline(
        openai_api_key=api_key,
        run_consistency=True,
        n_consistency_runs=int(os.getenv("VERITAS_CONSISTENCY_RUNS", "3")),
    )
    logger.info("VERITAS-Ω pipeline initialised.")


# ── Request / Response schemas ────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Raw text containing claim(s).")
    domain_mode: DomainMode = DomainMode.GENERAL
    session_id: Optional[str] = None

    model_config = {"extra": "forbid"}


class BatchVerifyRequest(BaseModel):
    items: List[VerifyRequest] = Field(..., min_length=1, max_length=20)

    model_config = {"extra": "forbid"}


def _envelope(data=None, error: Optional[str] = None) -> dict:
    return {
        "status": "ok" if error is None else "error",
        "data":   data,
        "error":  error,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return _envelope(data={"service": "VERITAS-Ω", "status": "running"})


@app.post("/verify", response_model=dict)
async def verify(request: VerifyRequest):
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")
    try:
        result: VeritasResult = _pipeline.run(
            raw_input=request.text,
            domain_mode=request.domain_mode,
            session_id=request.session_id,
        )
        return _envelope(data=result.model_dump(mode="json"))
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content=_envelope(error=str(exc)),
        )
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope(error=f"Internal pipeline error: {exc}"),
        )


@app.get("/trace/{trace_id}", response_model=dict)
async def get_trace(trace_id: str):
    try:
        trace = load_trace(trace_id)
        return _envelope(data=trace.model_dump(mode="json"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found.")
    except Exception as exc:
        logger.exception("Trace load error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/verify/batch", response_model=dict)
async def verify_batch(request: BatchVerifyRequest):
    """
    Sequential batch processing.
    For production, replace with a proper task queue (e.g., Celery + Redis).
    """
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    results = []
    errors = []
    for item in request.items:
        try:
            r = _pipeline.run(
                raw_input=item.text,
                domain_mode=item.domain_mode,
                session_id=item.session_id,
            )
            results.append(r.model_dump(mode="json"))
        except Exception as exc:
            errors.append({"text": item.text[:80], "error": str(exc)})

    return _envelope(data={"results": results, "errors": errors})
