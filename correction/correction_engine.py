"""
VERITAS-Ω — Correction Engine

Generates a corrected version of a claim using ONLY validated evidence.

Algorithm
─────────
function generate_correction(claim, judge_output, documents):
    if judge_output.verdict == TRUE:
        return original claim unchanged (no correction needed)

    supporting_docs = [d for d in documents if d.doc_id in judge_output.supporting_doc_ids]
    if not supporting_docs:
        return claim text redacted to "Claim could not be verified."

    prompt = build_correction_prompt(claim, supporting_docs, judge_output)
    corrected_text = call_llm(prompt)

    // Validate: corrected_text must not introduce new assertions
    removed_parts = detect_removed_assertions(claim.claim_text, corrected_text)

    return CorrectedClaim(
        original_claim_id = claim.claim_id,
        original_text     = claim.claim_text,
        corrected_text    = corrected_text,
        removed_assertions= removed_parts,
        evidence_basis    = [d.doc_id for d in supporting_docs],
        correction_note   = "Corrected using only validated supporting evidence."
    )

Intent preservation rule:
    The corrected claim must retain the SUBJECT and TOPIC of the original.
    Only unsupported predicates are removed or qualified.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import openai

from config.settings import MODEL_CFG
from core.schemas import (
    Claim,
    CorrectedClaim,
    JudgeOutput,
    RetrievedDocument,
    Verdict,
)

logger = logging.getLogger(__name__)

_CORRECTION_SYSTEM = """
You are a fact-correction engine. Your task is to produce a corrected version
of a claim using ONLY the supporting evidence provided.

Rules:
1. Do NOT introduce facts not present in the supporting evidence.
2. Preserve the original subject and topic.
3. Remove or qualify any part of the claim that is not supported.
4. If nothing can be supported, return the literal string: "[UNVERIFIABLE]"
5. The corrected claim must be a grammatically correct declarative sentence.
6. Return ONLY the corrected claim text. No explanation, no JSON.
"""

_CORRECTION_USER = """
Original claim: {claim_text}

Verdict: {verdict}
Confidence: {confidence:.3f}

Supporting evidence:
{evidence_block}

Write the corrected claim:
"""


class CorrectionEngine:
    """
    Produces a corrected claim grounded in validated evidence.
    """

    def __init__(self, client: Optional[openai.OpenAI] = None):
        self._client = client or openai.OpenAI()

    def correct(
        self,
        claim: Claim,
        judge_output: JudgeOutput,
        documents: List[RetrievedDocument],
    ) -> CorrectedClaim:
        # TRUE claims need no correction
        if judge_output.verdict == Verdict.TRUE:
            return CorrectedClaim(
                original_claim_id=claim.claim_id,
                original_text=claim.claim_text,
                corrected_text=claim.claim_text,
                removed_assertions=[],
                evidence_basis=judge_output.supporting_doc_ids,
                correction_note="Claim verified as TRUE; no correction required.",
            )

        # Select supporting documents
        supporting_docs = [
            d for d in documents
            if d.doc_id in set(judge_output.supporting_doc_ids)
        ]

        # If no support at all, mark unverifiable
        if not supporting_docs:
            return CorrectedClaim(
                original_claim_id=claim.claim_id,
                original_text=claim.claim_text,
                corrected_text="[UNVERIFIABLE]",
                removed_assertions=[claim.claim_text],
                evidence_basis=[],
                correction_note="No supporting evidence found; claim is unverifiable.",
            )

        # Build evidence block
        evidence_block = "\n".join(
            f"[{i+1}] {d.title}: {d.snippet[:300]}"
            for i, d in enumerate(supporting_docs[:5])
        )

        prompt = _CORRECTION_USER.format(
            claim_text=claim.claim_text,
            verdict=judge_output.verdict.value,
            confidence=judge_output.confidence_score,
            evidence_block=evidence_block,
        )

        try:
            response = self._client.chat.completions.create(
                model=MODEL_CFG.correction_model,
                messages=[
                    {"role": "system", "content": _CORRECTION_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            corrected_text = response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("CorrectionEngine LLM call failed: %s", exc)
            corrected_text = "[CORRECTION_FAILED]"

        # Detect removed assertions (simple diff at sentence level)
        removed = self._detect_removed_assertions(
            claim.claim_text, corrected_text
        )

        return CorrectedClaim(
            original_claim_id=claim.claim_id,
            original_text=claim.claim_text,
            corrected_text=corrected_text,
            removed_assertions=removed,
            evidence_basis=[d.doc_id for d in supporting_docs],
            correction_note=(
                f"Corrected from verdict={judge_output.verdict.value} "
                f"using {len(supporting_docs)} supporting document(s)."
            ),
        )

    @staticmethod
    def _detect_removed_assertions(original: str, corrected: str) -> List[str]:
        """
        Heuristic: split both texts into clauses on ',' and ';';
        return clauses in original that are NOT present in corrected.
        This is a best-effort approximation, not semantic entailment.
        """
        import re
        def clauses(text: str):
            return [c.strip() for c in re.split(r"[,;]", text) if len(c.strip()) > 8]

        orig_clauses = set(clauses(original.lower()))
        corr_clauses = set(clauses(corrected.lower()))
        removed = orig_clauses - corr_clauses
        return sorted(removed)
