"""
VERITAS-Ω — Main Pipeline Orchestrator

Wires all modules into a single end-to-end pipeline.

Data Flow:
──────────
raw_input
  → ClaimExtractor        → List[Claim]
  → HybridRetriever       → List[RetrievalResult]
  → TrustScorer           → documents with trust_scores
  → AgentOrchestrator     → List[AgentOutput]
  → TrustScorer (CSA)     → updated trust with cross-source agreement
  → EvidenceGraphBuilder  → EvidenceGraph
  → JudgeSystem           → JudgeOutput
  → ConsistencyLayer      → ConsistencyResult
  → CorrectionEngine      → CorrectedClaim
  → AuditLogger.finalise  → AuditTrace
  → VeritasResult         (returned to API)
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import os
import openai

from agents.agent_system import AgentOrchestrator
from agents.judge_system import JudgeSystem
from audit.audit_logger import AuditLogger
from config.settings import MODEL_CFG
from consistency.consistency_layer import ConsistencyLayer
from core.claim_extractor import ClaimExtractor
from core.schemas import DomainMode, JudgeOutput, VeritasResult
from correction.correction_engine import CorrectionEngine
from graph.evidence_graph import EvidenceGraphBuilder
from retrieval.hybrid_retriever import HybridRetriever
from scoring.trust_scorer import TrustScorer

logger = logging.getLogger(__name__)


from core.mock_openai import MockOpenAIClient

class VeritasPipeline:
    """
    Top-level pipeline. All dependencies are injected for testability.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        run_consistency: bool = True,
        n_consistency_runs: int = 3,
    ):
        use_mock = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
        if use_mock or not openai_api_key:
            logger.info("Initializing with MockOpenAIClient (Offline/Free Mode)")
            client = MockOpenAIClient()
        else:
            client = openai.OpenAI(api_key=openai_api_key)

        self._extractor     = ClaimExtractor(client)
        self._retriever     = HybridRetriever(openai_client=client)
        self._trust_scorer  = TrustScorer()
        self._orchestrator  = AgentOrchestrator(client)
        self._graph_builder = EvidenceGraphBuilder()
        self._judge         = JudgeSystem(client)
        self._corrector     = CorrectionEngine(client)
        self._consistency   = ConsistencyLayer(n_runs=n_consistency_runs) if run_consistency else None
        self._run_consistency = run_consistency

    def run(
        self,
        raw_input: str,
        domain_mode: DomainMode = DomainMode.GENERAL,
        session_id: Optional[str] = None,
    ) -> VeritasResult:
        """
        Execute the full VERITAS-Ω pipeline.

        Returns a VeritasResult containing all intermediate and final outputs.
        Raises on critical failures (e.g., no claims extracted, all agents fail).
        """
        session_id = session_id or str(uuid.uuid4())
        logger.info("Pipeline START session=%s domain=%s", session_id, domain_mode.value)

        # ── 1. Claim Extraction ───────────────────────────────────────────
        claims = self._extractor.extract(raw_input)
        if not claims:
            raise ValueError("ClaimExtractor returned no claims from the input.")

        # Process the primary (first) claim for full pipeline
        # Multi-claim batch processing can be added here
        primary_claim = claims[0]

        audit = AuditLogger(
            claim_id=primary_claim.claim_id,
            session_id=session_id,
            domain_mode=domain_mode,
        )
        audit.log_step("claim_extraction", raw_input, claims)

        # ── 2. Retrieval ──────────────────────────────────────────────────
        retrieval_results = []
        all_documents = []
        for claim in claims:
            ret = self._retriever.retrieve(claim)
            retrieval_results.append(ret)
            all_documents.extend(ret.documents)

        # Use documents for primary claim
        primary_docs = retrieval_results[0].documents
        audit.log_step("retrieval", primary_claim.dict(), [d.dict() for d in primary_docs])

        # ── 3. Initial Trust Scoring (without CSA) ────────────────────────
        primary_docs = self._trust_scorer.score_documents(primary_docs)
        audit.log_step("trust_scoring_initial", [d.doc_id for d in primary_docs],
                       [d.trust_score for d in primary_docs])

        # ── 4. Agent Orchestration ────────────────────────────────────────
        agent_outputs = self._orchestrator.orchestrate(primary_claim, primary_docs)
        audit.log_step("agent_orchestration", primary_claim.claim_id,
                       [a.dict() for a in agent_outputs])

        # ── 5. Refine Trust Scoring with CSA ─────────────────────────────
        stance_map = {}
        for ao in agent_outputs:
            for ref in ao.evidence_references:
                stance_map[ref.doc_id] = ao.stance
        primary_docs = self._trust_scorer.score_documents(primary_docs, stances=stance_map)

        # ── 6. Evidence Graph ─────────────────────────────────────────────
        evidence_graph = self._graph_builder.build(
            primary_claim, agent_outputs, primary_docs
        )
        audit.log_step("evidence_graph", primary_claim.claim_id,
                       {"nodes": len(evidence_graph.nodes),
                        "edges": len(evidence_graph.edges)})

        # ── 7. Judge ──────────────────────────────────────────────────────
        judge_output = self._judge.judge(
            primary_claim,
            agent_outputs,
            primary_docs,
            evidence_graph,
            domain_mode,
        )
        audit.log_step("judge", primary_claim.claim_id, judge_output.dict())

        # ── 8. Consistency Check ──────────────────────────────────────────
        consistency_result = None
        if self._run_consistency and self._consistency:
            def _pipeline_fn(claim, dm, seed):
                docs = self._retriever.retrieve(claim).documents
                docs = self._trust_scorer.score_documents(docs)
                agent_outs = self._orchestrator.orchestrate(claim, docs)
                graph = self._graph_builder.build(claim, agent_outs, docs)
                return self._judge.judge(claim, agent_outs, docs, graph, dm)

            try:
                consistency_result = self._consistency.evaluate(
                    primary_claim, domain_mode, _pipeline_fn
                )
                audit.log_step("consistency", primary_claim.claim_id, consistency_result.dict())
            except Exception as exc:
                logger.warning("Consistency layer error: %s", exc)

        # ── 9. Correction ─────────────────────────────────────────────────
        corrected_claim = self._corrector.correct(
            primary_claim, judge_output, primary_docs
        )
        audit.log_step("correction", primary_claim.claim_id, corrected_claim.dict())

        # ── 10. Finalise Audit ────────────────────────────────────────────
        audit_trace = audit.finalise(judge_output.verdict)

        result = VeritasResult(
            session_id=session_id,
            raw_input=raw_input,
            claims=claims,
            retrieval_results=retrieval_results,
            evidence_graph=evidence_graph,
            agent_outputs=agent_outputs,
            judge_output=judge_output,
            consistency_result=consistency_result,
            corrected_claim=corrected_claim,
            audit_trace=audit_trace,
            domain_mode=domain_mode,
        )

        logger.info(
            "Pipeline DONE session=%s verdict=%s conf=%.3f",
            session_id,
            judge_output.verdict.value,
            judge_output.confidence_score,
        )
        return result
