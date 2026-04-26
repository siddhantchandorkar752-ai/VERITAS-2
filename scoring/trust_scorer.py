"""
VERITAS-Ω — Trust Scoring Module

Formal Definition
─────────────────
TrustScore(source) = w_da · DA(source)
                   + w_cc · CC_norm(source)
                   + w_rec · Rec(source)
                   + w_csa · CSA(source)

where:
  DA(source)    = domain_authority ∈ [0, 1]  (lookup table, config/settings.py)

  CC_norm(s)    = log(1 + citation_count) / log(1 + MAX_CITATIONS)
                  (log-normalised citation count; MAX_CITATIONS = 10,000)

  Rec(s)        = exp(−λ · age_days)
                  where λ = ln(2) / HALF_LIFE_DAYS
                  (exponential decay; half-life = 365 days by default)

  CSA(s)        = fraction of other sources in retrieval set that agree with s
                  (measured as sign-agreement on claim stance, ∈ [0, 1])

Weights (w_da, w_cc, w_rec, w_csa) are defined in config/settings.py
and must sum to 1.0.

All four sub-scores are bounded to [0, 1] before combination,
producing a final TrustScore ∈ [0, 1].
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from config.settings import DOMAIN_AUTHORITY, RECENCY_HALF_LIFE_DAYS, TRUST_WEIGHTS
from core.schemas import RetrievedDocument

logger = logging.getLogger(__name__)

# Maximum citation count used in log-normalisation
_MAX_CITATIONS: int = 10_000
# Decay constant: λ = ln(2) / half_life
_LAMBDA: float = math.log(2) / RECENCY_HALF_LIFE_DAYS


# ══════════════════════════════════════════════════════════════════════════════
# TRUST SCORER
# ══════════════════════════════════════════════════════════════════════════════

class TrustScorer:
    """
    Computes and attaches a TrustScore to each RetrievedDocument in-place.

    Pseudocode:
    ───────────
    function score_documents(docs):
        for doc in docs:
            da   = domain_authority(doc.source_domain)
            cc   = log_normalise(doc.citation_count)
            rec  = recency_decay(doc.published_date)
            csa  = cross_source_agreement(doc, docs)
            doc.trust_score = w_da*da + w_cc*cc + w_rec*rec + w_csa*csa
        return docs
    """

    # ── public ───────────────────────────────────────────────────────────────

    def score_documents(
        self,
        documents: List[RetrievedDocument],
        stances: Optional[Dict[str, str]] = None,
    ) -> List[RetrievedDocument]:
        """
        Score all documents. `stances` maps doc_id → "supports"|"contradicts"|"neutral".
        If stances are not yet known (pre-agent phase), CSA defaults to 0.5.
        """
        for doc in documents:
            da  = self._domain_authority(doc.source_domain)
            cc  = self._citation_count_norm(doc.citation_count)
            rec = self._recency(doc.published_date)
            csa = self._cross_source_agreement(doc, documents, stances)

            doc.trust_score = (
                TRUST_WEIGHTS.w_da  * da
                + TRUST_WEIGHTS.w_cc  * cc
                + TRUST_WEIGHTS.w_rec * rec
                + TRUST_WEIGHTS.w_csa * csa
            )
            doc.trust_score = round(min(max(doc.trust_score, 0.0), 1.0), 4)

        return documents

    def aggregate_trust(self, documents: List[RetrievedDocument]) -> float:
        """
        Compute an aggregated trust score for a set of documents.
        Uses weighted mean: docs with higher fusion_score get more weight.

        AggregatedTrust = Σ(fusion_score_i · trust_score_i) / Σ(fusion_score_i)
        Falls back to simple mean when all fusion_scores are zero.
        """
        if not documents:
            return 0.0
        weights = [max(d.fusion_score, 1e-9) for d in documents]
        total_w = sum(weights)
        return round(
            sum(w * d.trust_score for w, d in zip(weights, documents)) / total_w,
            4,
        )

    # ── sub-score functions ──────────────────────────────────────────────────

    @staticmethod
    def _domain_authority(domain: str) -> float:
        """
        DA(source) — lookup in DOMAIN_AUTHORITY table.
        Strips to second-level domain before matching.
        """
        fqdn = domain.lower().lstrip("www.")
        # try exact match first, then suffix match
        if fqdn in DOMAIN_AUTHORITY:
            return DOMAIN_AUTHORITY[fqdn]
        for key, val in DOMAIN_AUTHORITY.items():
            if key != "default" and fqdn.endswith(key):
                return val
        return DOMAIN_AUTHORITY["default"]

    @staticmethod
    def _citation_count_norm(count: int) -> float:
        """
        CC_norm(s) = log(1 + count) / log(1 + MAX_CITATIONS)
        Result ∈ [0, 1].
        """
        return math.log1p(max(count, 0)) / math.log1p(_MAX_CITATIONS)

    @staticmethod
    def _recency(published_date: Optional[str]) -> float:
        """
        Rec(s) = exp(−λ · age_days)
        age_days = days since published_date; 0 if date unknown.
        If date is unknown, returns 0.5 (neutral / no penalty).
        """
        if not published_date:
            return 0.5
        try:
            pub = datetime.fromisoformat(published_date).replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            age_days = max((now - pub).days, 0)
            return math.exp(-_LAMBDA * age_days)
        except ValueError:
            return 0.5

    @staticmethod
    def _cross_source_agreement(
        doc: RetrievedDocument,
        all_docs: List[RetrievedDocument],
        stances: Optional[Dict[str, str]],
    ) -> float:
        """
        CSA(s) = (# of other sources with the same stance as s) / (# other sources)
        If stances are unknown, returns 0.5 (uninformative prior).
        Stance agreement: both "supports" or both "contradicts".
        """
        if not stances or doc.doc_id not in stances:
            return 0.5
        this_stance = stances[doc.doc_id]
        others = [d for d in all_docs if d.doc_id != doc.doc_id and d.doc_id in stances]
        if not others:
            return 0.5
        agreeing = sum(1 for d in others if stances[d.doc_id] == this_stance)
        return agreeing / len(others)
