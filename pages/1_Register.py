import streamlit as st
import os, time
import numpy as np
from utils.mock_backend import (
    find_matches, check_duplicate, register_animal, log_verification,
    add_fraud_flag, get_all_photo_paths, get_all_embeddings, get_embedding_for_image,
)

st.set_page_config(page_title="Register Cow", page_icon="📝", layout="wide")

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

st.title("📝 Register Cow")
st.caption("Upload at least 3 muzzle photos of the same cow for reliable enrollment")

if "reg_step" not in st.session_state:
    st.session_state.reg_step = "upload"
if "reg_paths" not in st.session_state:
    st.session_state.reg_paths = []

uploaded = st.file_uploader(
    "Upload muzzle photos (minimum 3, from different angles/lighting)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if st.session_state.reg_step == "upload":
    if uploaded:
        st.session_state.reg_paths = []
        os.makedirs("uploads", exist_ok=True)
        for i, file in enumerate(uploaded):
            path = f"uploads/reg_{int(time.time())}_{i}.jpg"
            with open(path, "wb") as f:
                f.write(file.getbuffer())
            st.session_state.reg_paths.append(path)

        st.write(f"**{len(uploaded)} photo(s) uploaded**")
        cols = st.columns(min(len(uploaded), 3))
        for i, p in enumerate(st.session_state.reg_paths):
            with cols[i % 3]:
                st.image(p, caption=f"Photo {i+1}", use_container_width=True)

        if len(uploaded) < 3:
            st.warning("⚠️ Please upload at least 3 photos for best accuracy")
        else:
            st.success("✅ 3 or more photos — ready to proceed")

        if st.button("Check & Continue", type="primary", disabled=len(uploaded) < 3):
            # 1. Duplicate check on every photo
            all_paths = get_all_photo_paths()
            for p in st.session_state.reg_paths:
                dup = check_duplicate(p, all_paths)
                if dup["is_duplicate"]:
                    st.error(f"❌ One of these photos already exists in the system")
                    add_fraud_flag(None, "duplicate_photo", f"Matched {dup['matched_photo_path']}")
                    st.stop()

            # 2. Match check on every photo
            with st.spinner("Checking against database..."):
                results = [find_matches(p) for p in st.session_state.reg_paths]

            # If any photo matches an existing cow with high confidence → already enrolled
            for r in results:
                if r["status"] == "high_confidence":
                    match = r["top_matches"][0]
                    st.error(f"⚠️ Already enrolled as Cow #{match['cow_id']} ({match['score']*100:.1f}% match)")
                    add_fraud_flag(match["cow_id"], "duplicate_registration",
                                   f"Score {match['score']:.2f}")
                    if os.path.exists(match["photo_path"]):
                        st.image(match["photo_path"], caption=f"Stored: #{match['cow_id']}", width=250)
                    st.stop()

            # 3. New cow → average the embeddings
            st.success("✅ New animal — not in database")
            st.session_state.reg_step = "details"

            existing = get_all_embeddings()
            new_points = [get_embedding_for_image(p) for p in st.session_state.reg_paths]
            avg_point = np.mean(new_points, axis=0)

            xs = [v[0] for v in existing.values()] + [p[0] for p in new_points] + [avg_point[0]]
            ys = [v[1] for v in existing.values()] + [p[1] for p in new_points] + [avg_point[1]]

            st.subheader("Embedding space (2D projection)")
            st.scatter_chart({"x": xs, "y": ys}, x="x", y="y")
            st.caption(f"Grey dots = existing animals · Blue = your 3 photos · Green = averaged identity")
            st.rerun()

# --- Step 2: Details form ---
if st.session_state.reg_step == "details":
    st.subheader("Enter animal details")
    breed = st.text_input("Breed")
    age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
    owner = st.text_input("Owner name")
    policy = st.text_input("Policy ID")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Register Animal", type="primary"):
            if not all([breed, owner, policy]):
                st.error("Please fill all fields")
            else:
                # Register with first photo as reference; log all 3
                cow_id = register_animal(breed, age, owner, policy, st.session_state.reg_paths[0])
                for p in st.session_state.reg_paths:
                    log_verification(cow_id, "register", p, None, None, "registered")
                st.success(f"✅ Registered as Cow #{cow_id} with {len(st.session_state.reg_paths)} photos")
                st.session_state.reg_step = "upload"
                st.session_state.reg_paths = []
    with col2:
        if st.button("Cancel"):
            st.session_state.reg_step = "upload"
            st.session_state.reg_paths = []
            st.rerun()