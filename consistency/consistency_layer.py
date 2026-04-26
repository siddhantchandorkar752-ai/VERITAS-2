"""
VERITAS-Ω — Consistency Layer

Purpose: Run the full pipeline N times with stochastic variation
to measure output stability.

Stability Score Formulation
───────────────────────────
Given N runs producing verdicts {v₁,...,vₙ} and confidences {c₁,...,cₙ}:

  majority_verdict = argmax_v count(vᵢ == v)
  majority_fraction = count(vᵢ == majority_verdict) / N
  mean_confidence  = (1/N) Σ cᵢ
  confidence_variance = (1/(N-1)) Σ (cᵢ − mean_confidence)²

  stability_score = majority_fraction × (1 − normalised_variance)
  where normalised_variance = min(confidence_variance / 0.25, 1.0)
        (0.25 = variance of uniform distribution on [0,1])

  stability_label:
    stability_score ≥ high_stability (0.80) → STABLE
    stability_score ≥ low_stability  (0.50) → MODERATE
    otherwise                               → UNSTABLE
"""
from __future__ import annotations

import logging
import statistics
from collections import Counter
from typing import Callable, List, Optional, Tuple

from config.settings import CONSISTENCY_CFG
from core.schemas import (
    Claim,
    ConsistencyResult,
    DomainMode,
    JudgeOutput,
    StabilityLabel,
    Verdict,
)

logger = logging.getLogger(__name__)

# Maximum possible variance for uniform dist on [0,1]
_MAX_VARIANCE = 0.25


class ConsistencyLayer:
    """
    Runs the pipeline N times and aggregates results.

    The pipeline_fn is a callable:
        pipeline_fn(claim: Claim, domain_mode: DomainMode, run_seed: int) -> JudgeOutput

    run_seed introduces stochastic variation: the caller should use it
    to vary LLM temperature or random retrieval order between runs.
    """

    def __init__(self, n_runs: Optional[int] = None):
        self._cfg = CONSISTENCY_CFG
        self._n   = n_runs or self._cfg.n_runs

    def evaluate(
        self,
        claim: Claim,
        domain_mode: DomainMode,
        pipeline_fn: Callable[[Claim, DomainMode, int], JudgeOutput],
    ) -> ConsistencyResult:
        """
        Execute pipeline_fn N times, collect verdicts and confidences,
        return a ConsistencyResult.

        Pseudocode:
        ───────────
        function evaluate(claim, domain_mode, pipeline_fn):
            verdicts    = []
            confidences = []
            for seed in range(N):
                output = pipeline_fn(claim, domain_mode, seed)
                verdicts.append(output.verdict)
                confidences.append(output.confidence_score)
            majority_verdict = mode(verdicts)
            return aggregate(verdicts, confidences)
        """
        verdicts:    List[Verdict] = []
        confidences: List[float]   = []

        for seed in range(self._n):
            try:
                out = pipeline_fn(claim, domain_mode, seed)
                verdicts.append(out.verdict)
                confidences.append(out.confidence_score)
                logger.debug(
                    "Consistency run %d/%d: verdict=%s conf=%.3f",
                    seed + 1, self._n, out.verdict.value, out.confidence_score,
                )
            except Exception as exc:
                logger.warning("Consistency run %d failed: %s", seed + 1, exc)

        if not verdicts:
            raise RuntimeError(
                f"All {self._n} consistency runs failed for claim {claim.claim_id}"
            )

        return self._aggregate(claim.claim_id, verdicts, confidences)

    # ── Private ───────────────────────────────────────────────────────────────

    def _aggregate(
        self,
        claim_id: str,
        verdicts: List[Verdict],
        confidences: List[float],
    ) -> ConsistencyResult:
        counter = Counter(verdicts)
        majority_verdict, majority_count = counter.most_common(1)[0]
        majority_fraction = majority_count / len(verdicts)

        mean_conf = statistics.mean(confidences)
        conf_var  = statistics.variance(confidences) if len(confidences) > 1 else 0.0
        norm_var  = min(conf_var / _MAX_VARIANCE, 1.0)

        stability_score = majority_fraction * (1.0 - norm_var)
        stability_score = round(min(max(stability_score, 0.0), 1.0), 4)

        if stability_score >= self._cfg.high_stability:
            label = StabilityLabel.STABLE
        elif stability_score >= self._cfg.low_stability:
            label = StabilityLabel.MODERATE
        else:
            label = StabilityLabel.UNSTABLE

        logger.info(
            "Consistency: claim=%s majority=%s stability=%.3f [%s]",
            claim_id,
            majority_verdict.value,
            stability_score,
            label.value,
        )

        return ConsistencyResult(
            claim_id=claim_id,
            run_verdicts=verdicts,
            run_confidences=confidences,
            majority_verdict=majority_verdict,
            mean_confidence=round(mean_conf, 4),
            confidence_variance=round(conf_var, 6),
            stability_score=stability_score,
            stability_label=label,
            n_runs=len(verdicts),
        )
