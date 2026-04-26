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
                "claim_text": "Is it universally illegal? Did the UN create such law? Does it override national laws? Is there mandatory imprisonment?",
                "entities": ["UN Law", "Universal Legality", "National Override", "Mandatory Imprisonment"],
                "temporal_scope": {"start": None, "end": None, "is_current": True},
                "claim_type": "factual"
            }])
        elif "PRO AGENT" in system_prompt or "Agent B" in system_prompt:
            content = json.dumps({
                "stance": "supports",
                "key_points": ["Evidence suggests some international agreements align with this concept.", "Several legal experts cite alignment with the UN framework."],
                "evidence_references": [{"doc_id": "mock_doc_1", "url": "https://mocksource.com/article1", "excerpt": "International law frameworks loosely support the underlying principles."}],
                "confidence": 0.88,
                "reasoning": "The evidence supports the premise. However, there is no universal scientific or legal consensus, only institutional recommendations."
            })
        elif "CON AGENT" in system_prompt or "Agent A" in system_prompt:
            content = json.dumps({
                "stance": "contradicts",
                "key_points": ["National sovereignty supersedes the UN framework in 80% of jurisdictions.", "No mandatory imprisonment clause exists in the treaties."],
                "evidence_references": [{"doc_id": "mock_doc_2", "url": "https://mocksource.com/article2", "excerpt": "Treaties lack enforcement mechanisms and do not override domestic laws."}],
                "confidence": 0.65,
                "reasoning": "The claim fails the sovereignty test. Tier 2 data directly contradicts the premise of universal illegality."
            })
        elif "ADVERSARIAL AGENT" in system_prompt or "Agent C" in system_prompt:
            content = json.dumps({
                "stance": "flags_weakness",
                "key_points": ["Detected conflation between 'resolutions' and 'binding law'.", "False authority fallacy in interpreting UN guidelines as mandatory."],
                "evidence_references": [{"doc_id": "mock_doc_3", "url": "https://mocksource.com/article3", "excerpt": "The resolution is non-binding and acts only as a soft-power guideline."}],
                "confidence": 0.72,
                "reasoning": "Rigorous adversarial analysis reveals severe semantic drift. The original claim confuses non-binding UN resolutions with enforceable international law."
            })
        elif "fact-correction engine" in system_prompt or "CORRECTED CLAIM" in system_prompt:
            content = json.dumps({"corrected_text": "The UN has issued non-binding resolutions regarding this topic, but it does not constitute universally enforceable international law, nor does it mandate imprisonment."})
        elif "synthesising fact-verification" in system_prompt or "Chief Judge" in system_prompt:
            content = "UNCERTAINTY DECOMPOSITION: Epistemic uncertainty driven by jurisdictional variance; Aleatoric uncertainty driven by subjective enforcement. PROBABILISTIC AGGREGATION: The final mathematical calculation inherently balances the supportive frameworks with the non-binding reality."
        else:
            content = json.dumps({"result": "mock_response"})

        return MockChatCompletion(content)

class MockOpenAIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.chat = MockChat()
        self.embeddings = MockEmbeddings()

