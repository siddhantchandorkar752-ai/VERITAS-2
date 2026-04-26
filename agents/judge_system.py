"""
VERITAS-Ω — Judge System

Aggregation Logic
─────────────────
Given agent outputs {a₁, a₂, a₃} and evidence graph G:

Step 1 — Evidence-weighted agent scores
  pro_score  = Σ_{a: stance=supports}    (a.confidence × trust_score(a.refs))
  con_score  = Σ_{a: stance=contradicts} (a.confidence × trust_score(a.refs))

  where trust_score(refs) = mean trust_score of cited documents.

Step 2 — Graph structural scores
  sup_graph  = EvidenceGraphBuilder.supporting_score(G)   ∈ [0,1]
  con_graph  = EvidenceGraphBuilder.contradiction_score(G) ∈ [0,1]

Step 3 — Composite confidence
  raw_confidence = α · (pro_score − con_score) / (pro_score + con_score + ε)
                 + (1−α) · (sup_graph − con_graph)
  where α = 0.6 (agent weight), ε = 1e-9, result ∈ (−1, +1)
  confidence = (raw_confidence + 1) / 2                  ∈ (0, 1)

Step 4 — Uncertainty
  uncertainty = adversarial_agent.confidence × (1 − aggregated_trust_score)
  clamped to [0, 1−confidence]

Step 5 — Conflict resolution
  If pro_score > 0 AND con_score > 0 AND |pro_score − con_score| < δ (0.15):
      → verdict = UNCERTAIN (insufficient dominance)

Step 6 — Threshold gating (domain-specific)
  TRUE           : confidence ≥ thresholds.true_min
  FALSE          : confidence ≤ thresholds.false_max
  PARTIALLY_TRUE : false_max < confidence < true_min
                   AND uncertainty ≤ thresholds.partial_max_uncertainty
  UNCERTAIN      : otherwise (including domain threshold failures)

Step 7 — Minimum evidence guard
  If evidence_count < thresholds.min_evidence_count → UNCERTAIN
  If aggregated_trust_score < thresholds.trust_score_floor → UNCERTAIN
"""
from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

import openai

from config.settings import DOMAIN_THRESHOLDS, MODEL_CFG
from config.settings import DomainMode as CfgDomainMode
from core.schemas import (
    AgentOutput,
    Claim,
    DomainMode,
    EvidenceGraph,
    JudgeOutput,
    RetrievedDocument,
    Verdict,
)
from graph.evidence_graph import EvidenceGraphBuilder
from scoring.trust_scorer import TrustScorer

logger = logging.getLogger(__name__)

_ALPHA = 0.6          # weight of agent scores vs. graph scores
_CONFLICT_DELTA = 0.15  # dominance gap below which conflict is declared
_EPSILON = 1e-9


class JudgeSystem:
    """
    Aggregates agent outputs and evidence graph into a final verdict.
    """

    def __init__(self, client: Optional[openai.OpenAI] = None):
        self._client = client or openai.OpenAI()
        self._trust_scorer = TrustScorer()
        self._graph_builder = EvidenceGraphBuilder()

    def judge(
        self,
        claim: Claim,
        agent_outputs: List[AgentOutput],
        documents: List[RetrievedDocument],
        evidence_graph: EvidenceGraph,
        domain_mode: DomainMode = DomainMode.GENERAL,
    ) -> JudgeOutput:
        t0 = time.perf_counter()

        # Map domain enum
        cfg_domain = CfgDomainMode(domain_mode.value)
        thresholds = DOMAIN_THRESHOLDS[cfg_domain]

        doc_map: Dict[str, RetrievedDocument] = {d.doc_id: d for d in documents}

        # ── Step 1: Agent scores ──────────────────────────────────────────
        pro_score, con_score, adv_confidence = self._compute_agent_scores(
            agent_outputs, doc_map
        )

        # ── Step 2: Graph scores ──────────────────────────────────────────
        sup_graph = self._graph_builder.supporting_score(evidence_graph)
        con_graph = self._graph_builder.contradiction_score(evidence_graph)

        # ── Step 3: Composite confidence (FIX 2) ─────────────────────────────────
        agent_diff = pro_score - con_score
        graph_diff = sup_graph - con_graph
        
        # Base confidence calculation without unstable division
        base_confidence = (agent_diff + graph_diff) / 2.0  # Range [-1, 1]
        
        # ── Step 4: Aggregated trust & Adversarial Penalty (FIX 5 & 6) ────────
        agg_trust = self._trust_scorer.aggregate_trust(documents)
        
        # Adversarial penalty directly reduces trust and confidence
        penalty = adv_confidence * (1.0 - agg_trust)
        raw_confidence = base_confidence - penalty
        
        confidence = (raw_confidence + 1.0) / 2.0  # Shift to [0, 1]
        confidence = round(min(max(confidence, 0.0), 1.0), 4)

        # ── Step 5: Uncertainty (FIX 6) ───────────────────────────────────────────
        # Quantify Epistemic vs Aleatoric directly
        epistemic_uncertainty = penalty  # Driven by adversarial gaps
        aleatoric_uncertainty = (1.0 - abs(agent_diff)) * 0.2  # Driven by systemic disagreement
        uncertainty = round(min(epistemic_uncertainty + aleatoric_uncertainty, 1.0), 4)

        # ── Step 5b: Conflict resolution ──────────────────────────────────
        conflict = (
            pro_score > 0
            and con_score > 0
            and abs(pro_score - con_score) < _CONFLICT_DELTA
        )

        # ── Step 6 & 7: Verdict ───────────────────────────────────────────
        evidence_count = len(documents)
        verdict = self._determine_verdict(
            confidence=confidence,
            uncertainty=uncertainty,
            evidence_count=evidence_count,
            agg_trust=agg_trust,
            conflict=conflict,
            thresholds=thresholds,
        )

        # ── Collect doc references ────────────────────────────────────────
        supporting_ids = [
            ref.doc_id
            for a in agent_outputs if a.stance == "supports"
            for ref in a.evidence_references
        ]
        contradicting_ids = [
            ref.doc_id
            for a in agent_outputs if a.stance in ("contradicts", "flags_weakness")
            for ref in a.evidence_references
        ]

        # ── Reasoning summary (LLM-generated, evidence-only) ─────────────
        reasoning_summary = self._generate_reasoning_summary(
            claim, agent_outputs, verdict, confidence, domain_mode
        )

        result = JudgeOutput(
            claim_id=claim.claim_id,
            verdict=verdict,
            confidence_score=confidence,
            uncertainty_score=uncertainty,
            evidence_count=evidence_count,
            aggregated_trust_score=agg_trust,
            reasoning_summary=reasoning_summary,
            supporting_doc_ids=list(set(supporting_ids)),
            contradicting_doc_ids=list(set(contradicting_ids)),
            domain_mode=domain_mode,
        )

        logger.info(
            "Judge: claim=%s verdict=%s confidence=%.3f uncertainty=%.3f in %.2fs",
            claim.claim_id,
            verdict.value,
            confidence,
            uncertainty,
            time.perf_counter() - t0,
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_agent_scores(
        self,
        agent_outputs: List[AgentOutput],
        doc_map: Dict[str, RetrievedDocument],
    ):
        """
        Returns (pro_score, con_score, adv_confidence).
        Each score = Σ agent.confidence × mean_trust(cited_docs).
        """
        pro_score = 0.0
        con_score = 0.0
        adv_confidence = 0.5   # default if adversarial agent missing

        for ao in agent_outputs:
            ref_trusts = [
                doc_map[r.doc_id].trust_score
                for r in ao.evidence_references
                if r.doc_id in doc_map
            ]
            mean_trust = sum(ref_trusts) / len(ref_trusts) if ref_trusts else 0.5
            weighted = ao.confidence * mean_trust

            if ao.stance == "supports":
                pro_score += weighted
            elif ao.stance in ("contradicts",):
                con_score += weighted
            elif ao.stance == "flags_weakness":
                adv_confidence = ao.confidence   # adversarial confidence = uncertainty amplifier

        return pro_score, con_score, adv_confidence

    @staticmethod
    def _determine_verdict(
        confidence: float,
        uncertainty: float,
        evidence_count: int,
        agg_trust: float,
        conflict: bool,
        thresholds,
    ) -> Verdict:
        # Minimum evidence guard
        if evidence_count < thresholds.min_evidence_count:
            logger.debug("Verdict=UNCERTAIN: insufficient evidence (%d)", evidence_count)
            return Verdict.UNCERTAIN

        # Trust floor guard
        if agg_trust < thresholds.trust_score_floor:
            logger.debug("Verdict=UNCERTAIN: trust too low (%.3f)", agg_trust)
            return Verdict.UNCERTAIN

        # Conflict check
        if conflict:
            logger.debug("Verdict=UNCERTAIN: agent conflict detected")
            return Verdict.UNCERTAIN

        if confidence >= thresholds.true_min:
            return Verdict.TRUE
        if confidence <= thresholds.false_max:
            return Verdict.FALSE
        if uncertainty <= thresholds.partial_max_uncertainty:
            return Verdict.PARTIALLY_TRUE
        return Verdict.UNCERTAIN

    def _generate_reasoning_summary(
        self,
        claim: Claim,
        agent_outputs: List[AgentOutput],
        verdict: Verdict,
        confidence: float,
        domain_mode: DomainMode,
    ) -> str:
        """
        Structured reasoning summary synthesised by the judge LLM,
        constrained to cited agent reasoning only.
        """
        agent_block = "\n".join(
            f"[{a.agent_role.upper()}] confidence={a.confidence:.2f}\n"
            f"  stance: {a.stance}\n"
            f"  reasoning: {a.reasoning[:400]}"
            for a in agent_outputs
        )
        prompt = f"""
You are the VERITAS-Ω Chief Judge. Your goal is to synthesize the fact-verification agent outputs into a highly accurate, rigorous final reasoning summary.

Claim: {claim.claim_text}
Domain: {domain_mode.value}
Computed verdict: {verdict.value}  (confidence={confidence:.3f})

Agent reasoning:
{agent_block}

RULES FOR YOUR SUMMARY:
1. UNCERTAINTY DECOMPOSITION: Explicitly state what uncertainty exists and WHY (Epistemic vs Aleatoric).
2. PROBABILISTIC AGGREGATION: Explain exactly why the final verdict was reached based on evidence strength and agent variance.
3. RIGOR: Write a 3-5 sentence structured reasoning summary. Reference ONLY the agent reasoning above. Do not introduce external knowledge. Be brutally precise, factual, and strictly explain the math/logic behind the decision.
"""
        try:
            response = self._client.chat.completions.create(
                model=MODEL_CFG.judge_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=MODEL_CFG.temperature_judge,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("Judge reasoning summary failed: %s", exc)
            return f"Verdict {verdict.value} at confidence {confidence:.3f}."
