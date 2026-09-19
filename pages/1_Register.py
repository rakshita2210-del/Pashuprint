from html import escape

import streamlit as st
import os, time
import sqlite3
import numpy as np

from backend import db
from backend.dup_check import check_duplicate
from cattle_gate import assess_cattle_likeness
from matching import find_matches, embed_query_average
from utils.mock_backend import get_all_embeddings, get_embedding_for_image
from utils.ui import (
    setup_page, page_header, callout, stepper, photo_grid, duplicate_card,
    section, html, fmt_ts,
)

setup_page("Register Cow", "📝", "register")

page_header(
    "Register Cow",
    "Enroll a new animal in two steps: upload at least 3 muzzle photos, then complete the animal's details.",
    "📝", eyebrow="Enrollment",
)

STEPS = ["Upload muzzle photos", "Animal details", "Registered"]

if "reg_step" not in st.session_state:
    st.session_state.reg_step = "upload"
if "reg_paths" not in st.session_state:
    st.session_state.reg_paths = []


def _reset():
    st.session_state.reg_step = "upload"
    st.session_state.reg_paths = []
    st.session_state.pop("reg_done", None)


# --- STEP 1: UPLOAD ---
if st.session_state.reg_step == "upload":
    stepper(STEPS, 0)

    section("Step 1 · Upload muzzle photos", "Clear, close-up photos of the same cow's muzzle. Three or more give the most reliable enrollment.")
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
            callout("warn", f"{n} photo(s) uploaded — at least 3 are required for reliable enrollment.", title="Add more photos")
        else:
            callout("success", f"{n} photos ready. Continue to run the image, fraud and identity checks.", title="Photos received")

        photo_grid(st.session_state.reg_paths)

        if n >= 3:
            if st.button("Check photos & continue  →", type="primary", use_container_width=True):
                # --- Cattle/muzzle DOMAIN gate -- runs before anything else.
                # An image that fails this can never reach check_duplicate(),
                # embed_image(), or find_matches(); registration is refused
                # outright and no id is generated. ---
                for p in st.session_state.reg_paths:
                    gate = assess_cattle_likeness(p)
                    if not gate["is_cattle_like"]:
                        callout("danger", "Please upload a clear cattle muzzle photo. " + (gate["reason"] or ""),
                                title="Invalid image")
                        st.stop()

                # --- Exact/near-identical PHOTO re-upload check (perceptual hash,
                # NOT biometric -- backend/dup_check.py) ---
                all_paths = db.get_all_photo_paths()
                for p in st.session_state.reg_paths:
                    dup = check_duplicate(p, all_paths)
                    if dup["is_duplicate"]:
                        owner_cow = next(
                            (a["cow_id"] for a in db.get_all_animals()
                             if a.get("muzzle_photo_path") == dup.get("matched_photo_path")),
                            "Existing record",
                        )
                        duplicate_card(
                            p, dup.get("matched_photo_path"), owner_cow,
                            title="This exact photo already exists in the system",
                            note="The same photograph has been submitted before. Reusing a photo is a common fraud pattern, so registration was refused and a fraud flag has been logged for review.",
                        )
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
                        callout("warn", "One or more photos are too blurry to analyse. Please retake them and upload again.",
                                title="Photo too blurry")
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

                        duplicate_card(
                            p, matched_animal.get("muzzle_photo_path"), matched_cow_id,
                            score=match["score"], title="Already enrolled — duplicate registration blocked",
                        )

                        db.add_fraud_flag(matched_cow_id, "duplicate_registration", f"Score {match['score']:.2f}")
                        st.stop()

                st.session_state.reg_step = "details"
                st.rerun()

# --- STEP 2: DETAILS + PLOT ---
elif st.session_state.reg_step == "details":
    if not st.session_state.reg_paths:
        _reset()
        st.rerun()
    stepper(STEPS, 1)
    callout("success", "The photos passed image, duplicate and identity checks — this animal is not yet enrolled.",
            title="Checks passed")

    section("Step 2 · Animal details", "These details are stored on the animal's passport and linked to the policy.")

    left, right = st.columns([1.1, 1], gap="large")

    with left:
        with st.container(key="formcard"):
            breed = st.text_input("Breed", placeholder="e.g. Gir, Sahiwal, Red Sindhi")
            c1, c2 = st.columns(2)
            with c1:
                age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
            with c2:
                policy = st.text_input("Policy ID", placeholder="e.g. POL-9924")
            owner = st.text_input("Owner name")

        st.markdown("<div style='height:.75rem;'></div>", unsafe_allow_html=True)
        error_slot = st.container()
        b1, b2 = st.columns([2, 1])
        with b1:
            register_clicked = st.button("Register animal", type="primary", use_container_width=True)
        with b2:
            if st.button("Cancel", use_container_width=True):
                _reset()
                st.rerun()

    with right:
        with st.container(key="chartcard"):
            html('<div style="font-weight:700;color:#022c22;">Identity embedding</div>'
                 '<div style="font-size:.82rem;color:#64748b;margin-bottom:.25rem;">Your photos are averaged into a single identity vector.</div>')
            existing = get_all_embeddings()
            new_points = [get_embedding_for_image(p) for p in st.session_state.reg_paths]
            avg_point = np.mean(new_points, axis=0)

            xs = [v[0] for v in existing.values()] + [p[0] for p in new_points] + [avg_point[0]]
            ys = [v[1] for v in existing.values()] + [p[1] for p in new_points] + [avg_point[1]]

            st.scatter_chart({"x": xs, "y": ys}, x="x", y="y", height=240)
            st.caption(f"{len(existing)} existing animals · {len(new_points)} of your photos · 1 averaged identity")
        photo_grid(st.session_state.reg_paths)

    if register_clicked:
        if not all([breed, owner, policy]):
            with error_slot:
                callout("danger", "Breed, Policy ID and Owner name are all required.", title="Missing details")
        else:
            try:
                animal = db.register_animal(
                    owner_name=owner, breed=breed, age=age, policy_id=policy,
                    muzzle_photo_path=st.session_state.reg_paths[0],
                )
            except sqlite3.IntegrityError:
                with error_slot:
                    callout("danger", "Cow ID was just taken by a simultaneous registration — please try again.",
                            title="Registration conflict")
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
            st.session_state.reg_done = {
                "cow_id": cow_id, "breed": breed, "age": age, "owner": owner,
                "policy": policy, "registered": animal.get("registration_date"),
                "n_photos": len(st.session_state.reg_paths),
            }
            st.session_state.reg_step = "done"
            st.session_state.reg_paths = []
            st.rerun()

# --- STEP 3: SUCCESS ---
else:
    stepper(STEPS, 3)
    d = st.session_state.get("reg_done")
    if not d:
        _reset()
        st.rerun()

    html(f"""
    <div class="donecard">
      <div class="done-head"><div class="ok">&#10003;</div>
        <div><div class="dt">Enrollment complete</div><div class="dm">Animal registered successfully</div></div></div>
      <div class="done-body">
        <div><div class="done-id-lab">New Cow ID</div><div class="done-id">{escape(str(d['cow_id']))}</div></div>
        <div class="kv">
          <div><div class="k">Breed</div><div class="v">{escape(str(d['breed']))}</div></div>
          <div><div class="k">Age</div><div class="v">{escape(str(d['age']))} yrs</div></div>
          <div><div class="k">Owner</div><div class="v">{escape(str(d['owner']))}</div></div>
          <div><div class="k">Policy ID</div><div class="v">{escape(str(d['policy']))}</div></div>
          <div><div class="k">Registered</div><div class="v">{escape(fmt_ts(d['registered']))}</div></div>
          <div><div class="k">Photos enrolled</div><div class="v">{d['n_photos']}</div></div>
        </div>
      </div>
    </div>
    """)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("View livestock passport", type="primary", use_container_width=True):
            st.session_state["selected_cow_id"] = d["cow_id"]
            st.switch_page("pages/4_Passport.py")
    with b2:
        if st.button("Register another animal", use_container_width=True):
            _reset()
            st.rerun()
