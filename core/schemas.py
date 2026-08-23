"""
VERITAS-Ω — Core Data Schemas
All Pydantic models shared across modules.
Every schema is strict (no extra fields allowed).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


# ══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════


class ClaimType(StrEnum):
    FACTUAL = "factual"
    CAUSAL = "causal"
    STATISTICAL = "statistical"
    OPINION = "opinion"


class Verdict(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    UNCERTAIN = "UNCERTAIN"


class EdgeType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class StabilityLabel(StrEnum):
    STABLE = "STABLE"
    MODERATE = "MODERATE"
    UNSTABLE = "UNSTABLE"


class DomainMode(StrEnum):
    GENERAL = "general"
    MEDICAL = "medical"
    LEGAL = "legal"


class ExecutionMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class EvidenceStatus(StrEnum):
    SYNTHETIC = "synthetic"
    RETRIEVED = "retrieved"


# ══════════════════════════════════════════════════════════════════════════════
# CLAIM SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class TemporalScope(BaseModel):
    """
    Temporal scope of a claim.
    start / end: ISO-8601 date strings or None for open bounds.
    """

    start: str | None = None  # e.g. "2020-01-01"
    end: str | None = None  # e.g. "2023-12-31"
    is_current: bool = False  # claim refers to present state

    model_config = {"extra": "forbid"}


class Claim(BaseModel):
    """
    Atomic, machine-verifiable claim produced by the extraction pipeline.
    Schema matches §1 of the system specification exactly.
    """

    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_text: str = Field(..., min_length=5, max_length=4000)
    entities: list[str] = Field(default_factory=list)
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)
    claim_type: ClaimType = ClaimType.FACTUAL
    source_input: str = ""  # original raw text this was extracted from
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class RetrievedDocument(BaseModel):
    """
    A single document returned by the retrieval layer.
    """

    doc_id: str
    url: str
    title: str
    snippet: str = Field(..., max_length=512)
    full_text: str | None = None
    source_domain: str  # FQDN
    published_date: str | None = None  # ISO-8601
    citation_count: int = 0
    bm25_score: float = 0.0
    dense_score: float = 0.0
    fusion_score: float = 0.0  # Reciprocal Rank Fusion score
    trust_score: float = 0.0  # computed by TrustScorer

    model_config = {"extra": "forbid"}


class RetrievalResult(BaseModel):
    claim_id: str
    documents: list[RetrievedDocument] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE GRAPH SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class EvidenceEdge(BaseModel):
    """
    Directed edge in the evidence graph.
    source_id → target_id with typed relationship.
    """

    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str  # node id (claim or doc_id)
    target_id: str  # node id (claim or doc_id)
    edge_type: EdgeType
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_url: str = ""
    reasoning: str = ""  # one-sentence justification

    model_config = {"extra": "forbid"}


class EvidenceNode(BaseModel):
    node_id: str
    node_type: str  # "claim" | "evidence"
    text: str
    trust_score: float = 0.0
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class EvidenceGraph(BaseModel):
    graph_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id: str
    nodes: list[EvidenceNode] = Field(default_factory=list)
    edges: list[EvidenceEdge] = Field(default_factory=list)
    built_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class EvidenceReference(BaseModel):
    """Pointer to a retrieved document used in agent reasoning."""

    doc_id: str
    url: str
    excerpt: str = Field(..., max_length=256)

    model_config = {"extra": "forbid"}


class AgentOutput(BaseModel):
    """
    Structured output produced by a single reasoning agent.
    Free-form text is NOT allowed; all fields must be populated.
    """

    agent_role: Literal["pro", "con", "adversarial"]
    claim_id: str
    stance: Literal["supports", "contradicts", "flags_weakness"]
    key_points: list[str] = Field(..., min_length=1, max_length=5)
    evidence_references: list[EvidenceReference]  # MUST be non-empty
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1, max_length=1024)

    model_config = {"extra": "forbid"}

    @field_validator("evidence_references")
    @classmethod
    def must_have_evidence(cls, v):
        if not v:
            raise ValueError("AgentOutput must cite at least one evidence reference.")
        return v


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class JudgeOutput(BaseModel):
    """
    Final verdict produced by the Judge module.
    Matches §6 of the system specification exactly.
    """

    claim_id: str
    verdict: Verdict
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    uncertainty_score: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int
    aggregated_trust_score: float = Field(..., ge=0.0, le=1.0)
    reasoning_summary: str
    supporting_doc_ids: list[str] = Field(default_factory=list)
    contradicting_doc_ids: list[str] = Field(default_factory=list)
    judged_at: datetime = Field(default_factory=utc_now)
    domain_mode: DomainMode = DomainMode.GENERAL

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def confidence_uncertainty_sum(self):
        total = self.confidence_score + self.uncertainty_score
        if total > 1.001:
            raise ValueError(f"confidence_score + uncertainty_score must be ≤ 1.0; got {total:.3f}")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# CONSISTENCY SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class ConsistencyResult(BaseModel):
    claim_id: str
    run_verdicts: list[Verdict]
    run_confidences: list[float]
    majority_verdict: Verdict
    mean_confidence: float
    confidence_variance: float
    stability_score: float  # 1 - normalized_variance ∈ [0, 1]
    stability_label: StabilityLabel
    n_runs: int

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# CORRECTION SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class CorrectedClaim(BaseModel):
    original_claim_id: str
    original_text: str
    corrected_text: str
    removed_assertions: list[str]  # parts removed because unsupported
    evidence_basis: list[str]  # doc_ids that ground the corrected claim
    correction_note: str
    corrected_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════


class AuditTraceStep(BaseModel):
    step_name: str
    timestamp: datetime = Field(default_factory=utc_now)
    input_hash: str  # SHA-256 of serialized input
    output_hash: str  # SHA-256 of serialized output
    duration_ms: float
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class AuditTrace(BaseModel):
    """
    Pipeline fingerprint summary for a single research run.
    Step inputs and outputs are hashed but intentionally not stored for replay.
    """

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id: str
    session_id: str
    domain_mode: DomainMode
    steps: list[AuditTraceStep] = Field(default_factory=list)
    final_verdict: Verdict | None = None
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL PIPELINE OUTPUT
# ══════════════════════════════════════════════════════════════════════════════


class VeritasResult(BaseModel):
    """
    Complete output of one VERITAS-Ω pipeline execution.
    This is the object returned by the application pipeline.
    """

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_input: str
    claims: list[Claim]
    retrieval_results: list[RetrievalResult]
    evidence_graph: EvidenceGraph | None = None
    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    judge_output: JudgeOutput | None = None
    consistency_result: ConsistencyResult | None = None
    corrected_claim: CorrectedClaim | None = None
    audit_trace: AuditTrace | None = None
    domain_mode: DomainMode = DomainMode.GENERAL
    execution_mode: ExecutionMode
    evidence_status: EvidenceStatus
    pipeline_version: str = "2.1.0"
    completed_at: datetime = Field(default_factory=utc_now)

    model_config = {"extra": "forbid"}
