"""
VERITAS-Ω — Claim Extraction Pipeline
Converts raw natural-language input into atomic, machine-verifiable claims.

Algorithm:
  1. Sentence segmentation via spaCy
  2. LLM-assisted atomic decomposition (one fact per claim)
  3. Entity extraction using NER
  4. Temporal scope resolution
  5. Claim type classification
  6. JSON schema validation via Pydantic
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import List, Optional

import openai

from config.settings import MODEL_CFG
from core.schemas import Claim, ClaimType, TemporalScope

logger = logging.getLogger(__name__)

# ─── Prompts ─────────────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM = """
You are a claim extraction engine. Given input text, decompose it into atomic,
independently verifiable claims. Each claim must express exactly ONE fact.

Rules:
- Do NOT introduce information not present in the source text.
- Each claim must be a complete, standalone declarative sentence.
- Classify claim_type as one of: factual | causal | statistical | opinion
- Extract named entities (people, places, organizations, quantities).
- Infer temporal_scope where stated; use null when unspecified.

Return ONLY a valid JSON array matching this schema:
[
  {
    "claim_text": "<string>",
    "entities": ["<entity1>", ...],
    "temporal_scope": {"start": "<ISO-date or null>", "end": "<ISO-date or null>", "is_current": <bool>},
    "claim_type": "<factual|causal|statistical|opinion>"
  }
]
"""

_EXTRACTION_USER = "Extract all atomic claims from the following text:\n\n{text}"


# ─── Core Extractor ──────────────────────────────────────────────────────────

class ClaimExtractor:
    """
    Extracts atomic claims from raw input text.

    Pseudocode:
    ───────────
    function extract(raw_text):
        segments = sentence_split(raw_text)          // §1: segment
        prompt   = build_extraction_prompt(segments) // §2: prompt construction
        llm_json = call_llm(prompt)                  // §3: LLM call
        raw_claims = parse_json(llm_json)            // §4: parse
        validated  = []
        for rc in raw_claims:
            claim = Claim(**rc)                      // §5: validate schema
            claim.source_input = raw_text
            validated.append(claim)
        return deduplicate(validated)                // §6: dedup
    """

    def __init__(self, client: Optional[openai.OpenAI] = None):
        self._client = client or openai.OpenAI()

    # ── public ───────────────────────────────────────────────────────────────

    def extract(self, raw_text: str) -> List[Claim]:
        """
        Main entry point. Returns a list of validated Claim objects.
        Raises ValueError if LLM returns malformed JSON or empty claims.
        """
        raw_text = raw_text.strip()
        if not raw_text:
            raise ValueError("Input text must not be empty.")

        t0 = time.perf_counter()
        llm_response = self._call_llm(raw_text)
        raw_claims = self._parse_response(llm_response)
        claims = self._validate_and_build(raw_claims, raw_text)
        claims = self._deduplicate(claims)

        logger.info(
            "ClaimExtractor: extracted %d claims in %.2fs",
            len(claims),
            time.perf_counter() - t0,
        )
        return claims

    # ── private ──────────────────────────────────────────────────────────────

    def _call_llm(self, text: str) -> str:
        response = self._client.chat.completions.create(
            model=MODEL_CFG.claim_extractor_model,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM},
                {"role": "user",   "content": _EXTRACTION_USER.format(text=text)},
            ],
            temperature=0.0,        # deterministic extraction
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return content

    def _parse_response(self, raw: str) -> List[dict]:
        """
        Parse LLM JSON output. The model is prompted for an array but may
        wrap it in {"claims": [...]} — handle both forms.
        """
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # try common wrapper keys
            for key in ("claims", "results", "output"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        raise ValueError(f"Unexpected LLM JSON shape: {type(data)}")

    def _validate_and_build(self, raw_claims: List[dict], source: str) -> List[Claim]:
        validated = []
        for i, rc in enumerate(raw_claims):
            try:
                ts_raw = rc.get("temporal_scope", {}) or {}
                ts = TemporalScope(
                    start=ts_raw.get("start"),
                    end=ts_raw.get("end"),
                    is_current=bool(ts_raw.get("is_current", False)),
                )
                claim = Claim(
                    claim_text=rc["claim_text"],
                    entities=rc.get("entities", []),
                    temporal_scope=ts,
                    claim_type=ClaimType(rc.get("claim_type", "factual")),
                    source_input=source,
                )
                validated.append(claim)
            except Exception as exc:
                logger.warning("Skipping malformed claim at index %d: %s", i, exc)
        return validated

    def _deduplicate(self, claims: List[Claim]) -> List[Claim]:
        """
        Remove near-duplicate claims using SHA-256 of normalised claim text.
        Normalisation: lowercase + collapse whitespace + strip punctuation.
        """
        seen: set = set()
        unique: List[Claim] = []
        for c in claims:
            key = self._normalise(c.claim_text)
            h = hashlib.sha256(key.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(c)
            else:
                logger.debug("Dedup: dropping duplicate claim '%s'", c.claim_text[:60])
        return unique

    @staticmethod
    def _normalise(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
