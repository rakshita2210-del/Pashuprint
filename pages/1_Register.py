import streamlit as st
import os, time
import sqlite3
import numpy as np

from backend import db
from backend.dup_check import check_duplicate
from cattle_gate import assess_cattle_likeness
from matching import find_matches, embed_query_average
from utils.mock_backend import get_all_embeddings, get_embedding_for_image
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
                # --- Cattle/muzzle DOMAIN gate -- runs before anything else.
                # An image that fails this can never reach check_duplicate(),
                # embed_image(), or find_matches(); registration is refused
                # outright and no id is generated. ---
                for p in st.session_state.reg_paths:
                    gate = assess_cattle_likeness(p)
                    if not gate["is_cattle_like"]:
                        st.error("❌ INVALID IMAGE — Please upload a clear cattle muzzle photo")
                        if gate["reason"]:
                            st.caption(gate["reason"])
                        st.stop()

                # --- Exact/near-identical PHOTO re-upload check (perceptual hash,
                # NOT biometric -- backend/dup_check.py) ---
                all_paths = db.get_all_photo_paths()
                for p in st.session_state.reg_paths:
                    dup = check_duplicate(p, all_paths)
                    if dup["is_duplicate"]:
                        st.error("❌ This exact photo already exists in the system")
                        db.add_fraud_flag("UNKNOWN", "duplicate_photo", f"Matched {dup['matched_photo_path']}")
                        st.stop()

                # --- REAL muzzle-identity check against the trained ResNet50
                # gallery (matching.find_matches) -- NOT mock ML. This is the
                # actual registration decision. ---
                with st.spinner("Checking against database..."):
                    results = []
                    for p in st.session_state.reg_paths:
                        try:
                            results.append(find_matches(p))
                        except ValueError:
                            # Unreadable file -- treat the same as a blurry/unusable photo.
                            results.append({"status": "unusable", "top_matches": [], "quality_ok": False})

                # Blurry/unusable photo -> reject, let the agent retake.
                for r in results:
                    if r["status"] == "unusable":
                        warn_strip("📷 Photo too blurry — please retake")
                        st.stop()

                # Already-enrolled cow -> block registration, show proof, flag it.
                #
                # matching.find_matches() searches the ML REFERENCE gallery
                # (data/embeddings.npy / embeddings_meta.csv), which is keyed
                # by dataset identities like "cattle_1200" -- internal ML
                # reference data, NOT PashuPrint-enrolled livestock. Only a
                # match against an animal ACTUALLY stored in the `animals`
                # table counts as "already enrolled". A gallery-only hit
                # (matched_animal is None) is never shown as an enrolled cow
                # and never blocks registration -- if nothing is enrolled yet
                # (animals table empty), no gallery match can block anything.
                for r, p in zip(results, st.session_state.reg_paths):
                    if r["status"] == "high_confidence":
                        match = r["top_matches"][0]
                        matched_cow_id = match["cow_id"]
                        matched_animal = db.get_animal(matched_cow_id)

                        if matched_animal is None:
                            # ML gallery/reference identity only -- not an
                            # application-enrolled animal. Not a duplicate.
                            continue

                        st.error(f"⚠️ Already enrolled as Cow #{matched_cow_id} ({match['score']*100:.1f}% match)")

                        matched_photo = matched_animal.get("muzzle_photo_path")
                        if matched_photo and os.path.exists(matched_photo):
                            side1, side2 = st.columns(2)
                            with side1:
                                st.image(p, caption="Uploaded photo", use_container_width=True)
                            with side2:
                                st.image(matched_photo, caption=f"Stored photo — Cow #{matched_cow_id}", use_container_width=True)

                        db.add_fraud_flag(matched_cow_id, "duplicate_registration", f"Score {match['score']:.2f}")
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
                try:
                    animal = db.register_animal(
                        owner_name=owner, breed=breed, age=age, policy_id=policy,
                        muzzle_photo_path=st.session_state.reg_paths[0],
                    )
                except sqlite3.IntegrityError:
                    st.error("Cow ID was just taken by a simultaneous registration — please try again.")
                    st.stop()

                cow_id = animal["cow_id"]

                # Store this animal's OWN reference embedding (averaged
                # across its registration photos) so Verify can compare
                # future claim photos against actual enrolled animals, not
                # just the internal ML reference gallery.
                try:
                    reference_vector = embed_query_average(st.session_state.reg_paths)
                    db.add_embedding(cow_id, reference_vector.tolist())
                except ValueError:
                    pass  # photos already passed the blur gate above; defensive only

                for p in st.session_state.reg_paths:
                    db.log_verification(
                        cow_id=cow_id, verification_type="register",
                        result_status="registered", photo_path=p,
                    )
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
