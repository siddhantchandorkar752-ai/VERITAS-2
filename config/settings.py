"""
VERITAS-Ω Configuration Module
All tunable constants, thresholds, and environment bindings.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


# ─── Verdict Thresholds ───────────────────────────────────────────────────────

class DomainMode(str, Enum):
    GENERAL = "general"
    MEDICAL = "medical"
    LEGAL   = "legal"


@dataclass(frozen=True)
class VerdictThresholds:
    """
    Confidence thresholds that gate verdict categories.
    TRUE       : confidence >= true_min
    FALSE      : confidence <= false_max
    PARTIALLY_TRUE : false_max < confidence < true_min AND uncertainty <= partial_max_uncertainty
    UNCERTAIN  : otherwise
    """
    true_min:               float
    false_max:              float
    partial_max_uncertainty: float
    min_evidence_count:     int
    trust_score_floor:      float   # minimum aggregated trust to accept verdict


DOMAIN_THRESHOLDS: Dict[DomainMode, VerdictThresholds] = {
    DomainMode.GENERAL: VerdictThresholds(
        true_min=0.72,
        false_max=0.28,
        partial_max_uncertainty=0.45,
        min_evidence_count=2,
        trust_score_floor=0.40,
    ),
    DomainMode.MEDICAL: VerdictThresholds(
        true_min=0.85,
        false_max=0.15,
        partial_max_uncertainty=0.30,
        min_evidence_count=4,
        trust_score_floor=0.65,
    ),
    DomainMode.LEGAL: VerdictThresholds(
        true_min=0.80,
        false_max=0.20,
        partial_max_uncertainty=0.35,
        min_evidence_count=3,
        trust_score_floor=0.55,
    ),
}


# ─── Retrieval ────────────────────────────────────────────────────────────────

@dataclass
class RetrievalConfig:
    top_k_bm25:   int   = 20     # candidates from BM25
    top_k_dense:  int   = 20     # candidates from dense vector search
    top_k_fusion: int   = 10     # final results after Reciprocal Rank Fusion
    rrf_k:        float = 60.0   # RRF constant (standard = 60)
    dedup_cosine_threshold: float = 0.92  # cosine sim above which docs are duplicate


RETRIEVAL_CFG = RetrievalConfig()


# ─── Trust Score Weights ──────────────────────────────────────────────────────

@dataclass
class TrustWeights:
    """
    Weights in the TrustScore linear combination.
    Must sum to 1.0 for normalized output.
    w_da  = domain_authority weight
    w_cc  = citation_count weight
    w_rec = recency weight
    w_csa = cross_source_agreement weight
    """
    w_da:  float = 0.30
    w_cc:  float = 0.25
    w_rec: float = 0.20
    w_csa: float = 0.25

    def __post_init__(self):
        total = self.w_da + self.w_cc + self.w_rec + self.w_csa
        assert abs(total - 1.0) < 1e-6, f"Weights must sum to 1.0; got {total}"


TRUST_WEIGHTS = TrustWeights()

# Recency half-life in days (older docs decay exponentially)
RECENCY_HALF_LIFE_DAYS: float = 365.0


# ─── Consistency Layer ────────────────────────────────────────────────────────

@dataclass
class ConsistencyConfig:
    n_runs:           int   = 5      # pipeline repetitions
    majority_thresh:  float = 0.60   # fraction of runs needed for majority verdict
    high_stability:   float = 0.80   # variance threshold for STABLE label
    low_stability:    float = 0.50   # variance threshold for UNSTABLE label


CONSISTENCY_CFG = ConsistencyConfig()


# ─── LLM / Embedding ─────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    claim_extractor_model: str = "gpt-4o-mini"
    agent_model:           str = "gpt-4o-mini"
    judge_model:           str = "gpt-4o-mini"
    correction_model:      str = "gpt-4o-mini"
    embedding_model:       str = "text-embedding-3-small"
    embedding_dim:         int = 1536
    max_tokens_agent:      int = 512
    max_tokens_judge:      int = 1024
    temperature_agent:     float = 0.2   # low for determinism
    temperature_judge:     float = 0.0   # fully deterministic


MODEL_CFG = ModelConfig()


# ─── Storage ──────────────────────────────────────────────────────────────────

@dataclass
class StorageConfig:
    chroma_persist_dir:  str = "./storage/chroma"
    neo4j_uri:           str = "bolt://localhost:7687"
    neo4j_user:          str = "neo4j"
    neo4j_password:      str = "veritas_omega"
    audit_log_dir:       str = "./storage/audit_logs"
    sqlite_db_path:      str = "./storage/veritas.db"


STORAGE_CFG = StorageConfig()


# ─── Source Domain Authority Table ───────────────────────────────────────────
# Pre-assigned domain authority scores in [0, 1].
# Extend as needed; keys are FQDN patterns.

DOMAIN_AUTHORITY: Dict[str, float] = {
    "wikipedia.org":      0.78,
    "pubmed.ncbi.nlm.nih.gov": 0.92,
    "arxiv.org":          0.80,
    "nature.com":         0.95,
    "science.org":        0.95,
    "thelancet.com":      0.93,
    "nejm.org":           0.95,
    "reuters.com":        0.82,
    "apnews.com":         0.83,
    "bbc.com":            0.80,
    "nytimes.com":        0.78,
    "scholar.google.com": 0.85,
    "default":            0.40,
}
