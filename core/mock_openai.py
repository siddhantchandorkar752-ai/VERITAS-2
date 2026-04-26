import json
import uuid
import numpy as np
from types import SimpleNamespace

class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockChatCompletion:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockEmbeddingData:
    def __init__(self, embedding):
        self.embedding = embedding

class MockEmbeddingResponse:
    def __init__(self, data):
        self.data = data

class MockEmbeddings:
    def create(self, model, input):
        if isinstance(input, str):
            input = [input]
        # Return random embeddings of dimension 1536
        data = [MockEmbeddingData(np.random.rand(1536).tolist()) for _ in input]
        return MockEmbeddingResponse(data)

class MockChat:
    def __init__(self):
        self.completions = self

    def create(self, model, messages, **kwargs):
        system_prompt = messages[0]["content"] if messages else ""
        
        # Determine what kind of response is needed based on prompt keywords
        if "claim extraction engine" in system_prompt:
            content = json.dumps([{
                "claim_text": "The verified statement extracted from the input.",
                "entities": ["Concept A", "Concept B"],
                "temporal_scope": {"start": None, "end": None, "is_current": True},
                "claim_type": "factual"
            }])
        elif "PRO AGENT" in system_prompt:
            content = json.dumps({
                "stance": "supports",
                "key_points": ["Strong correlation observed.", "Multiple peer-reviewed sources agree."],
                "evidence_references": [{"doc_id": "dummy_id", "url": "https://example.com/pro", "excerpt": "Clear evidence supporting the claim."}],
                "confidence": 0.85,
                "reasoning": "The evidence overwhelmingly supports the claim with consistent data points across multiple studies."
            })
        elif "CON AGENT" in system_prompt:
            content = json.dumps({
                "stance": "contradicts",
                "key_points": ["Sample sizes were too small.", "Alternative variables explain the effect."],
                "evidence_references": [{"doc_id": "dummy_id", "url": "https://example.com/con", "excerpt": "Studies failed to replicate the original findings."}],
                "confidence": 0.60,
                "reasoning": "There are significant methodological flaws in the supporting evidence, and newer studies directly contradict the premise."
            })
        elif "ADVERSARIAL AGENT" in system_prompt:
            content = json.dumps({
                "stance": "flags_weakness",
                "key_points": ["Funding bias in primary sources.", "Long-term data is missing."],
                "evidence_references": [{"doc_id": "dummy_id", "url": "https://example.com/adv", "excerpt": "The researchers note that long-term longitudinal tracking was not performed."}],
                "confidence": 0.45,
                "reasoning": "While the immediate data looks solid, the lack of long-term tracking and potential funding biases introduce notable uncertainty."
            })
        elif "fact-correction engine" in system_prompt:
            content = "This is a corrected, more accurate version of the original statement based on verified evidence."
        elif "synthesising fact-verification" in system_prompt:
            content = "The agents presented a divided view. While initial studies support the claim, rigorous counter-evidence and potential biases require a cautious, partially true verdict."
        else:
            content = json.dumps({"result": "mock_response"})

        return MockChatCompletion(content)

class MockOpenAIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.chat = MockChat()
        self.embeddings = MockEmbeddings()

