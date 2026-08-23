"""
VERITAS-Ω — Audit & Tracing Module

Behavior:
  1. Every pipeline step is logged with: name, timestamps, SHA-256 hashes of
     serialised input and output, and duration.
  2. Full trace stored as JSONL in audit_log_dir (config/settings.py).
  3. Hashes are integrity fingerprints, not proof that a verdict is correct and
     not a replay log (raw inputs and outputs are intentionally not persisted).
  4. JSONL steps are appended locally; operators must provide immutable storage
     if tamper resistance is required.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

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
        log_dir: str | None = None,
    ):
        self._trace = AuditTrace(
            claim_id=claim_id,
            session_id=session_id,
            domain_mode=domain_mode,
        )
        self._log_dir = Path(log_dir or STORAGE_CFG.audit_log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"{self._trace.trace_id}.jsonl"
        self._step_start: float | None = None
        self._current_step: str | None = None
        self._current_input_hash: str | None = None

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
            duration_ms = (time.perf_counter() - self._step_start) * 1000
            self._record_step(step_name, self._current_input_hash, "ERROR", duration_ms)
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
        extra_metadata: dict | None = None,
    ):
        """Synchronous single-call version for simple steps."""
        input_hash = _sha256(input_obj)
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
        metadata: dict | None = None,
    ):
        step = AuditTraceStep(
            step_name=step_name,
            timestamp=datetime.now(tz=UTC),
            input_hash=input_hash,
            output_hash=output_hash,
            duration_ms=round(duration_ms, 2),
            metadata=metadata or {},
        )
        self._trace.steps.append(step)
        # Append one local JSONL step. The file is not immutable storage.
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(step.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _flush_trace(self):
        """Write the complete trace as a summary JSON file."""
        summary_file = self._log_dir / f"{self._trace.trace_id}_summary.json"
        temporary_file = summary_file.with_suffix(".tmp")
        temporary_file.write_text(
            self._trace.model_dump_json(indent=2),
            encoding="utf-8",
        )
        os.replace(temporary_file, summary_file)


# ── Inspection helper ─────────────────────────────────────────────────────────


def load_trace(trace_id: str, log_dir: str | None = None) -> AuditTrace:
    """
    Load a previously saved audit trace for inspection.
    """
    try:
        normalized_trace_id = str(UUID(trace_id))
    except ValueError as error:
        raise ValueError("trace_id must be a UUID") from error
    log_dir_path = Path(log_dir or STORAGE_CFG.audit_log_dir).resolve()
    summary_file = (log_dir_path / f"{normalized_trace_id}_summary.json").resolve()
    if summary_file.parent != log_dir_path:
        raise ValueError("trace_id resolved outside the audit directory")
    if not summary_file.exists():
        raise FileNotFoundError(f"No audit trace found for trace_id={trace_id}")
    data = json.loads(summary_file.read_text(encoding="utf-8"))
    return AuditTrace(**data)
