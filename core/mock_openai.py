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
                "key_points": ["Tier 1 evidence confirms a statistically significant correlation (p < 0.01).", "Cross-verified across multiple peer-reviewed meta-analyses."],
                "evidence_references": [{"doc_id": "mock_doc_1", "url": "https://mocksource.com/article1", "excerpt": "Clear evidence supporting the claim with high methodological rigor."}],
                "confidence": 0.88,
                "reasoning": "The evidence overwhelmingly supports the claim. Based on Tier 1 scientific consensus, there is virtually zero aleatoric uncertainty in the measurement mechanisms."
            })
        elif "CON AGENT" in system_prompt or "Agent A" in system_prompt:
            content = json.dumps({
                "stance": "contradicts",
                "key_points": ["Tier 2 institutional data contradicts the primary claim.", "Sample sizes in supporting studies fail statistical power tests."],
                "evidence_references": [{"doc_id": "mock_doc_2", "url": "https://mocksource.com/article2", "excerpt": "Studies failed to replicate the original findings under controlled conditions."}],
                "confidence": 0.65,
                "reasoning": "There are significant methodological flaws in the supporting evidence. Tier 2 data directly contradicts the premise, indicating high epistemic uncertainty regarding long-term effects."
            })
        elif "ADVERSARIAL AGENT" in system_prompt or "Agent C" in system_prompt:
            content = json.dumps({
                "stance": "flags_weakness",
                "key_points": ["Detected cherry-picked data focusing only on short-term outcomes.", "False authority fallacy present in Tier 3 media coverage."],
                "evidence_references": [{"doc_id": "mock_doc_1", "url": "https://mocksource.com/article1", "excerpt": "The researchers note that long-term longitudinal tracking was not performed."}],
                "confidence": 0.72,
                "reasoning": "Rigorous adversarial analysis reveals significant funding bias in the primary sources. The lack of long-term tracking introduces critical Epistemic uncertainty, while inherent variability across demographics introduces Aleatoric uncertainty."
            })
        elif "fact-correction engine" in system_prompt or "CORRECTED CLAIM" in system_prompt:
            content = json.dumps({"corrected_text": "The phenomenon is observed under strictly controlled short-term conditions, but long-term longitudinal data remains statistically inconclusive. Original claim contained cherry-picked absolutes."})
        elif "synthesising fact-verification" in system_prompt or "Chief Judge" in system_prompt:
            content = "UNCERTAINTY DECOMPOSITION: High Epistemic uncertainty exists due to missing long-term longitudinal data, compounded by Aleatoric variability in demographic responses. PROBABILISTIC AGGREGATION: The final verdict (PARTIALLY_TRUE) is reached because while the Pro Agent found statistically significant short-term correlations (conf=0.88), the Adversarial Agent correctly flagged cherry-picked data and funding bias (conf=0.72). The structural variance mathematically bounds our confidence to 62%, mandating a cautious partial verdict."
        else:
            content = json.dumps({"result": "mock_response"})

        return MockChatCompletion(content)

class MockOpenAIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.chat = MockChat()
        self.embeddings = MockEmbeddings()

