import streamlit as st
from utils.mock_backend import check_agent_login

st.set_page_config(page_title="PashuPrint", page_icon="🐄", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🐄 PashuPrint")
st.subheader("Biometric verification for livestock insurance")
st.markdown("**Muzzle Photo → AI Verification → Livestock Passport → Insurance**")

col1, col2 = st.columns(2)
with col1:
    if st.button("📝 Register Cow", use_container_width=True):
        if st.session_state.user:
            st.switch_page("pages/1_Register.py")
        else:
            st.session_state.need_login = "register"
            st.rerun()
with col2:
    if st.button("🔍 Verify Cow", use_container_width=True):
        if st.session_state.user:
            st.switch_page("pages/2_Verify.py")
        else:
            st.session_state.need_login = "verify"
            st.rerun()

if st.session_state.get("need_login"):
    st.divider()
    st.subheader("🔐 Login Required")
    agent_id = st.text_input("Agent ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        result = check_agent_login(agent_id, password)
        if result["ok"]:
            st.session_state.user = result
            target = st.session_state.need_login
            st.session_state.need_login = None
            st.switch_page(f"pages/{'1_Register' if target == 'register' else '2_Verify'}.py")
        else:
            st.error("Invalid credentials")