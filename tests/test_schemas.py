from __future__ import annotations

import unittest

from pydantic import ValidationError

from core.schemas import AgentOutput, EvidenceReference


class SchemaBoundaryTests(unittest.TestCase):
    def test_agent_stance_is_closed_set(self) -> None:
        with self.assertRaises(ValidationError):
            AgentOutput(
                agent_role="pro",
                claim_id="claim-1",
                stance="neutral",
                key_points=["Point"],
                evidence_references=[
                    EvidenceReference(
                        doc_id="doc-1",
                        url="https://example.org",
                        excerpt="Excerpt",
                    )
                ],
                confidence=0.5,
                reasoning="Reasoning",
            )

    def test_agent_requires_key_points(self) -> None:
        with self.assertRaises(ValidationError):
            AgentOutput(
                agent_role="pro",
                claim_id="claim-1",
                stance="supports",
                key_points=[],
                evidence_references=[
                    EvidenceReference(
                        doc_id="doc-1",
                        url="https://example.org",
                        excerpt="Excerpt",
                    )
                ],
                confidence=0.5,
                reasoning="Reasoning",
            )
