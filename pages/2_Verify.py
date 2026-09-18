import streamlit as st
import os, time
from utils.mock_backend import find_matches_multi, log_verification, add_fraud_flag
from utils.ui import inject_css, hero, verdict_banner, match_card, info_strip, warn_strip

st.set_page_config(page_title="Verify Cow", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")
inject_css()

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

hero("Verify Cow", "Upload 3 muzzle photos of the same cow to verify identity", "🔍")

c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("#### 📸 Upload (minimum 3 photos)")
    uploaded = st.file_uploader(
        "Drop 3+ muzzle photos of the same cow",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded:
        os.makedirs("uploads", exist_ok=True)
        paths = []
        for i, file in enumerate(uploaded):
            p = f"uploads/claim_{int(time.time())}_{i}.jpg"
            with open(p, "wb") as f:
                f.write(file.getbuffer())
            paths.append(p)
        st.session_state.verify_paths = paths

        n = len(paths)
        if n < 3:
            warn_strip(f"⚠️ {n} photo(s) uploaded — at least 3 required")
        else:
            info_strip(f"✅ {n} photos ready — will be averaged into one identity")

        cols = st.columns(min(n, 4))
        for i, p in enumerate(paths):
            with cols[i % 4]:
                st.image(p, caption=f"#{i+1}", use_container_width=True)

with c2:
    st.markdown("#### 🎯 Result")
    if "verify_paths" not in st.session_state:
        info_strip("Upload 3 muzzle photos on the left to begin verification.")
    else:
        n = len(st.session_state.verify_paths)
        if n < 3:
            warn_strip("Need at least 3 photos before verifying.")
        else:
            if st.button("🚀  Verify Now", type="primary", use_container_width=True):
                with st.spinner("Analyzing muzzle patterns..."):
                    result = find_matches_multi(st.session_state.verify_paths, top_k=3)
                st.session_state.verify_result = result

            if "verify_result" in st.session_state:
                result = st.session_state.verify_result
                status = result["status"]

                if status == "high_confidence":
                    m = result["top_matches"][0]
                    verdict_banner(status, m["cow_id"], m["score"])
                    log_verification(m["cow_id"], "claim", st.session_state.verify_paths[0], m["cow_id"], m["score"], "high_confidence")
                elif status == "low_confidence":
                    verdict_banner(status)
                    m = result["top_matches"][0]
                    log_verification(m["cow_id"], "claim", st.session_state.verify_paths[0], m["cow_id"], m["score"], "low_confidence")
                    add_fraud_flag(m["cow_id"], "low_confidence_claim", f"Score {m['score']:.2f}")
                elif status == "no_match":
                    verdict_banner(status)
                    log_verification(None, "claim", st.session_state.verify_paths[0], None, None, "no_match")
                    add_fraud_flag(None, "no_match_claim", "No match above threshold")
                else:
                    verdict_banner(status)
                    log_verification(None, "claim", st.session_state.verify_paths[0], None, None, "unusable")
                    add_fraud_flag(None, "unusable_claim_image", "All photos were unusable")

if "verify_result" in st.session_state and st.session_state.verify_result["top_matches"]:
    st.markdown("### 🏆 Top 3 Matches")
    cols = st.columns(3)
    for i, m in enumerate(st.session_state.verify_result["top_matches"]):
        with cols[i]:
            img = m["photo_path"] if os.path.exists(m["photo_path"]) else None
            match_card(m["cow_id"], m["score"], image_path=img, rank=i+1)

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    if st.button("🔄  Verify Another"):
        st.session_state.pop("verify_result", None)
        st.session_state.pop("verify_paths", None)
        st.rerun()
        