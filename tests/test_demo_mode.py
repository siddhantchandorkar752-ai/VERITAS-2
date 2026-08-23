from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from core.mock_openai import deterministic_embedding
from core.pipeline import VeritasPipeline
from core.schemas import DomainMode, EvidenceStatus, ExecutionMode
from retrieval.hybrid_retriever import ArxivAdapter, WikipediaAdapter


class DemoModeContractTests(unittest.TestCase):
    def test_demo_is_input_dependent_synthetic_and_offline(self) -> None:
        claim = "The Earth orbits the Sun."
        with (
            tempfile.TemporaryDirectory() as audit_directory,
            patch.object(
                WikipediaAdapter,
                "fetch",
                side_effect=AssertionError("demo must not call Wikipedia"),
            ),
            patch.object(
                ArxivAdapter,
                "fetch",
                side_effect=AssertionError("demo must not call arXiv"),
            ),
        ):
            result = VeritasPipeline(
                mode=ExecutionMode.DEMO,
                run_consistency=False,
                audit_log_dir=audit_directory,
            ).run(claim)

        self.assertEqual(claim, result.claims[0].claim_text)
        self.assertEqual(ExecutionMode.DEMO, result.execution_mode)
        self.assertEqual(EvidenceStatus.SYNTHETIC, result.evidence_status)
        documents = result.retrieval_results[0].documents
        self.assertEqual(3, len(documents))
        self.assertTrue(all(document.source_domain == "demo.invalid" for document in documents))
        self.assertTrue(
            all(document.url.startswith("https://demo.invalid/") for document in documents)
        )
        self.assertLessEqual(
            result.judge_output.confidence_score + result.judge_output.uncertainty_score,
            1.0,
        )
        self.assertTrue(result.judge_output.reasoning_summary.startswith("Synthetic demonstration"))
        self.assertEqual("[UNVERIFIABLE — DEMO MODE]", result.corrected_claim.corrected_text)

    def test_demo_embeddings_are_stable_and_input_sensitive(self) -> None:
        first = deterministic_embedding("same")
        second = deterministic_embedding("same")
        different = deterministic_embedding("different")
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_live_mode_requires_a_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            VeritasPipeline(
                mode=ExecutionMode.LIVE,
                openai_api_key=None,
            )

    def test_input_limit_fails_before_processing(self) -> None:
        pipeline = VeritasPipeline(mode=ExecutionMode.DEMO, run_consistency=False)
        with self.assertRaisesRegex(ValueError, "4000"):
            pipeline.run("x" * 4001)

    def test_high_impact_domain_modes_are_rejected(self) -> None:
        pipeline = VeritasPipeline(mode=ExecutionMode.DEMO, run_consistency=False)
        with self.assertRaisesRegex(ValueError, "general research"):
            pipeline.run("A sufficiently long claim.", domain_mode=DomainMode.MEDICAL)
