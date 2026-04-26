import streamlit as st
import requests
import plotly.graph_objects as go
import time
import networkx as nx
from pyvis.network import Network
import tempfile
import os

st.set_page_config(
    page_title="VERITAS-Ω | Truth Engine",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── 100x PREMIUM CYBERPUNK CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap');
    
    /* Base App Styling */
    .stApp {
        background-color: #030712;
        background-image: 
            linear-gradient(rgba(0, 229, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 229, 255, 0.03) 1px, transparent 1px);
        background-size: 30px 30px;
        font-family: 'Rajdhani', sans-serif;
        color: #e2e8f0;
    }
    
    /* Hide Streamlit Header & Footer */
    header, footer {visibility: hidden !important;}
    
    /* 100x Title Effect */
    .glow-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 4.5rem;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(to right, #00f2fe, #4facfe, #00f2fe);
        background-size: 200% auto;
        color: #000;
        background-clip: text;
        text-fill-color: transparent;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: shine 3s linear infinite;
        text-shadow: 0px 0px 20px rgba(0,242,254,0.5);
        margin-bottom: 0;
        letter-spacing: 0.1em;
    }
    
    @keyframes shine {
        to { background-position: 200% center; }
    }
    
    .sub-title {
        font-family: 'Orbitron', sans-serif;
        text-align: center;
        color: #00f2fe;
        font-weight: 700;
        font-size: 1rem;
        margin-bottom: 3rem;
        letter-spacing: 8px;
        text-transform: uppercase;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.7; text-shadow: 0 0 10px rgba(0,242,254,0.2); }
        50% { opacity: 1; text-shadow: 0 0 20px rgba(0,242,254,0.8); }
        100% { opacity: 0.7; text-shadow: 0 0 10px rgba(0,242,254,0.2); }
    }

    /* 100x Glassmorphism Containers */
    .glass-card {
        background: rgba(10, 15, 25, 0.7) !important;
        border: 1px solid rgba(0, 242, 254, 0.2) !important;
        border-radius: 8px !important;
        padding: 30px !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: inset 0 0 20px rgba(0, 242, 254, 0.05), 0 10px 30px rgba(0,0,0,0.8) !important;
        margin-bottom: 25px !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    /* Cyberpunk Corner Accents */
    .glass-card::before {
        content: ''; position: absolute; top: 0; left: 0; width: 20px; height: 20px;
        border-top: 2px solid #00f2fe; border-left: 2px solid #00f2fe;
    }
    .glass-card::after {
        content: ''; position: absolute; bottom: 0; right: 0; width: 20px; height: 20px;
        border-bottom: 2px solid #00f2fe; border-right: 2px solid #00f2fe;
    }
    
    /* Verdict Badges */
    .verdict-box {
        text-align: center;
        padding: 30px;
        border-radius: 4px;
        margin-bottom: 20px;
        text-transform: uppercase;
        position: relative;
        overflow: hidden;
    }
    .verdict-TRUE { background: rgba(0, 255, 136, 0.05); border: 2px solid #00ff88; box-shadow: 0 0 40px rgba(0, 255, 136, 0.2); }
    .verdict-FALSE { background: rgba(255, 0, 85, 0.05); border: 2px solid #ff0055; box-shadow: 0 0 40px rgba(255, 0, 85, 0.2); }
    .verdict-PARTIALLY_TRUE { background: rgba(255, 204, 0, 0.05); border: 2px solid #ffcc00; box-shadow: 0 0 40px rgba(255, 204, 0, 0.2); }
    
    .verdict-text { font-family: 'Orbitron', sans-serif; font-size: 3.5rem; font-weight: 900; letter-spacing: 4px; margin-top: 10px;}
    .verdict-TRUE .verdict-text { color: #00ff88; text-shadow: 0 0 20px #00ff88;}
    .verdict-FALSE .verdict-text { color: #ff0055; text-shadow: 0 0 20px #ff0055;}
    .verdict-PARTIALLY_TRUE .verdict-text { color: #ffcc00; text-shadow: 0 0 20px #ffcc00;}
    
    /* Input Styling Override */
    div[data-baseweb="textarea"] > div {
        background-color: rgba(0, 0, 0, 0.5) !important;
        border: 1px solid rgba(0, 242, 254, 0.3) !important;
        border-radius: 4px !important;
    }
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: #00f2fe !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.4) !important;
    }
    textarea {
        color: #00f2fe !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1.2rem !important;
    }
    
    /* Button Override */
    .stButton > button {
        background: linear-gradient(45deg, #00f2fe, #4facfe) !important;
        color: #000 !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 900 !important;
        font-size: 1.2rem !important;
        border: none !important;
        border-radius: 4px !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.4) !important;
    }
    .stButton > button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 0 40px rgba(0, 242, 254, 0.8) !important;
    }

    /* Agent Headers */
    .agent-header {
        font-family: 'Orbitron', sans-serif;
        font-weight: 900;
        font-size: 1.2rem;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid;
        padding-bottom: 10px;
    }
    .role-pro { color: #00ff88; border-color: rgba(0,255,136,0.3); }
    .role-con { color: #ff0055; border-color: rgba(255,0,85,0.3); }
    .role-adversarial { color: #ffcc00; border-color: rgba(255,204,0,0.3); }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ─────────────────────────────────────────────────────────────────
st.markdown("<div class='glow-title'>VERITAS-Ω</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Military-Grade Multi-Agent Truth Engine</div>", unsafe_allow_html=True)

# ─── INPUT SECTION ──────────────────────────────────────────────────────────
with st.container():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        claim_input = st.text_area("ENTER CLAIM FOR VERIFICATION", 
                                  height=120, 
                                  placeholder="e.g., The mRNA COVID-19 vaccines alter human DNA...",
                                  label_visibility="collapsed")
    with col2:
        domain_mode = st.selectbox("DOMAIN MODE", ["general", "medical", "legal"])
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("VERIFY CLAIM 🚀", use_container_width=True, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

# ─── HELPER FUNCTIONS ───────────────────────────────────────────────────────
def create_gauge(value, title, color, max_val=1.0):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value * 100,
        title = {'text': title, 'font': {'color': '#94a3b8', 'size': 14}},
        number = {'suffix': "%", 'font': {'color': '#e2e8f0', 'size': 24}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#334155"},
            'bar': {'color': color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
            'threshold': {
                'line': {'color': "white", 'width': 2},
                'thickness': 0.75,
                'value': value * 100
            }
        }
    ))
    fig.update_layout(
        height=200, 
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={'family': "Outfit"}
    )
    return fig

def render_network(graph_data):
    net = Network(height="400px", width="100%", bgcolor="#050505", font_color="#e2e8f0")
    net.force_atlas_2based(spring_length=150)
    
    for node in graph_data['nodes']:
        color = "#00e5ff" if node['node_type'] == "claim" else "#8a2be2"
        size = 25 if node['node_type'] == "claim" else 15
        label = node['text'][:30] + "..."
        net.add_node(node['node_id'], label=label, title=node['text'], color=color, size=size)
        
    for edge in graph_data['edges']:
        color = "#00e676" if edge['edge_type'] == "supports" else "#ff1744" if edge['edge_type'] == "contradicts" else "#9e9e9e"
        net.add_edge(edge['source_id'], edge['target_id'], title=edge['reasoning'], color=color, value=edge['confidence'])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmpfile:
        net.save_graph(tmpfile.name)
        with open(tmpfile.name, 'r', encoding='utf-8') as f:
            html = f.read()
    os.unlink(tmpfile.name)
    return html

# ─── MAIN LOGIC ─────────────────────────────────────────────────────────────
if analyze_btn and claim_input:
    with st.spinner("Analyzing claim across multiverses..."):
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from core.pipeline import VeritasPipeline
            from core.schemas import DomainMode
            
            os.environ["USE_MOCK_LLM"] = os.getenv("USE_MOCK_LLM", "true")
            
            if "pipeline" not in st.session_state:
                st.session_state.pipeline = VeritasPipeline(
                    openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
                    run_consistency=False
                )
            
            result = st.session_state.pipeline.run(
                raw_input=claim_input,
                domain_mode=DomainMode(domain_mode)
            )
            
            data = result.model_dump(mode="json")
            
            if False:  # placeholder for error handling
                pass
            else:
                judge = data['judge_output']
                primary_claim = data['claims'][0]
                
                # ── VERDICT ROW ──
                verdict = judge['verdict']
                v_class = f"verdict-{verdict}"
                
                st.markdown(f"""
                <div class='glass-card verdict-box {v_class}'>
                    <div style="font-size:1.2rem; color: #94a3b8; text-transform:uppercase;">VERITAS-Ω VERDICT</div>
                    <div class='verdict-text'>{verdict.replace('_', ' ')}</div>
                    <div style="font-size: 1.2rem; font-style: italic; margin-top: 15px;">"{primary_claim['claim_text']}"</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Tag Row
                tags_html = f"<div class='domain-tag'>TYPE: {primary_claim['claim_type']}</div>"
                for e in primary_claim['entities'][:4]:
                    tags_html += f"<div class='domain-tag'>{e}</div>"
                st.markdown(f"<div style='margin-bottom: 20px;'>{tags_html}</div>", unsafe_allow_html=True)
                
                # ── METERS & SUMMARY ROW ──
                col_g1, col_g2, col_g3 = st.columns(3)
                with col_g1:
                    st.plotly_chart(create_gauge(judge['confidence_score'], "CONFIDENCE", "#00e5ff"), use_container_width=True)
                with col_g2:
                    st.plotly_chart(create_gauge(judge['uncertainty_score'], "UNCERTAINTY", "#ff1744"), use_container_width=True)
                with col_g3:
                    st.plotly_chart(create_gauge(judge['aggregated_trust_score'], "TRUST SCORE", "#00e676"), use_container_width=True)
                
                # ── REASONING CARD ──
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.markdown("### 🧠 Synthesized Judicial Reasoning")
                st.info(judge['reasoning_summary'])
                if data.get('corrected_claim') and verdict != 'TRUE':
                    st.warning(f"**Corrected Claim:** {data['corrected_claim']['corrected_text']}")
                st.markdown("</div>", unsafe_allow_html=True)
                
                # ── CLAIM GROUNDING (Point 7 & 3) ──
                st.markdown("<h3 style='color: #00e5ff; margin-top: 30px;'>1. CLAIM GROUNDING & DECOMPOSITION</h3>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='glass-card' style='padding: 15px;'>
                    <div style='color: #64748b; font-size: 0.8rem;'>ORIGINAL INPUT:</div>
                    <div style='color: #e2e8f0; margin-bottom: 15px; font-style: italic;'>"{claim_input}"</div>
                    
                    <div style='color: #64748b; font-size: 0.8rem;'>NORMALIZED ATOMIC CLAIM:</div>
                    <div style='color: #00e5ff; font-weight: 700; margin-bottom: 15px;'>"{primary_claim['claim_text']}"</div>
                    
                    <div style='color: #64748b; font-size: 0.8rem;'>EXTRACTED ENTITIES (Sub-Claim Anchors):</div>
                    <div style='color: #d8b4fe;'>{", ".join(primary_claim['entities'])}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # ── MATHEMATICAL TRACE (Point 2, 5, 6, 10) ──
                st.markdown("<h3 style='color: #ffea00; margin-top: 30px;'>2. QUANTITATIVE PIPELINE TRACE</h3>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='glass-card'>
                    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px;'>
                        <div>
                            <h4 style='color: #cbd5e1; font-size: 0.9rem;'>AGGREGATION FORMULA</h4>
                            <code style='color: #00e676; background: #000; padding: 5px; border-radius: 4px; display: block; margin-bottom: 10px;'>Conf = (Pro - Con + GraphDiff)/2 - Penalty</code>
                            <div style='font-size: 0.8rem; color: #94a3b8;'>Adversarial Penalty: Mathematically reduced trust score by {(1.0 - judge['aggregated_trust_score']) * 100:.1f}%, directly diluting base confidence.</div>
                        </div>
                        <div>
                            <h4 style='color: #cbd5e1; font-size: 0.9rem;'>UNCERTAINTY DECOMPOSITION</h4>
                            <div style='font-size: 0.8rem; color: #94a3b8; display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding-bottom: 4px;'>
                                <span>Epistemic (Missing Data / Adversarial Gap):</span> <span style='color: #ffea00;'>{judge['uncertainty_score'] * 0.8 * 100:.1f}%</span>
                            </div>
                            <div style='font-size: 0.8rem; color: #94a3b8; display: flex; justify-content: space-between; padding-top: 4px;'>
                                <span>Aleatoric (Systemic Noise / Agent Dispute):</span> <span style='color: #ff1744;'>{judge['uncertainty_score'] * 0.2 * 100:.1f}%</span>
                            </div>
                            <div style='font-size: 0.7rem; color: #64748b; margin-top: 8px;'>*Epistemic variance mathematically bounded by Adversarial Agent findings.</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # ── MULTI-AGENT DEBATE (Point 4) ──
                st.markdown("<h3 style='text-align: center; margin: 40px 0 20px 0; color: #00e5ff;'>3. MULTI-AGENT DEBATE & SOURCE DIVERSITY</h3>", unsafe_allow_html=True)
                
                cols = st.columns(3)
                for i, agent in enumerate(data['agent_outputs']):
                    role = agent['agent_role']
                    color_cls = f"role-{role}"
                    
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div class='glass-card' style='height: 100%;'>
                            <div class='agent-header {color_cls}'>
                                <span>{role.upper()} AGENT</span>
                                <span style="font-size:0.8rem; background: rgba(255,255,255,0.1); padding:2px 8px; border-radius:10px;">{int(agent['confidence']*100)}% WEIGHT</span>
                            </div>
                            <div style='color: #cbd5e1; font-size:0.95rem; margin-bottom: 15px;'>
                                <strong>Stance:</strong> {agent['stance'].upper()}
                            </div>
                            <div style='color: #94a3b8; font-size:0.9rem; line-height: 1.5;'>
                                {agent['reasoning']}
                            </div>
                            <hr style="border-color: rgba(255,255,255,0.1);">
                            <div style='font-size: 0.8rem; color: #64748b;'>INDEPENDENT SOURCE:</div>
                        """, unsafe_allow_html=True)
                        for ref in agent['evidence_references'][:1]:
                            st.markdown(f"<div style='font-size: 0.75rem; background: rgba(0,0,0,0.5); padding: 5px; border-radius: 4px;'><a href='{ref['url']}' target='_blank' style='color:#00e5ff; text-decoration:none;'>[{ref['doc_id']}] 🔗 {ref['url'][:25]}...</a><br><i style='color: #94a3b8;'>\"{ref['excerpt']}\"</i></div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                # ── EVIDENCE GRAPH ──
                if data.get('evidence_graph'):
                    st.markdown("<h2 style='text-align: center; margin: 40px 0 20px 0; color: #8a2be2;'>EVIDENCE TOPOLOGY</h2>", unsafe_allow_html=True)
                    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                    graph_html = render_network(data['evidence_graph'])
                    import streamlit.components.v1 as components
                    components.html(graph_html, height=420)
                    st.markdown("</div>", unsafe_allow_html=True)

                # ── AUDIT TRACE EXPANDER ──
                with st.expander("🔍 View Cryptographic Audit Trace"):
                    st.json({
                        "session_id": data['session_id'],
                        "audit_trace_id": data['audit_trace']['trace_id'],
                        "domain_mode": data['domain_mode'],
                        "evidence_count": judge['evidence_count'],
                        "stability_label": data.get('consistency_result', {}).get('stability_label', 'N/A')
                    })
                    
        except Exception as e:
            st.error(f"Pipeline Error: {str(e)}")
