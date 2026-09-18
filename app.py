import streamlit as st

st.set_page_config(
    page_title="PashuPrint",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 2rem !important; max-width: 1200px !important;}
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #0f172a;
}

.hero {
    background: linear-gradient(135deg, #022c22 0%, #064e3b 45%, #10b981 100%);
    border-radius: 24px;
    padding: 3.5rem 3rem;
    color: white;
    position: relative;
    overflow: hidden;
    margin-bottom: 2rem;
}
.hero::before {
    content:"";
    position:absolute;
    top:-150px; right:-120px;
    width:450px; height:450px;
    background: radial-gradient(circle, rgba(52,211,153,0.55) 0%, transparent 65%);
    border-radius: 50%;
    filter: blur(30px);
}
.hero-inner {position: relative; z-index: 1;}
.hero h1 {
    font-size: 3.2rem;
    font-weight: 900;
    color: white;
    letter-spacing: -0.03em;
    margin: 0 0 0.75rem 0;
    line-height: 1.05;
}
.hero .accent {
    background: linear-gradient(120deg, #6ee7b7 0%, #34d399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero p {
    color: #d1fae5;
    font-size: 1.1rem;
    max-width: 640px;
    line-height: 1.6;
    margin: 0;
}
.flow {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 1.75rem;
}
.flow-chip {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.18);
    padding: 0.4rem 0.9rem;
    border-radius: 10px;
    font-size: 0.9rem;
    color: #ecfdf5;
    font-weight: 500;
}

.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-top: 2rem;
}
.stat {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.25rem;
    text-align: center;
    transition: all 0.2s ease;
}
.stat:hover {
    transform: translateY(-3px);
    border-color: #10b981;
    box-shadow: 0 12px 28px rgba(16,185,129,0.12);
}
.stat-value {
    font-size: 1.9rem;
    font-weight: 800;
    color: #064e3b;
    line-height: 1;
    letter-spacing: -0.03em;
}
.stat-label {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.45rem;
}
.stat-note {
    font-size: 0.7rem;
    color: #94a3b8;
    margin-top: 0.25rem;
}

.section-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #022c22;
    margin: 2.5rem 0 0.5rem 0;
    letter-spacing: -0.02em;
}
.section-sub {
    color: #64748b;
    font-size: 0.95rem;
    margin: 0 0 1.5rem 0;
}

.features {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
}
.feature {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    padding: 1.75rem;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.feature::before {
    content:"";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #10b981, #34d399);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform 0.3s;
}
.feature:hover::before {transform: scaleX(1);}
.feature:hover {
    transform: translateY(-5px);
    border-color: #10b981;
    box-shadow: 0 20px 40px rgba(16,185,129,0.12);
}
.feature-icon {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem;
    margin-bottom: 1rem;
}
.feature-title {
    font-weight: 700;
    font-size: 1.05rem;
    color: #022c22;
    margin: 0 0 0.4rem 0;
}
.feature-text {
    color: #64748b;
    font-size: 0.9rem;
    line-height: 1.55;
    margin: 0;
}

.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    padding: 0.55rem 1.1rem;
    border: 1px solid #e2e8f0;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    border: none;
    color: white;
    box-shadow: 0 4px 14px rgba(16,185,129,0.3);
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(16,185,129,0.4);
}
</style>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None

PAGE_MAP = {
    "register": "pages/1_Register.py",
    "verify": "pages/2_Verify.py",
    "passport": "pages/4_Passport.py",
    "fraud": "pages/5_Fraud.py",
}

# --- HERO ---
st.markdown("""
<div class="hero">
  <div class="hero-inner">
    <h1>🐄 Pashu<span class="accent">Print</span></h1>
    <p>Biometric verification for livestock insurance — identifying every cow by its unique muzzle print.</p>
    <div class="flow">
      <span class="flow-chip">📸 Muzzle Photo</span>
      <span class="flow-chip">🧠 AI Verification</span>
      <span class="flow-chip">🪪 Livestock Passport</span>
      <span class="flow-chip">🛡️ Insurance</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# --- STATS ---
st.markdown("""
<div class="stats">
  <div class="stat"><div class="stat-value">243</div><div class="stat-label">Cows</div></div>
  <div class="stat"><div class="stat-value">87.96%</div><div class="stat-label">Best Val Accuracy</div><div class="stat-note">on 243-cow benchmark</div></div>
  <div class="stat"><div class="stat-value">&lt; 3s</div><div class="stat-label">Verification</div></div>
  <div class="stat"><div class="stat-value">24/7</div><div class="stat-label">Audit Trail</div></div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

# --- CTA buttons ---
if st.session_state.user:
    st.success(f"👋 Logged in as **{st.session_state.user['name']}** ({st.session_state.user['role']})")

c1, c2, c3, c4 = st.columns(4)
button_specs = [
    (c1, "📝  Register Cow", "register", "primary"),
    (c2, "🔍  Verify Cow", "verify", "primary"),
    (c3, "🪪  Livestock Passport", "passport", "secondary"),
    (c4, "📊  Fraud Dashboard", "fraud", "secondary"),
]
for col, label, target, kind in button_specs:
    with col:
        if st.button(label, use_container_width=True, type=kind):
            if st.session_state.user:
                st.switch_page(PAGE_MAP[target])
            else:
                st.session_state.need_login = target
                st.rerun()

# --- Features ---
st.markdown("""
<div class="section-title">Why PashuPrint</div>
<div class="section-sub">Three layers of protection manual verification can't match.</div>
<div class="features">
  <div class="feature">
    <div class="feature-icon">🎯</div>
    <div class="feature-title">Unique Identity</div>
    <p class="feature-text">Every cow's muzzle print is unique — like a human fingerprint. No two are the same.</p>
  </div>
  <div class="feature">
    <div class="feature-icon">🚫</div>
    <div class="feature-title">Fraud Detection</div>
    <p class="feature-text">Catches duplicate registrations, animal swaps, and reused photos automatically.</p>
  </div>
  <div class="feature">
    <div class="feature-icon">📊</div>
    <div class="feature-title">Audit Trail</div>
    <p class="feature-text">Every verification logged, timestamped, and traceable for the insurer.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# --- AI Model ---
st.markdown("""
<div class="section-title">🧠 AI Model</div>
<div class="section-sub">Performance of the trained muzzle-recognition model used by Verify and Register.</div>
<div class="stats">
  <div class="stat"><div class="stat-value">ResNet50</div><div class="stat-label">Model</div></div>
  <div class="stat"><div class="stat-value">320 × 320</div><div class="stat-label">Input Size</div></div>
  <div class="stat"><div class="stat-value">512</div><div class="stat-label">Embedding Dimension</div></div>
  <div class="stat"><div class="stat-value">87.96%</div><div class="stat-label">Best Validation Accuracy</div></div>
  <div class="stat"><div class="stat-value">86.41%</div><div class="stat-label">Test Classification Accuracy</div><div class="stat-note">Model evaluation metric — not a real-world verification accuracy</div></div>
  <div class="stat"><div class="stat-value">0.952</div><div class="stat-label">High Confidence Threshold</div></div>
  <div class="stat"><div class="stat-value">0.925</div><div class="stat-label">Low Confidence Threshold</div></div>
</div>
""", unsafe_allow_html=True)

# --- Login ---
if st.session_state.get("need_login"):
    st.markdown("<hr style='margin:2rem 0;border:none;border-top:1px solid #e2e8f0;'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.container(border=True):
            st.markdown("### 🔐 Agent Login")
            agent_id = st.text_input("Agent ID", placeholder="vet01")
            password = st.text_input("Password", type="password", placeholder="test")
            if st.button("Login", type="primary", use_container_width=True):
                from utils.mock_backend import check_agent_login
                result = check_agent_login(agent_id, password)
                if result["ok"]:
                    st.session_state.user = result
                    target = st.session_state.need_login
                    st.session_state.need_login = None
                    st.switch_page(PAGE_MAP[target])
                else:
                    st.error("Invalid credentials")
                    