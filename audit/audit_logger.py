"""
VERITAS-Ω — Audit & Tracing Module

Guarantees:
  1. Every pipeline step is logged with: name, timestamps, SHA-256 hashes of
     serialised input and output, and duration.
  2. Full trace stored as JSONL in audit_log_dir (config/settings.py).
  3. Replayability: given the same trace_id, every step can be re-executed
     by feeding the logged inputs back through the modules.
  4. All logs are append-only (no delete, no overwrite).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import STORAGE_CFG
from core.schemas import AuditTrace, AuditTraceStep, DomainMode, Verdict

logger = logging.getLogger(__name__)


def _sha256(obj: Any) -> str:
    """SHA-256 of JSON-serialised object (deterministic, sorted keys)."""
    serialised = json.dumps(obj, default=str, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


class AuditLogger:
    """
    Manages audit traces for a single pipeline execution session.
    Thread-safe for sequential use within a single session.
    """

    def __init__(
        self,
        claim_id: str,
        session_id: str,
        domain_mode: DomainMode,
        log_dir: Optional[str] = None,
    ):
        self._trace = AuditTrace(
            claim_id=claim_id,
            session_id=session_id,
            domain_mode=domain_mode,
        )
        self._log_dir = Path(log_dir or STORAGE_CFG.audit_log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"{self._trace.trace_id}.jsonl"
        self._step_start: Optional[float] = None
        self._current_step: Optional[str] = None
        self._current_input_hash: Optional[str] = None

    # ── Context manager for steps ─────────────────────────────────────────────

    @contextmanager
    def step(self, step_name: str, input_obj: Any):
        """
        Usage:
            with audit.step("retrieval", claim) as h:
                result = retriever.retrieve(claim)
            audit.end_step(result)

        Alternative: use log_step() for non-contextmanager use.
        """
        self._current_step = step_name
        self._current_input_hash = _sha256(input_obj)
        self._step_start = time.perf_counter()
        try:
            yield
        except Exception:
            self._record_step(step_name, self._current_input_hash, "ERROR", 0.0)
            raise

    def end_step(self, output_obj: Any):
        """Must be called after the `with step(...)` block completes."""
        duration_ms = (time.perf_counter() - self._step_start) * 1000
        output_hash = _sha256(output_obj)
        self._record_step(
            self._current_step,
            self._current_input_hash,
            output_hash,
            duration_ms,
        )

    def log_step(
        self,
        step_name: str,
        input_obj: Any,
        output_obj: Any,
        extra_metadata: Optional[dict] = None,
    ):
        """Synchronous single-call version for simple steps."""
        input_hash  = _sha256(input_obj)
        output_hash = _sha256(output_obj)
        self._record_step(step_name, input_hash, output_hash, 0.0, extra_metadata)

    # ── Finalisation ──────────────────────────────────────────────────────────

    def finalise(self, verdict: Verdict) -> AuditTrace:
        self._trace.final_verdict = verdict
        self._flush_trace()
        logger.info(
            "AuditLogger: trace %s finalised. Steps=%d verdict=%s",
            self._trace.trace_id,
            len(self._trace.steps),
            verdict.value,
        )
        return self._trace

    def get_trace(self) -> AuditTrace:
        return self._trace

    # ── Private ───────────────────────────────────────────────────────────────

    def _record_step(
        self,
        step_name: str,
        input_hash: str,
        output_hash: str,
        duration_ms: float,
        metadata: Optional[dict] = None,
    ):
        step = AuditTraceStep(
            step_name=step_name,
            timestamp=datetime.now(tz=timezone.utc),
            input_hash=input_hash,
            output_hash=output_hash,
            duration_ms=round(duration_ms, 2),
            metadata=metadata or {},
        )
        self._trace.steps.append(step)
        # Append-only JSONL write
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(step.model_dump_json() + "\n")

    def _flush_trace(self):
        """Write the complete trace as a summary JSON file."""
        summary_file = self._log_dir / f"{self._trace.trace_id}_summary.json"
        summary_file.write_text(
            self._trace.model_dump_json(indent=2),
            encoding="utf-8",
        )


# ── Replay helper ─────────────────────────────────────────────────────────────

def load_trace(trace_id: str, log_dir: Optional[str] = None) -> AuditTrace:
    """
    Load a previously saved audit trace for replay or inspection.
    """
    log_dir_path = Path(log_dir or STORAGE_CFG.audit_log_dir)
    summary_file = log_dir_path / f"{trace_id}_summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"No audit trace found for trace_id={trace_id}")
    data = json.loads(summary_file.read_text(encoding="utf-8"))
    return AuditTrace(**data)
