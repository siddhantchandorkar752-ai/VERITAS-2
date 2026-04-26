"""
VERITAS-Ω — Evidence Graph Builder

Graph Definition
────────────────
G = (V, E)
V = {claim_nodes} ∪ {evidence_nodes}
E ⊆ V × V  with type ∈ {supports, contradicts, neutral}

Edge weight (confidence) is computed as:
  edge.confidence = (agent_confidence + doc.trust_score) / 2

Graph Construction Algorithm
─────────────────────────────
function build_graph(claim, agent_outputs, documents):
    G = empty graph
    G.add_node(claim_node)          // central claim node

    for doc in documents:
        G.add_node(evidence_node(doc))

    for agent_output in agent_outputs:
        for ref in agent_output.evidence_references:
            doc = lookup(ref.doc_id)
            edge_type = map_stance(agent_output.stance)
            confidence = (agent_output.confidence + doc.trust_score) / 2
            G.add_edge(claim_node → evidence_node,
                       type=edge_type,
                       confidence=confidence,
                       source_url=doc.url,
                       reasoning=agent_output.reasoning)
    return G

Update Rule (on new evidence):
  If a new document d is added post-construction:
    1. Embed d → compare cosine with existing evidence nodes.
    2. If cosine ≥ dedup_threshold → merge (keep higher trust_score).
    3. Else → add new evidence_node + edges from matching agents.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.schemas import (
    AgentOutput,
    Claim,
    EdgeType,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    RetrievedDocument,
)

logger = logging.getLogger(__name__)

# ─── Stance → EdgeType mapping ───────────────────────────────────────────────

_STANCE_MAP: Dict[str, EdgeType] = {
    "supports":         EdgeType.SUPPORTS,
    "contradicts":      EdgeType.CONTRADICTS,
    "flags_weakness":   EdgeType.CONTRADICTS,  # treated as contradicting evidence
    "neutral":          EdgeType.NEUTRAL,
}


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════════════════

class EvidenceGraphBuilder:
    """
    Constructs and maintains the evidence graph for a single claim.
    """

    def build(
        self,
        claim: Claim,
        agent_outputs: List[AgentOutput],
        documents: List[RetrievedDocument],
    ) -> EvidenceGraph:
        graph = EvidenceGraph(claim_id=claim.claim_id)

        # ── 1. Claim node ────────────────────────────────────────────────
        claim_node = EvidenceNode(
            node_id=claim.claim_id,
            node_type="claim",
            text=claim.claim_text,
            trust_score=0.0,
            metadata={"claim_type": claim.claim_type.value},
        )
        graph.nodes.append(claim_node)

        # ── 2. Evidence nodes ─────────────────────────────────────────────
        doc_map: Dict[str, RetrievedDocument] = {d.doc_id: d for d in documents}
        for doc in documents:
            ev_node = EvidenceNode(
                node_id=doc.doc_id,
                node_type="evidence",
                text=doc.snippet,
                trust_score=doc.trust_score,
                metadata={
                    "url":    doc.url,
                    "title":  doc.title,
                    "domain": doc.source_domain,
                    "published_date": doc.published_date or "",
                },
            )
            graph.nodes.append(ev_node)

        # ── 3. Edges from agent outputs ───────────────────────────────────
        for agent_out in agent_outputs:
            edge_type = _STANCE_MAP.get(agent_out.stance, EdgeType.NEUTRAL)
            for ref in agent_out.evidence_references:
                doc = doc_map.get(ref.doc_id)
                if doc is None:
                    logger.warning(
                        "Graph builder: doc_id %s not in document set; skipping edge.",
                        ref.doc_id,
                    )
                    continue

                # confidence = harmonic combination of agent and doc trust
                confidence = (agent_out.confidence + doc.trust_score) / 2.0
                confidence = round(min(max(confidence, 0.0), 1.0), 4)

                edge = EvidenceEdge(
                    source_id=claim.claim_id,
                    target_id=ref.doc_id,
                    edge_type=edge_type,
                    confidence=confidence,
                    source_url=doc.url,
                    reasoning=f"[{agent_out.agent_role}] {ref.excerpt[:200]}",
                )
                graph.edges.append(edge)

        logger.info(
            "EvidenceGraph built: claim=%s nodes=%d edges=%d",
            claim.claim_id,
            len(graph.nodes),
            len(graph.edges),
        )
        return graph

    def update_graph(
        self,
        graph: EvidenceGraph,
        new_doc: RetrievedDocument,
        new_agent_output: Optional[AgentOutput],
        cosine_threshold: float = 0.92,
    ) -> EvidenceGraph:
        """
        Update rule: add a new evidence node (if not duplicate) and
        edges from the new agent output.

        Args:
            cosine_threshold: skip new_doc if its text is too similar
                              to an existing node (handled upstream by retriever).
        """
        existing_ids = {n.node_id for n in graph.nodes}
        if new_doc.doc_id not in existing_ids:
            graph.nodes.append(
                EvidenceNode(
                    node_id=new_doc.doc_id,
                    node_type="evidence",
                    text=new_doc.snippet,
                    trust_score=new_doc.trust_score,
                    metadata={
                        "url":    new_doc.url,
                        "title":  new_doc.title,
                        "domain": new_doc.source_domain,
                    },
                )
            )

        if new_agent_output:
            edge_type = _STANCE_MAP.get(new_agent_output.stance, EdgeType.NEUTRAL)
            for ref in new_agent_output.evidence_references:
                if ref.doc_id == new_doc.doc_id:
                    confidence = (new_agent_output.confidence + new_doc.trust_score) / 2.0
                    edge = EvidenceEdge(
                        source_id=graph.claim_id,
                        target_id=ref.doc_id,
                        edge_type=edge_type,
                        confidence=round(confidence, 4),
                        source_url=new_doc.url,
                        reasoning=f"[{new_agent_output.agent_role}] {ref.excerpt[:200]}",
                    )
                    graph.edges.append(edge)

        return graph

    # ── Graph analytics helpers ───────────────────────────────────────────────

    @staticmethod
    def supporting_score(graph: EvidenceGraph) -> float:
        """
        Σ confidence of SUPPORTS edges / total edges.
        Returns 0.0 if no edges exist.
        """
        edges = graph.edges
        if not edges:
            return 0.0
        support_weight = sum(
            e.confidence for e in edges if e.edge_type == EdgeType.SUPPORTS
        )
        total_weight = sum(e.confidence for e in edges)
        return round(support_weight / max(total_weight, 1e-9), 4)

    @staticmethod
    def contradiction_score(graph: EvidenceGraph) -> float:
        """
        Σ confidence of CONTRADICTS edges / total edges.
        """
        edges = graph.edges
        if not edges:
            return 0.0
        contra_weight = sum(
            e.confidence for e in edges if e.edge_type == EdgeType.CONTRADICTS
        )
        total_weight = sum(e.confidence for e in edges)
        return round(contra_weight / max(total_weight, 1e-9), 4)
