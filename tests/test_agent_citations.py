from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from agents.agent_system import AgentOrchestrator, ProAgent
from core.mock_openai import MockOpenAIClient
from core.schemas import AgentOutput, Claim, EvidenceReference, RetrievedDocument


def document() -> RetrievedDocument:
    return RetrievedDocument(
        doc_id="doc-1",
        url="https://example.org/canonical",
        title="Canonical source",
        snippet="Canonical retrieved excerpt.",
        source_domain="example.org",
    )


class CitationBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ProAgent(MockOpenAIClient())

    def response(self, doc_id: str = "doc-1", stance: str = "supports") -> str:
        return json.dumps(
            {
                "stance": stance,
                "key_points": ["A structured point."],
                "evidence_references": [
                    {
                        "doc_id": doc_id,
                        "url": "https://attacker.invalid/substitution",
                        "excerpt": "Model-supplied substitution",
                    }
                ],
                "confidence": 0.7,
                "reasoning": "Reasoning tied to the cited document.",
            }
        )

    def test_reference_url_and_excerpt_are_canonicalized(self) -> None:
        output = self.agent._parse(self.response(), "claim-1", [document()])
        reference = output.evidence_references[0]
        self.assertEqual("https://example.org/canonical", reference.url)
        self.assertEqual("Canonical retrieved excerpt.", reference.excerpt)

    def test_duplicate_document_references_are_collapsed(self) -> None:
        payload = json.loads(self.response())
        payload["evidence_references"] *= 2
        output = self.agent._parse(json.dumps(payload), "claim-1", [document()])
        self.assertEqual(1, len(output.evidence_references))

    def test_unknown_document_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not cite"):
            self.agent._parse(self.response(doc_id="unknown"), "claim-1", [document()])

    def test_role_inconsistent_stance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 'supports'"):
            self.agent._parse(
                self.response(stance="contradicts"),
                "claim-1",
                [document()],
            )

    def test_incomplete_agent_panel_is_rejected(self) -> None:
        orchestrator = AgentOrchestrator(MockOpenAIClient())
        reference = EvidenceReference(
            doc_id="doc-1",
            url="https://example.org/canonical",
            excerpt="Canonical retrieved excerpt.",
        )
        orchestrator._pro.run = Mock(
            return_value=AgentOutput(
                agent_role="pro",
                claim_id="claim-1",
                stance="supports",
                key_points=["Pro point"],
                evidence_references=[reference],
                confidence=0.5,
                reasoning="Pro reasoning",
            )
        )
        orchestrator._con.run = Mock(
            return_value=AgentOutput(
                agent_role="con",
                claim_id="claim-1",
                stance="contradicts",
                key_points=["Con point"],
                evidence_references=[reference],
                confidence=0.5,
                reasoning="Con reasoning",
            )
        )
        orchestrator._adv.run = Mock(side_effect=RuntimeError("agent unavailable"))
        with self.assertRaisesRegex(RuntimeError, "Incomplete agent panel"):
            orchestrator.orchestrate(
                Claim(claim_text="A sufficiently long claim."),
                [document()],
            )
