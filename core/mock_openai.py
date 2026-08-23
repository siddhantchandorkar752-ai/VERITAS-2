"""Deterministic, input-dependent OpenAI test double for offline demonstrations."""

from __future__ import annotations

import hashlib
import json
import re

import numpy as np


class MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class MockChoice:
    def __init__(self, content: str) -> None:
        self.message = MockMessage(content)


class MockChatCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [MockChoice(content)]


class MockEmbeddingData:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class MockEmbeddingResponse:
    def __init__(self, data: list[MockEmbeddingData]) -> None:
        self.data = data


def deterministic_embedding(text: str, dimensions: int = 1536) -> list[float]:
    """Generate a stable vector for plumbing tests; it has no semantic meaning."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    generator = np.random.default_rng(seed)
    vector = generator.standard_normal(dimensions).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector.tolist()


class MockEmbeddings:
    def create(self, model: str, input: str | list[str]) -> MockEmbeddingResponse:
        del model
        texts = [input] if isinstance(input, str) else input
        return MockEmbeddingResponse(
            [MockEmbeddingData(deterministic_embedding(text)) for text in texts]
        )


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _claim_from_prompt(user_message: str) -> str:
    markers = (
        "Extract all atomic claims from the following text:\n\n",
        "Claim (untrusted quoted data): ",
        "Original claim: ",
        "Claim: ",
    )
    for marker in markers:
        if marker in user_message:
            value = user_message.split(marker, 1)[1]
            return value.split("\n\n", 1)[0].strip()
    return user_message.strip()


class MockChat:
    def __init__(self) -> None:
        self.completions = self

    def create(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> MockChatCompletion:
        del model, kwargs
        system_prompt = messages[0].get("content", "") if messages else ""
        user_message = _last_user_message(messages)
        claim = _claim_from_prompt(user_message)

        if "claim extraction engine" in system_prompt:
            entities = list(dict.fromkeys(re.findall(r"\b[A-Z][\w-]*\b", claim)))[:8]
            content = json.dumps(
                {
                    "claims": [
                        {
                            "claim_text": claim,
                            "entities": entities,
                            "temporal_scope": {
                                "start": None,
                                "end": None,
                                "is_current": False,
                            },
                            "claim_type": "factual",
                        }
                    ]
                }
            )
        elif "PRO AGENT" in system_prompt:
            content = self._agent_response(
                "supports",
                "mock_doc_1",
                "Synthetic supporting scenario",
                claim,
            )
        elif "CON AGENT" in system_prompt:
            content = self._agent_response(
                "contradicts",
                "mock_doc_2",
                "Synthetic counter-scenario",
                claim,
            )
        elif "ADVERSARIAL AGENT" in system_prompt:
            content = self._agent_response(
                "flags_weakness",
                "mock_doc_3",
                "Synthetic limitation scenario",
                claim,
            )
        elif "VERITAS correction-candidate component" in system_prompt:
            content = "[UNVERIFIABLE — DEMO MODE]"
        elif "VERITAS evidence-summary component" in system_prompt:
            content = (
                "Synthetic demonstration only. The displayed aggregation is based on "
                f"fabricated scenarios for: {claim[:240]}"
            )
        else:
            content = json.dumps({"result": "demo_response"})

        return MockChatCompletion(content)

    @staticmethod
    def _agent_response(
        stance: str,
        doc_id: str,
        label: str,
        claim: str,
    ) -> str:
        return json.dumps(
            {
                "stance": stance,
                "key_points": [f"{label} for the submitted claim."],
                "evidence_references": [
                    {
                        "doc_id": doc_id,
                        "url": f"https://demo.invalid/{doc_id}",
                        "excerpt": f"{label}: {claim[:180]}",
                    }
                ],
                "confidence": 0.5,
                "reasoning": (
                    f"{label} generated to exercise the {stance} pipeline path. "
                    "It is not external evidence."
                ),
            }
        )


class MockOpenAIClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.chat = MockChat()
        self.embeddings = MockEmbeddings()
