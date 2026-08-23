from __future__ import annotations

import unittest

from core.mock_openai import MockOpenAIClient
from core.schemas import (
    AgentOutput,
    Claim,
    DomainMode,
    EdgeType,
    EvidenceReference,
    JudgeOutput,
    RetrievedDocument,
    Verdict,
)
from correction.correction_engine import CorrectionEngine
from graph.evidence_graph import EvidenceGraphBuilder


def document() -> RetrievedDocument:
    return RetrievedDocument(
        doc_id="doc-1",
        url="https://example.org/evidence",
        title="Example evidence",
        snippet="A retrieved evidence excerpt.",
        source_domain="example.org",
        trust_score=0.8,
    )


def agent_output(role: str, stance: str) -> AgentOutput:
    return AgentOutput(
        agent_role=role,
        claim_id="claim-1",
        stance=stance,
        key_points=["A structured point."],
        evidence_references=[
            EvidenceReference(
                doc_id="doc-1",
                url="https://example.org/evidence",
                excerpt="A retrieved evidence excerpt.",
            )
        ],
        confidence=0.6,
        reasoning="A bounded reasoning summary.",
    )


class EvidenceGraphBoundaryTests(unittest.TestCase):
    def test_weakness_signal_is_neutral_not_counter_evidence(self) -> None:
        claim = Claim(claim_id="claim-1", claim_text="A sufficiently long claim.")
        graph = EvidenceGraphBuilder().build(
            claim,
            [agent_output("adversarial", "flags_weakness")],
            [document()],
        )

        self.assertEqual(EdgeType.NEUTRAL, graph.edges[0].edge_type)
        self.assertEqual(0.0, EvidenceGraphBuilder.supporting_score(graph))
        self.assertEqual(0.0, EvidenceGraphBuilder.contradiction_score(graph))


class CorrectionLabelTests(unittest.TestCase):
    def test_true_label_is_not_described_as_verification(self) -> None:
        claim = Claim(claim_id="claim-1", claim_text="A sufficiently long claim.")
        judge = JudgeOutput(
            claim_id=claim.claim_id,
            verdict=Verdict.TRUE,
            confidence_score=0.8,
            uncertainty_score=0.1,
            evidence_count=2,
            aggregated_trust_score=0.8,
            reasoning_summary="Experimental aggregation only.",
            supporting_doc_ids=["doc-1"],
            domain_mode=DomainMode.GENERAL,
        )

        result = CorrectionEngine(MockOpenAIClient()).correct(claim, judge, [document()])

        self.assertIn("not factual verification", result.correction_note)


if __name__ == "__main__":
    unittest.main()
