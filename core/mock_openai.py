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
        if "claim extraction engine" in system_prompt or "Extract factual" in system_prompt:
            content = json.dumps([{
                "claim_text": "The verified atomic statement extracted from the input, stripped of all ambiguity and emotional bias.",
                "entities": ["Concept A", "Concept B"],
                "temporal_scope": {"start": None, "end": None, "is_current": True},
                "claim_type": "factual"
            }])
        elif "PRO AGENT" in system_prompt or "Agent B" in system_prompt:
            content = json.dumps({
                "stance": "supports",
                "key_points": ["Tier 1 evidence confirms a statistically significant correlation (p < 0.01) for the isolated variables.", "Cross-verified across multiple controlled trials."],
                "evidence_references": [{"doc_id": "mock_doc_1", "url": "https://mocksource.com/article1", "excerpt": "Clear evidence supporting the claim under short-term laboratory conditions."}],
                "confidence": 0.88,
                "reasoning": "The evidence robustly supports the claim under strict boundaries. However, I avoid declaring absolute consensus as longitudinal tracking is incomplete."
            })
        elif "CON AGENT" in system_prompt or "Agent A" in system_prompt:
            content = json.dumps({
                "stance": "contradicts",
                "key_points": ["Tier 2 institutional data contradicts the long-term viability of the primary claim.", "Sample sizes in supporting studies fail statistical power tests for broad populations."],
                "evidence_references": [{"doc_id": "mock_doc_2", "url": "https://mocksource.com/article2", "excerpt": "Studies failed to replicate the original findings across diverse demographics."}],
                "confidence": 0.65,
                "reasoning": "There are significant methodological limits in the supporting evidence. Tier 2 data directly contradicts the premise when applied broadly, indicating high epistemic uncertainty regarding long-term effects."
            })
        elif "ADVERSARIAL AGENT" in system_prompt or "Agent C" in system_prompt:
            content = json.dumps({
                "stance": "flags_weakness",
                "key_points": ["Detected cherry-picked data focusing only on short-term outcomes.", "False authority fallacy present in Tier 3 media interpretations of the core studies."],
                "evidence_references": [{"doc_id": "mock_doc_3", "url": "https://mocksource.com/article3", "excerpt": "The researchers explicitly note that long-term tracking was not performed."}],
                "confidence": 0.72,
                "reasoning": "Rigorous adversarial analysis reveals significant selection bias in the primary sources. The lack of long-term tracking introduces critical Epistemic uncertainty, which mathematically demands a penalty on the overall trust score."
            })
        elif "fact-correction engine" in system_prompt or "CORRECTED CLAIM" in system_prompt:
            content = json.dumps({"corrected_text": "The claimed effect occurs only under strict, short-term laboratory conditions; applying it to general populations over extended periods is unsupported due to missing longitudinal data."})
        elif "synthesising fact-verification" in system_prompt or "Chief Judge" in system_prompt:
            content = "UNCERTAINTY DECOMPOSITION: Severe Epistemic uncertainty exists due to missing longitudinal data, compounded by Aleatoric variability across demographics. PROBABILISTIC AGGREGATION: The final verdict (PARTIALLY_TRUE) mathematically synthesizes the Pro Agent's short-term evidence with the Con Agent's broad contradiction. The Adversarial Agent's exposure of cherry-picked boundaries actively suppresses the composite trust score, proving the claim is technically true but contextually misleading."
        else:
            content = json.dumps({"result": "mock_response"})

        return MockChatCompletion(content)

class MockOpenAIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.chat = MockChat()
        self.embeddings = MockEmbeddings()

