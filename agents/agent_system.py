"""
VERITAS-Ω — Multi-Agent Reasoning System

Agent Roles
───────────
ProAgent       → constructs the strongest argument that the claim is TRUE
ConAgent       → constructs the strongest argument that the claim is FALSE
AdversarialAgent → identifies weaknesses, gaps, or bias in the available evidence

Constraints (non-negotiable):
  1. Agents MUST cite at least one retrieved document.
  2. All key_points must be directly traceable to cited evidence.
  3. Confidence reflects ONLY the evidence quality, not prior belief.
  4. No free-form opinion; outputs are structured AgentOutput objects.

Agent Orchestration:
  The orchestrator runs agents in parallel (via asyncio or thread pool)
  then collects outputs for the Judge.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import openai

from config.settings import MODEL_CFG
from core.schemas import (
    AgentOutput,
    Claim,
    EvidenceReference,
    RetrievedDocument,
)

logger = logging.getLogger(__name__)


# ─── Shared prompt components ─────────────────────────────────────────────────

_BASE_SYSTEM = """
You are a rigorous fact-verification agent. Your ONLY job is to analyse
the provided evidence and produce a structured JSON output.

RULES:
- You may ONLY use the evidence documents provided. Do NOT use prior knowledge.
- Every key_point must be directly supported by a cited evidence_reference.
- confidence must reflect evidence quality (not your prior belief).
- Return ONLY valid JSON matching the schema below. No markdown, no prose.

Output Schema:
{
  "stance": "<supports|contradicts|flags_weakness>",
  "key_points": ["<point1>", ...],        // 1-5 points
  "evidence_references": [
    {"doc_id": "<id>", "url": "<url>", "excerpt": "<≤256 chars>"}
  ],
  "confidence": <float 0-1>,
  "reasoning": "<structured paragraph ≤1024 chars>"
}
"""

_PRO_SYSTEM = (
    _BASE_SYSTEM
    + "\nYour role: PRO AGENT. Build the strongest case that the claim is TRUE "
    "using ONLY the provided evidence. Stance must be 'supports'."
)

_CON_SYSTEM = (
    _BASE_SYSTEM
    + "\nYour role: CON AGENT. Build the strongest case that the claim is FALSE "
    "using ONLY the provided evidence. Stance must be 'contradicts'."
)

_ADV_SYSTEM = (
    _BASE_SYSTEM
    + "\nYour role: ADVERSARIAL AGENT. Identify weaknesses, missing evidence, "
    "potential bias, or logical gaps in the evidence set. "
    "Do NOT take a pro/con stance. Stance must be 'flags_weakness'."
)

_USER_TEMPLATE = """
Claim: {claim_text}

Evidence Documents:
{evidence_block}
"""


# ══════════════════════════════════════════════════════════════════════════════
# BASE AGENT
# ══════════════════════════════════════════════════════════════════════════════

class BaseAgent:
    role: str = "base"
    system_prompt: str = _BASE_SYSTEM

    def __init__(self, client: Optional[openai.OpenAI] = None):
        self._client = client or openai.OpenAI()

    def run(
        self,
        claim: Claim,
        documents: List[RetrievedDocument],
    ) -> AgentOutput:
        evidence_block = self._format_evidence(documents)
        user_msg = _USER_TEMPLATE.format(
            claim_text=claim.claim_text,
            evidence_block=evidence_block,
        )
        t0 = time.perf_counter()
        raw = self._call_llm(user_msg)
        elapsed = time.perf_counter() - t0

        parsed = self._parse(raw, claim.claim_id, documents)
        logger.info(
            "Agent[%s] claim=%s confidence=%.2f in %.2fs",
            self.role,
            claim.claim_id,
            parsed.confidence,
            elapsed,
        )
        return parsed

    def _call_llm(self, user_msg: str) -> str:
        response = self._client.chat.completions.create(
            model=MODEL_CFG.agent_model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            temperature=MODEL_CFG.temperature_agent,
            max_tokens=MODEL_CFG.max_tokens_agent,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def _parse(
        self,
        raw: str,
        claim_id: str,
        documents: List[RetrievedDocument],
    ) -> AgentOutput:
        data = json.loads(raw)
        doc_map = {d.doc_id: d for d in documents}

        refs = []
        for r in data.get("evidence_references", []):
            refs.append(
                EvidenceReference(
                    doc_id=r.get("doc_id", ""),
                    url=r.get("url", ""),
                    excerpt=r.get("excerpt", "")[:256],
                )
            )

        # If LLM cited doc_ids not in our set, drop them silently
        refs = [r for r in refs if r.doc_id in doc_map]

        # Fallback: if no valid refs, use the top document
        if not refs and documents:
            top = documents[0]
            refs = [
                EvidenceReference(
                    doc_id=top.doc_id,
                    url=top.url,
                    excerpt=top.snippet[:256],
                )
            ]

        return AgentOutput(
            agent_role=self.role,
            claim_id=claim_id,
            stance=data.get("stance", "neutral"),
            key_points=data.get("key_points", [])[:5],
            evidence_references=refs,
            confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
            reasoning=data.get("reasoning", "")[:1024],
        )

    @staticmethod
    def _format_evidence(docs: List[RetrievedDocument]) -> str:
        lines = []
        for i, d in enumerate(docs, 1):
            lines.append(
                f"[{i}] doc_id={d.doc_id} | trust={d.trust_score:.2f}\n"
                f"    Title: {d.title}\n"
                f"    URL: {d.url}\n"
                f"    Snippet: {d.snippet[:400]}\n"
            )
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SPECIALISED AGENTS
# ══════════════════════════════════════════════════════════════════════════════

class ProAgent(BaseAgent):
    role = "pro"
    system_prompt = _PRO_SYSTEM


class ConAgent(BaseAgent):
    role = "con"
    system_prompt = _CON_SYSTEM


class AdversarialAgent(BaseAgent):
    role = "adversarial"
    system_prompt = _ADV_SYSTEM


# ══════════════════════════════════════════════════════════════════════════════
# AGENT ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

class AgentOrchestrator:
    """
    Runs Pro, Con, and Adversarial agents in parallel threads.

    Pseudocode:
    ───────────
    function orchestrate(claim, documents):
        agents = [ProAgent, ConAgent, AdversarialAgent]
        futures = {executor.submit(agent.run, claim, documents): agent
                   for agent in agents}
        outputs = []
        for future in as_completed(futures, timeout=60):
            try:
                outputs.append(future.result())
            except Exception as e:
                log_warning(e)   // partial failure: continue with other agents
        return outputs
    """

    def __init__(self, client: Optional[openai.OpenAI] = None):
        self._pro = ProAgent(client)
        self._con = ConAgent(client)
        self._adv = AdversarialAgent(client)

    def orchestrate(
        self,
        claim: Claim,
        documents: List[RetrievedDocument],
    ) -> List[AgentOutput]:
        if not documents:
            raise ValueError(
                f"No documents available to run agents for claim {claim.claim_id}"
            )

        outputs: List[AgentOutput] = []
        agents = [self._pro, self._con, self._adv]

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(agent.run, claim, documents): agent.role
                for agent in agents
            }
            for future in as_completed(future_map, timeout=90):
                role = future_map[future]
                try:
                    result = future.result()
                    outputs.append(result)
                    logger.debug("Agent[%s] completed.", role)
                except Exception as exc:
                    logger.warning(
                        "Agent[%s] failed for claim %s: %s",
                        role,
                        claim.claim_id,
                        exc,
                    )

        if not outputs:
            raise RuntimeError(
                f"All agents failed for claim {claim.claim_id}. Cannot proceed."
            )

        # Sort for deterministic ordering: pro → con → adversarial
        _order = {"pro": 0, "con": 1, "adversarial": 2}
        outputs.sort(key=lambda o: _order.get(o.agent_role, 99))

        logger.info(
            "Orchestrator: %d/%d agents succeeded for claim %s",
            len(outputs),
            len(agents),
            claim.claim_id,
        )
        return outputs
