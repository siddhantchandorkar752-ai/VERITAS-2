"""Streamlit interface for the VERITAS evidence-aggregation research prototype."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.pipeline import VeritasPipeline  # noqa: E402
from core.schemas import DomainMode, ExecutionMode  # noqa: E402

logger = logging.getLogger("veritas.ui")

st.set_page_config(
    page_title="VERITAS research workbench",
    page_icon="🔎",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background: #071018; color: #e2e8f0; }
    .veritas-card {
        background: #0f1d2a;
        border: 1px solid #25445d;
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .veritas-kicker { color: #67e8f9; font-weight: 700; letter-spacing: .08em; }
    </style>
    """,
    unsafe_allow_html=True,
)


def network_figure(graph_data: dict) -> go.Figure:
    """Render an evidence graph without injecting graph text into raw HTML."""

    graph = nx.DiGraph()
    node_map = {node["node_id"]: node for node in graph_data.get("nodes", [])}
    graph.add_nodes_from(node_map)
    for edge in graph_data.get("edges", []):
        graph.add_edge(edge["source_id"], edge["target_id"])

    positions = nx.spring_layout(graph, seed=42) if graph.nodes else {}
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for source, target in graph.edges:
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_x.extend((float(x0), float(x1), None))
        edge_y.extend((float(y0), float(y1), None))

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line={"width": 1, "color": "#64748b"},
        hoverinfo="skip",
    )

    node_ids = list(graph.nodes)
    node_trace = go.Scatter(
        x=[float(positions[node][0]) for node in node_ids],
        y=[float(positions[node][1]) for node in node_ids],
        mode="markers",
        marker={
            "size": [22 if node_map[node]["node_type"] == "claim" else 14 for node in node_ids],
            "color": [
                "#22d3ee" if node_map[node]["node_type"] == "claim" else "#a78bfa"
                for node in node_ids
            ],
            "line": {"width": 1, "color": "#e2e8f0"},
        },
        text=[node_map[node]["text"][:240] for node in node_ids],
        hovertemplate="%{text}<extra></extra>",
    )

    figure = go.Figure(data=[edge_trace, node_trace])
    figure.update_layout(
        showlegend=False,
        paper_bgcolor="#0f1d2a",
        plot_bgcolor="#0f1d2a",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        xaxis={"visible": False},
        yaxis={"visible": False},
        height=420,
    )
    return figure


def configured_mode() -> ExecutionMode:
    raw_mode = os.getenv("VERITAS_MODE", ExecutionMode.DEMO.value).lower()
    try:
        return ExecutionMode(raw_mode)
    except ValueError:
        st.error("VERITAS_MODE must be either 'demo' or 'live'.")
        st.stop()


def pipeline_for(mode: ExecutionMode) -> VeritasPipeline:
    cache_key = f"pipeline_{mode.value}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = VeritasPipeline(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            run_consistency=False,
            mode=mode,
        )
    return st.session_state[cache_key]


st.markdown(
    '<div class="veritas-kicker">EVIDENCE-AGGREGATION RESEARCH PROTOTYPE</div>',
    unsafe_allow_html=True,
)
st.title("VERITAS research workbench")
st.write(
    "Explore claim decomposition, retrieval, structured agent outputs, scoring, "
    "and trace fingerprints. The system does not establish truth and must not be "
    "used for medical, legal, journalistic, election, employment, identity, or "
    "access-control decisions."
)

mode = configured_mode()
if mode == ExecutionMode.DEMO:
    st.warning(
        "DEMO MODE — all evidence and model responses are deterministic synthetic "
        "fixtures. No network request or real fact verification is performed."
    )
else:
    st.info(
        "LIVE RESEARCH MODE — external retrieval and model APIs are enabled. Outputs "
        "remain experimental evidence-aggregation results, not factual determinations."
    )
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is required for live mode.")
        st.stop()

with st.sidebar:
    st.header("Run configuration")
    st.text_input("Execution mode", value=mode.value, disabled=True)
    st.text_input("Domain", value="general research only", disabled=True)
    st.caption("Medical and legal verdict modes are intentionally disabled in the UI.")
    st.divider()
    st.caption(
        "Submitted text may be sent to Wikipedia, arXiv, and the configured model "
        "provider only in live mode. Review those providers' retention policies."
    )

claim_input = st.text_area(
    "Claim or short passage",
    placeholder="Enter a claim to inspect the pipeline…",
    height=130,
    max_chars=4000,
)
analyze = st.button("Run research pipeline", type="primary", width="stretch")

if analyze:
    if not claim_input.strip():
        st.warning("Enter a claim before running the pipeline.")
        st.stop()

    try:
        with st.spinner("Running the evidence pipeline…"):
            result = pipeline_for(mode).run(
                raw_input=claim_input,
                domain_mode=DomainMode.GENERAL,
            )
    except Exception:
        logger.exception("Pipeline execution failed")
        st.error("The pipeline failed. Review the server logs for diagnostic details.")
        st.stop()

    data = result.model_dump(mode="json")
    judge = data["judge_output"]
    primary_claim = data["claims"][0]
    simulated = data["evidence_status"] == "synthetic"

    st.divider()
    st.subheader("Simulated aggregation output" if simulated else "Evidence aggregation output")
    if simulated:
        st.warning(
            "SYNTHETIC RESULT — do not interpret the label or scores as evidence about the claim."
        )

    columns = st.columns(4)
    columns[0].metric("Algorithm label", judge["verdict"].replace("_", " "))
    columns[1].metric("Aggregation score", f"{judge['confidence_score']:.3f}")
    columns[2].metric("Uncertainty heuristic", f"{judge['uncertainty_score']:.3f}")
    columns[3].metric("Source heuristic", f"{judge['aggregated_trust_score']:.3f}")

    st.markdown("### Claim decomposition")
    st.write("Submitted input:", claim_input)
    st.write("Primary normalized claim:", primary_claim["claim_text"])
    st.write("Entities:", primary_claim["entities"] or "None extracted")

    st.markdown("### Reasoning summary")
    st.info(judge["reasoning_summary"])
    if data.get("corrected_claim"):
        st.write("Correction candidate:", data["corrected_claim"]["corrected_text"])
        st.caption("Correction text is model-generated and is not independently verified.")

    st.markdown("### Retrieved evidence")
    documents = data["retrieval_results"][0]["documents"]
    st.dataframe(
        [
            {
                "title": document["title"],
                "domain": document["source_domain"],
                "url": document["url"],
                "trust heuristic": document["trust_score"],
                "synthetic": simulated,
            }
            for document in documents
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown("### Structured agent panel")
    for agent in data["agent_outputs"]:
        with st.expander(f"{agent['agent_role'].title()} — {agent['stance']}"):
            st.write(agent["reasoning"])
            st.write("Key points:", agent["key_points"])
            st.write("Cited document IDs:", [ref["doc_id"] for ref in agent["evidence_references"]])

    if data.get("evidence_graph"):
        st.markdown("### Evidence topology")
        st.plotly_chart(
            network_figure(data["evidence_graph"]),
            width="stretch",
        )

    with st.expander("Trace fingerprints"):
        st.caption(
            "These SHA-256 values detect accidental changes in serialized step inputs/outputs. "
            "They are not a signature, immutable ledger, replay artifact, or proof of correctness."
        )
        st.json(
            {
                "trace_id": data["audit_trace"]["trace_id"],
                "session_id": data["session_id"],
                "execution_mode": data["execution_mode"],
                "steps": data["audit_trace"]["steps"],
            }
        )
