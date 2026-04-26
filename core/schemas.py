"""
VERITAS-Ω — Core Data Schemas
All Pydantic models shared across modules.
Every schema is strict (no extra fields allowed).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


# ══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ══════════════════════════════════════════════════════════════════════════════

class ClaimType(str, Enum):
    FACTUAL     = "factual"
    CAUSAL      = "causal"
    STATISTICAL = "statistical"
    OPINION     = "opinion"


class Verdict(str, Enum):
    TRUE            = "TRUE"
    FALSE           = "FALSE"
    PARTIALLY_TRUE  = "PARTIALLY_TRUE"
    UNCERTAIN       = "UNCERTAIN"


class EdgeType(str, Enum):
    SUPPORTS     = "supports"
    CONTRADICTS  = "contradicts"
    NEUTRAL      = "neutral"


class StabilityLabel(str, Enum):
    STABLE   = "STABLE"
    MODERATE = "MODERATE"
    UNSTABLE = "UNSTABLE"


class DomainMode(str, Enum):
    GENERAL = "general"
    MEDICAL = "medical"
    LEGAL   = "legal"


# ══════════════════════════════════════════════════════════════════════════════
# CLAIM SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class TemporalScope(BaseModel):
    """
    Temporal scope of a claim.
    start / end: ISO-8601 date strings or None for open bounds.
    """
    start: Optional[str] = None   # e.g. "2020-01-01"
    end:   Optional[str] = None   # e.g. "2023-12-31"
    is_current: bool = False      # claim refers to present state

    model_config = {"extra": "forbid"}


class Claim(BaseModel):
    """
    Atomic, machine-verifiable claim produced by the extraction pipeline.
    Schema matches §1 of the system specification exactly.
    """
    claim_id:      str       = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_text:    str       = Field(..., min_length=5)
    entities:      List[str] = Field(default_factory=list)
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)
    claim_type:    ClaimType = ClaimType.FACTUAL
    source_input:  str       = ""     # original raw text this was extracted from
    created_at:    datetime  = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class RetrievedDocument(BaseModel):
    """
    A single document returned by the retrieval layer.
    """
    doc_id:        str
    url:           str
    title:         str
    snippet:       str            # ≤ 512 chars excerpt
    full_text:     Optional[str] = None
    source_domain: str            # FQDN
    published_date: Optional[str] = None   # ISO-8601
    citation_count: int          = 0
    bm25_score:    float         = 0.0
    dense_score:   float         = 0.0
    fusion_score:  float         = 0.0   # Reciprocal Rank Fusion score
    trust_score:   float         = 0.0   # computed by TrustScorer

    model_config = {"extra": "forbid"}


class RetrievalResult(BaseModel):
    claim_id:  str
    documents: List[RetrievedDocument] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE GRAPH SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class EvidenceEdge(BaseModel):
    """
    Directed edge in the evidence graph.
    source_id → target_id with typed relationship.
    """
    edge_id:    str   = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id:  str   # node id (claim or doc_id)
    target_id:  str   # node id (claim or doc_id)
    edge_type:  EdgeType
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_url: str   = ""
    reasoning:  str   = ""   # one-sentence justification

    model_config = {"extra": "forbid"}


class EvidenceNode(BaseModel):
    node_id:    str
    node_type:  str    # "claim" | "evidence"
    text:       str
    trust_score: float = 0.0
    metadata:   Dict   = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class EvidenceGraph(BaseModel):
    graph_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id:   str
    nodes:      List[EvidenceNode] = Field(default_factory=list)
    edges:      List[EvidenceEdge] = Field(default_factory=list)
    built_at:   datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class EvidenceReference(BaseModel):
    """Pointer to a retrieved document used in agent reasoning."""
    doc_id:  str
    url:     str
    excerpt: str   # ≤ 256 chars

    model_config = {"extra": "forbid"}


class AgentOutput(BaseModel):
    """
    Structured output produced by a single reasoning agent.
    Free-form text is NOT allowed; all fields must be populated.
    """
    agent_role:          str                      # "pro" | "con" | "adversarial"
    claim_id:            str
    stance:              str                      # "supports" | "contradicts" | "flags_weakness"
    key_points:          List[str]                # 1-5 bullet points
    evidence_references: List[EvidenceReference]  # MUST be non-empty
    confidence:          float = Field(..., ge=0.0, le=1.0)
    reasoning:           str                      # ≤ 1024 chars structured paragraph

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
    claim_id:             str
    verdict:              Verdict
    confidence_score:     float = Field(..., ge=0.0, le=1.0)
    uncertainty_score:    float = Field(..., ge=0.0, le=1.0)
    evidence_count:       int
    aggregated_trust_score: float = Field(..., ge=0.0, le=1.0)
    reasoning_summary:    str
    supporting_doc_ids:   List[str] = Field(default_factory=list)
    contradicting_doc_ids: List[str] = Field(default_factory=list)
    judged_at:            datetime = Field(default_factory=datetime.utcnow)
    domain_mode:          DomainMode = DomainMode.GENERAL

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def confidence_uncertainty_sum(self):
        total = self.confidence_score + self.uncertainty_score
        if total > 1.001:
            raise ValueError(
                f"confidence_score + uncertainty_score must be ≤ 1.0; got {total:.3f}"
            )
        return self


# ══════════════════════════════════════════════════════════════════════════════
# CONSISTENCY SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ConsistencyResult(BaseModel):
    claim_id:          str
    run_verdicts:      List[Verdict]
    run_confidences:   List[float]
    majority_verdict:  Verdict
    mean_confidence:   float
    confidence_variance: float
    stability_score:   float     # 1 - normalized_variance ∈ [0, 1]
    stability_label:   StabilityLabel
    n_runs:            int

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# CORRECTION SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class CorrectedClaim(BaseModel):
    original_claim_id:  str
    original_text:      str
    corrected_text:     str
    removed_assertions: List[str]   # parts removed because unsupported
    evidence_basis:     List[str]   # doc_ids that ground the corrected claim
    correction_note:    str
    corrected_at:       datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class AuditTraceStep(BaseModel):
    step_name:  str
    timestamp:  datetime = Field(default_factory=datetime.utcnow)
    input_hash: str      # SHA-256 of serialized input
    output_hash: str     # SHA-256 of serialized output
    duration_ms: float
    metadata:   Dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class AuditTrace(BaseModel):
    """
    Full pipeline trace for a single claim verification run.
    Supports replayability: every step's input/output is hashed.
    """
    trace_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id:   str
    session_id: str
    domain_mode: DomainMode
    steps:      List[AuditTraceStep] = Field(default_factory=list)
    final_verdict: Optional[Verdict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


# ══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL PIPELINE OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

class VeritasResult(BaseModel):
    """
    Complete output of one VERITAS-Ω pipeline execution.
    This is the object returned by the API endpoint.
    """
    session_id:          str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_input:           str
    claims:              List[Claim]
    retrieval_results:   List[RetrievalResult]
    evidence_graph:      Optional[EvidenceGraph] = None
    agent_outputs:       List[AgentOutput] = Field(default_factory=list)
    judge_output:        Optional[JudgeOutput] = None
    consistency_result:  Optional[ConsistencyResult] = None
    corrected_claim:     Optional[CorrectedClaim] = None
    audit_trace:         Optional[AuditTrace] = None
    domain_mode:         DomainMode = DomainMode.GENERAL
    pipeline_version:    str = "1.0.0"
    completed_at:        datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}
