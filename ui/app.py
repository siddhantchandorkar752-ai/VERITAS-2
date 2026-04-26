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

# ─── PREMIUM CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Premium Typography & Background */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    .stApp {
        background-color: #050505;
        background-image: 
            radial-gradient(circle at 10% 20%, rgba(0, 229, 255, 0.05) 0%, transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(138, 43, 226, 0.05) 0%, transparent 40%);
        font-family: 'Outfit', sans-serif;
        color: #e2e8f0;
    }
    
    h1, h2, h3 { font-family: 'Outfit', sans-serif; }
    
    /* Title glowing effect */
    .glow-title {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #00e5ff, #8a2be2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 30px rgba(0, 229, 255, 0.3);
        margin-bottom: 0.2rem;
        letter-spacing: 2px;
    }
    .sub-title {
        text-align: center;
        color: #94a3b8;
        font-weight: 300;
        font-size: 1.2rem;
        margin-bottom: 3rem;
        letter-spacing: 5px;
        text-transform: uppercase;
    }

    /* Glassmorphism containers */
    .glass-card {
        background: rgba(20, 25, 35, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(0, 229, 255, 0.1);
        border-color: rgba(0, 229, 255, 0.2);
    }
    
    /* Verdict Badges */
    .verdict-box {
        text-align: center;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .verdict-TRUE { background: rgba(0, 230, 118, 0.1); border: 1px solid #00e676; box-shadow: 0 0 20px rgba(0, 230, 118, 0.2); }
    .verdict-FALSE { background: rgba(255, 23, 68, 0.1); border: 1px solid #ff1744; box-shadow: 0 0 20px rgba(255, 23, 68, 0.2); }
    .verdict-PARTIALLY_TRUE { background: rgba(255, 234, 0, 0.1); border: 1px solid #ffea00; box-shadow: 0 0 20px rgba(255, 234, 0, 0.2); }
    .verdict-UNCERTAIN { background: rgba(158, 158, 158, 0.1); border: 1px solid #9e9e9e; }
    
    .verdict-text { font-size: 2.5rem; font-weight: 800; letter-spacing: 2px; }
    .verdict-TRUE .verdict-text { color: #00e676; }
    .verdict-FALSE .verdict-text { color: #ff1744; }
    .verdict-PARTIALLY_TRUE .verdict-text { color: #ffea00; }
    .verdict-UNCERTAIN .verdict-text { color: #9e9e9e; }
    
    /* Tag styling */
    .domain-tag {
        display: inline-block;
        background: rgba(138, 43, 226, 0.2);
        color: #d8b4fe;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(138, 43, 226, 0.5);
        margin-right: 8px;
    }
    
    /* Agent outputs styling */
    .agent-header {
        font-weight: 800;
        font-size: 1.1rem;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 8px;
    }
    .role-pro { color: #00e5ff; }
    .role-con { color: #ff1744; }
    .role-adversarial { color: #ffea00; }
    
    /* Smooth Inputs */
    div[data-baseweb="textarea"] > div {
        background-color: rgba(20, 25, 35, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
    }
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: #00e5ff;
        box-shadow: 0 0 15px rgba(0, 229, 255, 0.2);
    }
    
    /* Streamlit overrides */
    header {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─── HEADER ─────────────────────────────────────────────────────────────────
st.markdown("<div class='glow-title'>VERITAS-Ω</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>AUDITABLE MULTI-AGENT TRUTH ENGINE</div>", unsafe_allow_html=True)

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
                
                # ── MULTI-AGENT DEBATE ──
                st.markdown("<h2 style='text-align: center; margin: 40px 0 20px 0; color: #00e5ff;'>MULTI-AGENT DEBATE</h2>", unsafe_allow_html=True)
                
                cols = st.columns(3)
                for i, agent in enumerate(data['agent_outputs']):
                    role = agent['agent_role']
                    color_cls = f"role-{role}"
                    
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div class='glass-card' style='height: 100%;'>
                            <div class='agent-header {color_cls}'>
                                <span>{role.upper()} AGENT</span>
                                <span style="font-size:0.8rem; background: rgba(255,255,255,0.1); padding:2px 8px; border-radius:10px;">{int(agent['confidence']*100)}% CONF</span>
                            </div>
                            <div style='color: #cbd5e1; font-size:0.95rem; margin-bottom: 15px;'>
                                <strong>Stance:</strong> {agent['stance'].upper()}
                            </div>
                            <div style='color: #94a3b8; font-size:0.9rem; line-height: 1.5;'>
                                {agent['reasoning']}
                            </div>
                            <hr style="border-color: rgba(255,255,255,0.1);">
                            <div style='font-size: 0.8rem; color: #64748b;'>EVIDENCE SOURCES:</div>
                        """, unsafe_allow_html=True)
                        for ref in agent['evidence_references'][:2]:
                            st.markdown(f"<div style='font-size: 0.75rem;'><a href='{ref['url']}' target='_blank' style='color:#00e5ff; text-decoration:none;'>🔗 {ref['url'][:35]}...</a></div>", unsafe_allow_html=True)
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
