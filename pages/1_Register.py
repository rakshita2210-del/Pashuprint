import streamlit as st
import os, time
import numpy as np
from utils.mock_backend import (
    find_matches, check_duplicate, register_animal, log_verification,
    add_fraud_flag, get_all_photo_paths, get_all_embeddings, get_embedding_for_image,
)
from utils.ui import inject_css, hero, info_strip, warn_strip

st.set_page_config(page_title="Register Cow", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")
inject_css()

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

hero("Register Cow", "Upload at least 3 muzzle photos of the same cow for reliable enrollment", "📝")

if "reg_step" not in st.session_state:
    st.session_state.reg_step = "upload"
if "reg_paths" not in st.session_state:
    st.session_state.reg_paths = []

# --- STEP 1: UPLOAD ---
if st.session_state.reg_step == "upload":
    uploaded = st.file_uploader(
        "Drop 3+ muzzle photos here",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded:
        st.session_state.reg_paths = []
        os.makedirs("uploads", exist_ok=True)
        for i, file in enumerate(uploaded):
            path = f"uploads/reg_{int(time.time())}_{i}.jpg"
            with open(path, "wb") as f:
                f.write(file.getbuffer())
            st.session_state.reg_paths.append(path)

        n = len(uploaded)
        if n < 3:
            warn_strip(f"⚠️ {n} photo(s) uploaded — at least 3 required for reliable enrollment")
        else:
            info_strip(f"✅ {n} photos ready for enrollment")

        cols = st.columns(min(n, 4))
        for i, p in enumerate(st.session_state.reg_paths):
            with cols[i % 4]:
                st.image(p, caption=f"Photo #{i+1}", use_container_width=True)

        if n >= 3:
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            if st.button("✅  Check & Continue", type="primary", use_container_width=True):
                all_paths = get_all_photo_paths()
                for p in st.session_state.reg_paths:
                    dup = check_duplicate(p, all_paths)
                    if dup["is_duplicate"]:
                        st.error("❌ One of these photos already exists in the system")
                        add_fraud_flag(None, "duplicate_photo", f"Matched {dup['matched_photo_path']}")
                        st.stop()

                with st.spinner("Checking against database..."):
                    results = [find_matches(p) for p in st.session_state.reg_paths]

                for r in results:
                    if r["status"] == "high_confidence":
                        match = r["top_matches"][0]
                        st.error(f"⚠️ Already enrolled as Cow #{match['cow_id']} ({match['score']*100:.1f}% match)")
                        add_fraud_flag(match["cow_id"], "duplicate_registration", f"Score {match['score']:.2f}")
                        st.stop()

                st.success("✅  New animal — not in database")
                st.session_state.reg_step = "details"
                st.rerun()

# --- STEP 2: DETAILS + PLOT ---
elif st.session_state.reg_step == "details":
    st.markdown("### 🧬 Embedding generated")
    info_strip("Photos averaged into a single identity vector.")

    existing = get_all_embeddings()
    new_points = [get_embedding_for_image(p) for p in st.session_state.reg_paths]
    avg_point = np.mean(new_points, axis=0)

    xs = [v[0] for v in existing.values()] + [p[0] for p in new_points] + [avg_point[0]]
    ys = [v[1] for v in existing.values()] + [p[1] for p in new_points] + [avg_point[1]]

    st.scatter_chart({"x": xs, "y": ys}, x="x", y="y", height=320)
    st.caption(f"🟢 Existing: {len(existing)} · 🔵 Your {len(new_points)} photos · ⭐ Averaged identity")

    st.divider()
    st.markdown("### 📋 Animal details")

    with st.container(border=True):
        breed = st.text_input("Breed", placeholder="e.g. Gir, Sahiwal, Red Sindhi")
        c1, c2 = st.columns(2)
        with c1:
            age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
        with c2:
            policy = st.text_input("Policy ID", placeholder="e.g. POL-9924")
        owner = st.text_input("Owner name")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅  Register Animal", type="primary", use_container_width=True):
            if not all([breed, owner, policy]):
                st.error("Please fill all fields")
            else:
                cow_id = register_animal(breed, age, owner, policy, st.session_state.reg_paths[0])
                for p in st.session_state.reg_paths:
                    log_verification(cow_id, "register", p, None, None, "registered")
                st.balloons()
                st.success(f"✅  Registered as Cow #{cow_id}")
                st.session_state.reg_step = "upload"
                st.session_state.reg_paths = []
                time.sleep(1.5)
                st.rerun()
    with c2:
        if st.button("↩️  Cancel", use_container_width=True):
            st.session_state.reg_step = "upload"
            st.session_state.reg_paths = []
            st.rerun()
            