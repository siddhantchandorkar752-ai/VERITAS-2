"""
VERITAS-Ω — Hybrid Retrieval Engine
Implements BM25 (sparse) + Dense Embedding (vector) retrieval
fused via Reciprocal Rank Fusion (RRF).

Algorithm Detail
────────────────
1. BM25 scoring:
   BM25(q, d) = Σ_t IDF(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 - b + b·|d|/avgdl))
   k1 = 1.5, b = 0.75  (standard Robertson parameters)

2. Dense retrieval:
   score(q, d) = cosine(E(q), E(d))
   where E = text-embedding-3-small

3. Reciprocal Rank Fusion:
   RRF(d) = Σ_{r ∈ rankers} 1 / (k + rank_r(d))
   k = 60  (prevents high-rank bias)

4. Deduplication:
   For doc pairs with cosine(embed_i, embed_j) >= threshold (0.92),
   keep the one ranked earlier by reciprocal-rank fusion.

5. Trust scoring is applied after fusion (see scoring/trust_scorer.py).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

import numpy as np
import openai
import requests
from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from config.settings import MODEL_CFG, RETRIEVAL_CFG
from core.schemas import Claim, RetrievalResult, RetrievedDocument

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "VERITAS-Research-Prototype/2.1 (+https://github.com/siddhantchandorkar752-ai/VERITAS-2)"
)


# ══════════════════════════════════════════════════════════════════════════════
# BM25 IMPLEMENTATION (in-memory, for retrieved corpus)
# ══════════════════════════════════════════════════════════════════════════════


class BM25:
    """
    In-memory BM25 scorer.
    Constructed over a corpus; scores a query against the corpus.

    Parameters (Robertson et al., 1994):
        k1 = 1.5   — term frequency saturation
        b  = 0.75  — length normalisation
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._corpus: list[list[str]] = []
        self._doc_lens: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = defaultdict(int)
        self._N: int = 0

    def fit(self, documents: list[str]) -> BM25:
        self._corpus = [self._tokenise(d) for d in documents]
        self._N = len(self._corpus)
        self._doc_lens = [len(d) for d in self._corpus]
        self._avgdl = sum(self._doc_lens) / max(self._N, 1)
        self._df = defaultdict(int)
        for tokens in self._corpus:
            for term in set(tokens):
                self._df[term] += 1
        return self

    def score(self, query: str) -> np.ndarray:
        """Returns a (N,) array of BM25 scores for each document."""
        q_tokens = self._tokenise(query)
        scores = np.zeros(self._N, dtype=np.float64)
        for term in q_tokens:
            if self._df[term] == 0:
                continue
            idf = math.log((self._N - self._df[term] + 0.5) / (self._df[term] + 0.5) + 1.0)
            for i, doc_tokens in enumerate(self._corpus):
                f = doc_tokens.count(term)
                denom = f + self.k1 * (
                    1 - self.b + self.b * self._doc_lens[i] / max(self._avgdl, 1)
                )
                scores[i] += idf * (f * (self.k1 + 1)) / denom
        return scores

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════


class WikipediaAdapter:
    """Fetches candidate documents from Wikipedia Search API."""

    BASE_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def fetch(self, query: str, top_k: int = 10) -> list[RetrievedDocument]:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": top_k,
            "format": "json",
            "utf8": 1,
        }
        try:
            resp = self._session.get(
                self.BASE_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=(3.05, 8),
            )
            resp.raise_for_status()
            items = resp.json().get("query", {}).get("search", [])
        except Exception as exc:
            logger.warning("WikipediaAdapter error: %s", exc)
            return []

        docs = []
        for item in items:
            page_id = str(item["pageid"])
            url = f"https://en.wikipedia.org/?curid={page_id}"
            snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
            docs.append(
                RetrievedDocument(
                    doc_id=hashlib.sha256(url.encode()).hexdigest()[:16],
                    url=url,
                    title=item.get("title", ""),
                    snippet=snippet[:512],
                    source_domain="wikipedia.org",
                    published_date=None,
                    citation_count=0,
                )
            )
        return docs


class NewsAdapter:
    """
    Stub news adapter — replace API_KEY + endpoint with a real news provider
    (e.g., NewsAPI, GDELT) in production.
    """

    def fetch(self, query: str, top_k: int = 10) -> list[RetrievedDocument]:
        # Production: call newsapi.org or equivalent
        logger.info("NewsAdapter: stub returning empty (no API key configured)")
        return []


class ArxivAdapter:
    """Fetches papers from the arXiv API."""

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def fetch(self, query: str, top_k: int = 5) -> list[RetrievedDocument]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": top_k,
        }
        try:
            resp = self._session.get(
                self.BASE_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=(3.05, 10),
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("ArxivAdapter error: %s", exc)
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        try:
            root = DefusedET.fromstring(resp.text)
        except (ET.ParseError, DefusedXmlException) as exc:
            logger.warning("ArxivAdapter returned unsafe or malformed XML: %s", exc)
            return []
        docs = []
        for entry in root.findall("atom:entry", ns):
            link = entry.find("atom:id", ns)
            url = link.text.strip() if link is not None else ""
            if not url:
                continue
            title_el = entry.find("atom:title", ns)
            title = title_el.text.strip() if title_el is not None else ""
            summary_el = entry.find("atom:summary", ns)
            summary = summary_el.text.strip()[:512] if summary_el is not None else ""
            pub_el = entry.find("atom:published", ns)
            pub = pub_el.text[:10] if pub_el is not None else None
            docs.append(
                RetrievedDocument(
                    doc_id=hashlib.sha256(url.encode()).hexdigest()[:16],
                    url=url,
                    title=title,
                    snippet=summary,
                    source_domain="arxiv.org",
                    published_date=pub,
                    citation_count=0,
                )
            )
        return docs


# ══════════════════════════════════════════════════════════════════════════════
# DENSE EMBEDDING CLIENT
# ══════════════════════════════════════════════════════════════════════════════


class EmbeddingClient:
    """Wraps OpenAI embedding API with simple caching."""

    def __init__(self, client: openai.OpenAI | None = None):
        self._client = client or openai.OpenAI()
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, texts: list[str]) -> np.ndarray:
        """Returns (N, D) embedding matrix."""
        results = []
        uncached_indices = []
        uncached_texts = []

        for i, t in enumerate(texts):
            key = hashlib.sha256(t.encode()).hexdigest()
            if key in self._cache:
                results.append((i, self._cache[key]))
            else:
                uncached_indices.append(i)
                uncached_texts.append(t)
                results.append((i, None))

        if uncached_texts:
            response = self._client.embeddings.create(
                model=MODEL_CFG.embedding_model,
                input=uncached_texts,
            )
            for j, emb in enumerate(response.data):
                vec = np.array(emb.embedding, dtype=np.float32)
                key = hashlib.sha256(uncached_texts[j].encode()).hexdigest()
                self._cache[key] = vec
                results[uncached_indices[j]] = (uncached_indices[j], vec)

        results.sort(key=lambda x: x[0])
        return np.stack([r[1] for r in results])


# ══════════════════════════════════════════════════════════════════════════════
# HYBRID RETRIEVAL ENGINE
# ══════════════════════════════════════════════════════════════════════════════


class HybridRetriever:
    """
    Hybrid BM25 + Dense retrieval fused via RRF.

    Pseudocode:
    ───────────
    function retrieve(claim):
        query = build_query(claim)

        // Fetch raw candidates
        raw_docs = []
        for adapter in [WikipediaAdapter, ArxivAdapter, NewsAdapter]:
            raw_docs += adapter.fetch(query, top_k=top_k_bm25)

        // BM25 ranking
        corpus = [d.snippet for d in raw_docs]
        bm25.fit(corpus)
        bm25_scores = bm25.score(query)           // shape (N,)
        bm25_ranks  = argsort(-bm25_scores)       // descending

        // Dense ranking
        doc_embeds = embed([d.snippet for d in raw_docs])  // (N, D)
        q_embed    = embed([query])                         // (1, D)
        dense_scores = cosine_similarity(q_embed, doc_embeds)  // (N,)
        dense_ranks  = argsort(-dense_scores)

        // RRF fusion
        for doc_i in range(N):
            rrf[doc_i] = 1/(k + rank_bm25(doc_i)) + 1/(k + rank_dense(doc_i))
        fusion_ranks = argsort(-rrf)

        // Deduplication
        top_docs = raw_docs[fusion_ranks[:top_k_fusion]]
        top_docs = deduplicate(top_docs, threshold=0.92)

        return top_docs[:top_k_fusion]
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        openai_client: openai.OpenAI | None = None,
        demo_mode: bool = False,
    ):
        self._embedder = embedding_client or EmbeddingClient(openai_client)
        self._wiki = WikipediaAdapter()
        self._arxiv = ArxivAdapter()
        self._news = NewsAdapter()
        self._cfg = RETRIEVAL_CFG
        self._demo_mode = demo_mode

    def retrieve(self, claim: Claim) -> RetrievalResult:
        t0 = time.perf_counter()
        query = self._build_query(claim)[:500]

        # ── 1. Fetch candidates ───────────────────────────────────────────
        if self._demo_mode:
            raw_docs = self._demo_documents(claim)
        else:
            raw_docs: list[RetrievedDocument] = []
            raw_docs += self._wiki.fetch(query, top_k=self._cfg.top_k_bm25)
            raw_docs += self._arxiv.fetch(query, top_k=5)
            raw_docs += self._news.fetch(query, top_k=5)

        if not raw_docs:
            logger.warning("No documents retrieved for claim %s", claim.claim_id)
            return RetrievalResult(claim_id=claim.claim_id, documents=[])

        # ── 2. BM25 ranking ───────────────────────────────────────────────
        corpus = [d.title + " " + d.snippet for d in raw_docs]
        bm25 = BM25().fit(corpus)
        bm25_scores = bm25.score(query)
        bm25_ranks = np.argsort(-bm25_scores)  # descending

        # ── 3. Dense ranking ──────────────────────────────────────────────
        texts = [query] + corpus
        embeds = self._embedder.embed(texts)
        q_vec = embeds[0]  # (D,)
        d_vecs = embeds[1:]  # (N, D)
        dense_scores = self._cosine_batch(q_vec, d_vecs)  # (N,)
        dense_ranks = np.argsort(-dense_scores)

        # Store raw scores
        for i, doc in enumerate(raw_docs):
            doc.bm25_score = float(bm25_scores[i])
            doc.dense_score = float(dense_scores[i])

        # ── 4. RRF fusion ─────────────────────────────────────────────────
        N = len(raw_docs)
        rrf_scores = np.zeros(N, dtype=np.float64)
        # RRF ranks are one-based by definition.
        bm25_rank_map = {idx: rank for rank, idx in enumerate(bm25_ranks, start=1)}
        dense_rank_map = {idx: rank for rank, idx in enumerate(dense_ranks, start=1)}
        k = self._cfg.rrf_k

        for i in range(N):
            rrf_scores[i] = 1.0 / (k + bm25_rank_map[i]) + 1.0 / (k + dense_rank_map[i])
        fusion_order = np.argsort(-rrf_scores)

        for i, doc in enumerate(raw_docs):
            doc.fusion_score = float(rrf_scores[i])

        # ── 5. Deduplication ──────────────────────────────────────────────
        ordered = [raw_docs[i] for i in fusion_order]
        deduped = self._deduplicate(ordered, d_vecs[fusion_order])

        # ── 6. Top-K selection ────────────────────────────────────────────
        final = deduped[: self._cfg.top_k_fusion]

        logger.info(
            "HybridRetriever: claim=%s → %d docs in %.2fs",
            claim.claim_id,
            len(final),
            time.perf_counter() - t0,
        )
        return RetrievalResult(claim_id=claim.claim_id, documents=final)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_query(claim: Claim) -> str:
        """Combine claim text with salient entities for a richer query."""
        entity_str = " ".join(claim.entities[:5])
        return f"{claim.claim_text} {entity_str}".strip()

    @staticmethod
    def _demo_documents(claim: Claim) -> list[RetrievedDocument]:
        """Return explicit synthetic fixtures without making any network call."""

        scenarios = (
            ("mock_doc_1", "Synthetic supporting scenario", "supports"),
            ("mock_doc_2", "Synthetic counter-scenario", "contradicts"),
            ("mock_doc_3", "Synthetic limitation scenario", "limits"),
        )
        return [
            RetrievedDocument(
                doc_id=doc_id,
                url=f"https://demo.invalid/{doc_id}",
                title=title,
                snippet=(
                    f"Synthetic {stance} fixture for pipeline testing only: {claim.claim_text}"
                )[:512],
                source_domain="demo.invalid",
                published_date=None,
                citation_count=0,
            )
            for doc_id, title, stance in scenarios
        ]

    @staticmethod
    def _cosine_batch(query: np.ndarray, docs: np.ndarray) -> np.ndarray:
        """
        Compute cosine similarity between query vector and doc matrix.
        cosine(q, d) = (q · d) / (||q|| · ||d||)
        """
        q_norm = query / (np.linalg.norm(query) + 1e-10)
        d_norms = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-10)
        return d_norms @ q_norm  # (N,)

    def _deduplicate(
        self,
        docs: list[RetrievedDocument],
        embeds: np.ndarray,
    ) -> list[RetrievedDocument]:
        """
        Remove near-duplicates: for each pair (i, j) with cosine ≥ threshold,
        keep the one with higher fusion_score (already ranked in descending order,
        so simply skip later ones that are too similar to kept ones).
        """
        threshold = self._cfg.dedup_cosine_threshold
        norms = embeds / (np.linalg.norm(embeds, axis=1, keepdims=True) + 1e-10)
        kept_indices: list[int] = []

        for i in range(len(docs)):
            duplicate = False
            for j in kept_indices:
                sim = float(norms[i] @ norms[j])
                if sim >= threshold:
                    duplicate = True
                    break
            if not duplicate:
                kept_indices.append(i)

        return [docs[i] for i in kept_indices]
