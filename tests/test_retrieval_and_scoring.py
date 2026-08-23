from __future__ import annotations

import unittest
from unittest.mock import Mock

from core.mock_openai import MockOpenAIClient
from core.schemas import Claim, RetrievedDocument
from retrieval.hybrid_retriever import ArxivAdapter, HybridRetriever, WikipediaAdapter
from scoring.trust_scorer import TrustScorer


class WikipediaTransportTests(unittest.TestCase):
    def test_wikipedia_request_has_user_agent_and_bounds(self) -> None:
        response = Mock()
        response.json.return_value = {
            "query": {"search": [{"pageid": 42, "title": "Example", "snippet": "<b>Safe</b> text"}]}
        }
        session = Mock()
        session.get.return_value = response

        documents = WikipediaAdapter(session=session).fetch("example", top_k=2)

        response.raise_for_status.assert_called_once_with()
        _, kwargs = session.get.call_args
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertEqual((3.05, 8), kwargs["timeout"])
        self.assertEqual(2, kwargs["params"]["srlimit"])
        self.assertEqual("Safe text", documents[0].snippet)


class ArxivTransportTests(unittest.TestCase):
    def test_external_entity_payload_is_rejected(self) -> None:
        response = Mock()
        response.text = """<?xml version="1.0"?>
        <!DOCTYPE feed [<!ENTITY external SYSTEM "file:///forbidden">]>
        <feed xmlns="http://www.w3.org/2005/Atom"><title>&external;</title></feed>
        """
        session = Mock()
        session.get.return_value = response

        documents = ArxivAdapter(session=session).fetch("example", top_k=1)

        self.assertEqual([], documents)


class TrustScoringBoundaryTests(unittest.TestCase):
    def test_domain_suffix_spoof_does_not_receive_authority(self) -> None:
        self.assertEqual(0.78, TrustScorer._domain_authority("en.wikipedia.org"))
        self.assertEqual(0.40, TrustScorer._domain_authority("evilwikipedia.org"))

    def test_citation_normalization_is_bounded(self) -> None:
        self.assertEqual(1.0, TrustScorer._citation_count_norm(1_000_000))


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_rank_is_one_based(self) -> None:
        retriever = HybridRetriever(openai_client=MockOpenAIClient(), demo_mode=True)
        retriever._demo_documents = lambda _claim: [
            RetrievedDocument(
                doc_id="doc-1",
                url="https://demo.invalid/doc-1",
                title="Synthetic",
                snippet="Synthetic fixture",
                source_domain="demo.invalid",
            )
        ]

        result = retriever.retrieve(Claim(claim_text="A sufficiently long claim."))

        self.assertAlmostEqual(2 / 61, result.documents[0].fusion_score)
