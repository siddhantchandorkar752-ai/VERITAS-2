# VERITAS research workbench

An evidence-aggregation research prototype for inspecting claim decomposition, retrieval, structured model outputs, heuristic scoring, evidence graphs, and local trace fingerprints.

[![Core quality gates](https://github.com/siddhantchandorkar752-ai/VERITAS-2/actions/workflows/ci.yml/badge.svg)](https://github.com/siddhantchandorkar752-ai/VERITAS-2/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

VERITAS does **not** compute, prove, or establish truth. Its labels, confidence values, uncertainty values, source scores, corrections, and model-generated text are experimental outputs that require source inspection and independent human verification.

## Evidence status

| Claim | Status | Evidence |
|---|---|---|
| Explicit demo and live execution modes | Implemented | Mode contract tests |
| Demo performs no retrieval/model network calls | Implemented | Network methods are patched to fail in the end-to-end demo test |
| Demo output is input-dependent and deterministic | Implemented | Mock-client and pipeline regression tests |
| Agent citations refer to retrieved documents | Implemented | Canonicalization tests reject unknown document IDs and replace URL/excerpt text from the retrieved record |
| Wikipedia and arXiv retrieval | Implemented, experimental | Mocked transport tests; live availability depends on external services |
| Evidence graph and heuristic aggregation | Implemented | Unit tests for graph/scoring boundaries |
| Local trace fingerprints | Implemented | Audit tests and UUID/path validation |
| Accuracy, calibration, fairness, robustness, or factual reliability | **Not established** | No labeled benchmark or reproducible evaluation artifact is published |
| Medical or legal verification | **Out of scope** | UI restricts use to general research exploration |
| Public hosted access | **Not established** | The current Streamlit URL redirects unauthenticated visitors to Streamlit authentication |

## Execution modes

### Demo mode (default)

```bash
set VERITAS_MODE=demo       # Windows PowerShell: $env:VERITAS_MODE = "demo"
streamlit run ui/app.py
```

Demo mode:

- makes no Wikipedia, arXiv, or model-provider request;
- creates deterministic synthetic embeddings, evidence, and structured agent responses;
- uses reserved `demo.invalid` URLs;
- labels every presented result synthetic.

Demo labels and numbers test the pipeline plumbing only. They say nothing about the submitted claim.

### Live research mode

```bash
export VERITAS_MODE=live
export OPENAI_API_KEY=your-secret-from-a-secure-store
streamlit run ui/app.py
```

Live mode fails closed when `OPENAI_API_KEY` is absent. It can send submitted text to Wikipedia, arXiv, and the configured OpenAI models. Review provider retention, privacy, acceptable-use, and cost policies before enabling it. Do not submit confidential, personal, privileged, regulated, or otherwise sensitive material.

## Architecture

```text
submitted text
  └─ claim extraction
      └─ retrieval
          ├─ demo: deterministic synthetic fixtures, no network
          └─ live: Wikipedia + arXiv candidates
              └─ BM25 + embedding ranks → reciprocal-rank fusion
                  └─ heuristic source scoring
                      └─ pro / con / adversarial structured outputs
                          └─ canonical citation validation
                              └─ evidence graph + bounded aggregation
                                  └─ optional correction candidate
                                      └─ local trace fingerprints
```

Trust boundaries:

- Retrieved titles, snippets, and model responses are untrusted data.
- Unknown citation IDs are rejected; URL and excerpt values are taken from the retrieved record, not copied from model output.
- All three agent roles must complete before aggregation continues.
- Source authority, recency, citation, agreement, confidence, and uncertainty values are hand-designed heuristics—not learned or calibrated probabilities.
- A SHA-256 trace value can detect a changed serialization. It is not a signature, immutable ledger, replay record, or proof that the underlying result is correct.

## Install

Requirements: Python 3.11–3.13.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[ui]"
```

The application no longer declares the previous unused ChromaDB, FastAPI, SciPy, python-dotenv, or PyVis stack. Streamlit currently brings Uvicorn transitively, and the OpenAI SDK brings its own HTTP client; neither is imported directly by VERITAS. Package versions declared by this project are fixed in `pyproject.toml` so a clean install is reviewable.

## Run without the UI

```python
from core.pipeline import VeritasPipeline
from core.schemas import ExecutionMode

result = VeritasPipeline(
    mode=ExecutionMode.DEMO,
    run_consistency=False,
).run("The Earth orbits the Sun.")

print(result.execution_mode)  # demo
print(result.evidence_status)  # synthetic
```

## Quality gates

```bash
python -m pip install --upgrade pip==26.2.1
python -m pip install -e ".[ui,dev,security]"
ruff format --check .
ruff check .
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . --wheel-dir wheelhouse
python -m compileall -q agents audit config consistency core correction graph retrieval scoring ui
python -m pip check
python -m pip_audit --local --skip-editable --progress-spinner off
```

CI uses demo mode, mocked transports, security linting, an installed-dependency audit, official actions pinned to full commit SHAs, and no API credential.

## Limitations and prohibited use

Do not use VERITAS for:

- medical diagnosis, treatment, triage, or safety decisions;
- legal advice, legal status, guilt, liability, or rights determinations;
- election, journalistic publication, identity, employment, credit, housing, insurance, education, or access-control decisions;
- accusations about a person or organization;
- autonomous moderation, enforcement, or censorship.

Known limitations include retrieval coverage, source selection bias, stale or misleading sources, prompt injection in retrieved text, model hallucination, correlated model outputs, brittle entity extraction, heuristic thresholds, missing citation counts, external-service failures, and distribution shift. The current code processes only the first extracted claim through the full downstream pipeline.

## Repository map

```text
core/                    schemas, mock client, claim extraction, pipeline
retrieval/               Wikipedia/arXiv adapters, BM25, embeddings, RRF
agents/                  structured pro/con/adversarial outputs and judge
scoring/                 source-score heuristics
graph/                   evidence nodes and typed edges
consistency/             repeated-run aggregation experiment
correction/              model-generated correction candidate
audit/                   local trace fingerprints and persistence
ui/app.py                safe Streamlit presentation
tests/                   trust-boundary and behavior contracts
```

## Security and privacy

Read [SECURITY.md](SECURITY.md). Keep API keys in the deployment platform's encrypted secret store. Local audit files are excluded from Git, but operators must separately control filesystem permissions, backups, logs, traces, retention, and deletion.

## License

Source code is available under the [MIT License](LICENSE). External services, retrieved content, and third-party packages retain their own terms and licenses.
