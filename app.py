import streamlit as st

from utils.ui import setup_page, html, section, stat_grid, login_card

setup_page("Home", "🐄", "home", require_auth=False)

PAGE_MAP = {
    "register": "pages/1_Register.py",
    "verify": "pages/2_Verify.py",
    "passport": "pages/4_Passport.py",
    "fraud": "pages/5_Fraud.py",
}

# --- HERO ---
html("""
<div class="hero">
  <div class="hero-inner">
    <div class="eyebrow">Livestock insurance · Identity assurance</div>
    <h1>Pashu<span class="accent">Print</span></h1>
    <p>Biometric verification for livestock insurance — identifying every cow by its unique muzzle print.</p>
    <div class="flow">
      <span class="flow-chip">📸 Muzzle Photo</span>
      <span class="flow-chip">🧠 AI Verification</span>
      <span class="flow-chip">🪪 Livestock Passport</span>
      <span class="flow-chip">🛡️ Insurance</span>
    </div>
  </div>
</div>
""")

# --- STATS (real, measured figures only) ---
stat_grid([
    {"value": "243", "label": "Cows in benchmark"},
    {"value": "86.41%", "label": "Accuracy", "note": "on benchmark dataset"},
    {"value": "&lt; 3s", "label": "Verification"},
    {"value": "24/7", "label": "Audit trail"},
], cols=4)

# --- CTA buttons ---
c1, c2, c3, c4 = st.columns(4)
button_specs = [
    (c1, "📝  Register Cow", "register", "primary"),
    (c2, "🔍  Verify Cow", "verify", "primary"),
    (c3, "🪪  Livestock Passport", "passport", "secondary"),
    (c4, "📊  Fraud Dashboard", "fraud", "secondary"),
]
for col, label, target, kind in button_specs:
    with col:
        if st.button(label, use_container_width=True, type=kind, key=f"cta_{target}"):
            if st.session_state.user:
                st.switch_page(PAGE_MAP[target])
            else:
                st.session_state.need_login = target
                st.rerun()

# --- Login (shown right under the buttons when a signed-out visitor clicks one) ---
if st.session_state.get("need_login") and not st.session_state.user:
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    login_card(target=PAGE_MAP.get(st.session_state.need_login))

# --- Features ---
section("Why PashuPrint", "Three layers of protection manual verification can't match.")
html("""
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
""")

# --- AI Model ---
section("AI Model", "The trained muzzle-recognition model behind Register and Verify.")
stat_grid([
    {"value": "ResNet50", "label": "Model", "tone": "dark"},
    {"value": "320 × 320", "label": "Input size", "tone": "dark"},
    {"value": "512", "label": "Embedding dimension", "tone": "dark"},
    {"value": "0.952", "label": "High-confidence threshold", "note": "At or above: automatic match", "tone": "dark"},
    {"value": "0.925", "label": "Low-confidence threshold", "note": "At or above: manual review", "tone": "dark"},
], cols=5)
