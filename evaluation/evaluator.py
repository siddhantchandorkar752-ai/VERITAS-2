"""
VERITAS-Ω — Evaluation Framework

Metrics
───────
1. Claim Verification F1:
   F1 = 2·Precision·Recall / (Precision + Recall)
   where Precision = TP/(TP+FP), Recall = TP/(TP+FN)
   Labels: TRUE=1, FALSE=0, PARTIALLY_TRUE=0.5, UNCERTAIN=ignore

2. Evidence Grounding Rate:
   EGR = (# claims where every key_point has ≥1 evidence_reference)
         / total_claims

3. False Positive Rate:
   FPR = FP / (FP + TN)
   (claims predicted TRUE that are actually FALSE)

4. Cross-Run Consistency Score:
   Mean stability_score across all tested claims.
   Higher = more reproducible.

Benchmark Datasets:
  - LIAR (Wang 2017)      — 12,836 labelled political claims
  - FEVER (Thorne 2018)   — 185,445 Wikipedia-based factual claims
  - VitaminC (Schuster 2021) — contrastive fact verification

Testing Methodology:
  1. Sample N claims from each dataset.
  2. Map dataset labels → {TRUE, FALSE, PARTIALLY_TRUE, UNCERTAIN}.
  3. Run VERITAS pipeline.
  4. Compare system verdict vs. ground truth.
  5. Compute F1, FPR, EGR, consistency_score.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.schemas import ConsistencyResult, JudgeOutput, Verdict

logger = logging.getLogger(__name__)


# ── Label mapping ─────────────────────────────────────────────────────────────

LIAR_LABEL_MAP: Dict[str, Optional[Verdict]] = {
    "true":          Verdict.TRUE,
    "mostly-true":   Verdict.PARTIALLY_TRUE,
    "half-true":     Verdict.PARTIALLY_TRUE,
    "barely-true":   Verdict.FALSE,
    "false":         Verdict.FALSE,
    "pants-fire":    Verdict.FALSE,
}

FEVER_LABEL_MAP: Dict[str, Optional[Verdict]] = {
    "SUPPORTS":        Verdict.TRUE,
    "REFUTES":         Verdict.FALSE,
    "NOT ENOUGH INFO": Verdict.UNCERTAIN,
}


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvaluationReport:
    total_claims:       int = 0
    tp: int = 0   # TRUE predicted AND true
    fp: int = 0   # TRUE predicted BUT false/partial
    fn: int = 0   # TRUE in ground truth BUT not predicted TRUE
    tn: int = 0   # FALSE predicted AND false in ground truth
    skipped:            int = 0   # UNCERTAIN predictions (excluded from F1)
    evidence_grounded:  int = 0   # claims with all key_points evidenced
    consistency_scores: List[float] = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.tp / max(self.tp + self.fp, 1)

    @property
    def recall(self) -> float:
        return self.tp / max(self.tp + self.fn, 1)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / max(p + r, 1e-9)

    @property
    def false_positive_rate(self) -> float:
        return self.fp / max(self.fp + self.tn, 1)

    @property
    def evidence_grounding_rate(self) -> float:
        decidable = self.total_claims - self.skipped
        return self.evidence_grounded / max(decidable, 1)

    @property
    def mean_consistency_score(self) -> float:
        return (
            sum(self.consistency_scores) / len(self.consistency_scores)
            if self.consistency_scores else 0.0
        )

    def to_dict(self) -> dict:
        return {
            "total_claims":           self.total_claims,
            "precision":              round(self.precision, 4),
            "recall":                 round(self.recall, 4),
            "f1":                     round(self.f1, 4),
            "false_positive_rate":    round(self.false_positive_rate, 4),
            "evidence_grounding_rate": round(self.evidence_grounding_rate, 4),
            "mean_consistency_score": round(self.mean_consistency_score, 4),
            "skipped_uncertain":      self.skipped,
        }


class Evaluator:
    """
    Evaluates VERITAS-Ω outputs against ground-truth labels.
    """

    def evaluate_batch(
        self,
        predictions: List[JudgeOutput],
        ground_truths: List[Verdict],
        consistency_results: Optional[List[ConsistencyResult]] = None,
        agent_outputs_list: Optional[list] = None,
    ) -> EvaluationReport:
        """
        Args:
            predictions:       JudgeOutput per claim.
            ground_truths:     Ground-truth Verdict per claim (same order).
            consistency_results: Optional consistency results per claim.
            agent_outputs_list:  Optional list of agent output lists per claim.
        """
        assert len(predictions) == len(ground_truths), "Mismatched lengths."
        report = EvaluationReport(total_claims=len(predictions))

        for i, (pred, gt) in enumerate(zip(predictions, ground_truths)):
            if pred.verdict == Verdict.UNCERTAIN:
                report.skipped += 1
                continue

            pred_positive = pred.verdict in (Verdict.TRUE, Verdict.PARTIALLY_TRUE)
            gt_positive   = gt         in (Verdict.TRUE, Verdict.PARTIALLY_TRUE)

            if pred_positive and gt_positive:
                report.tp += 1
            elif pred_positive and not gt_positive:
                report.fp += 1
            elif not pred_positive and gt_positive:
                report.fn += 1
            else:
                report.tn += 1

            # Evidence grounding
            if agent_outputs_list:
                agents = agent_outputs_list[i]
                all_grounded = all(
                    len(ao.evidence_references) > 0
                    for ao in agents
                )
                if all_grounded:
                    report.evidence_grounded += 1

            # Consistency
            if consistency_results and i < len(consistency_results):
                report.consistency_scores.append(consistency_results[i].stability_score)

        return report

    def save_report(self, report: EvaluationReport, path: str):
        Path(path).write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        logger.info("Evaluation report saved to %s", path)
