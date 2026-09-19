import streamlit as st
import os
import time

from backend import db
from backend.services.mock_ml import mock_muzzle_verification
from cattle_gate import assess_cattle_likeness
from matching import (
    find_matches_multi,
    embed_query_average,
    rank_against_registered,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
)
from utils.ui import (
    setup_page,
    page_header,
    verdict_banner,
    match_card,
    callout,
    empty_state,
    photo_grid,
    section,
    stepper,
)

setup_page("Verify Cow", "🔍", "verify")

page_header(
    "Verify Cow",
    "Upload 3 muzzle photos of the animal presented for a claim. PashuPrint checks them against every enrolled cow.",
    "🔍", eyebrow="Claim verification",
)

if not db.get_all_animals():
    empty_state(
        "🐄",
        "No animals enrolled yet",
        "Verification compares claim photos against registered animals. Register your first cow to get started.",
        cta=("pages/1_Register.py", "Register a cow", "📝"),
    )
    st.stop()


def _mock_verification(image_paths):
    """Fallback only when the real ML gallery/model is unavailable."""

    candidate_ids = [a["cow_id"] for a in db.get_all_animals()]

    mock_result = mock_muzzle_verification(
        image_paths[0],
        candidate_ids,
    )

    status = (
        "high_confidence"
        if mock_result["result_status"] == "MATCH"
        else "no_match"
    )

    top_matches = []

    if mock_result["top_match_cow_id"]:
        top_matches = [
            {
                "cow_id": mock_result["top_match_cow_id"],
                "score": mock_result["similarity_score"],
            }
        ]

    return {
        "status": status,
        "top_matches": top_matches,
        "quality_ok": True,
    }


def _run_verification(image_paths):
    """Run the real multi-image muzzle verification.

    Cattle/muzzle DOMAIN gate runs FIRST, on every uploaded photo. An
    image that fails it can never reach find_matches_multi() (and so can
    never reach embed_image() or produce a MATCHED result) -- the whole
    batch is refused outright."""

    for p in image_paths:
        gate = assess_cattle_likeness(p)
        if not gate["is_cattle_like"]:
            return {
                "status": "invalid_image",
                "top_matches": [],
                "quality_ok": False,
                "model_loaded": True,
                "invalid_reason": gate["reason"],
            }

    try:
        result = find_matches_multi(
            image_paths,
            top_k=3,
        )

        result["model_loaded"] = True

    except FileNotFoundError:
        result = _mock_verification(image_paths)
        result["model_loaded"] = False

    # If quality/consistency are fine, ALSO compare against ACTUAL
    # registered animals' own reference embeddings (stored at registration
    # time -- see pages/1_Register.py). This is the real "does this match
    # an enrolled cow" check; a registered-animal match takes priority
    # over the raw ML-gallery result below.
    if result["status"] not in ("unusable", "inconsistent_images") and result.get("model_loaded"):
        registered = []
        for animal in db.get_all_animals():
            vec = db.get_embedding(animal["cow_id"])
            if vec is not None:
                registered.append((animal["cow_id"], vec))

        if registered:
            try:
                query = embed_query_average(image_paths)
                reg_result = rank_against_registered(query, registered, top_k=3)
                if reg_result["status"] in ("high_confidence", "low_confidence"):
                    reg_result["model_loaded"] = True
                    result = reg_result
            except ValueError:
                pass  # fall through to the existing gallery-based result

    for match in result.get("top_matches", []):
        animal = db.get_animal(match["cow_id"])

        match["is_enrolled"] = animal is not None
        match["photo_path"] = (
            animal["muzzle_photo_path"]
            if animal
            else None
        )

    # find_matches_multi() ranks against the full ML REFERENCE gallery,
    # which includes dataset identities (e.g. "cattle_1200") that were
    # never enrolled through this app. Only a match against an animal
    # ACTUALLY stored in the `animals` table is an application-level
    # identification -- a gallery-only hit is never presented as a
    # matched/enrolled cow, in the verdict OR in the Top Matches cards.
    enrolled_matches = [m for m in result.get("top_matches", []) if m["is_enrolled"]]

    if result["status"] in ("high_confidence", "low_confidence") and not enrolled_matches:
        result["status"] = "no_match"

    result["top_matches"] = enrolled_matches

    return result


def _reset():
    st.session_state.pop("verify_result", None)
    st.session_state.pop("verify_paths", None)


def _tone(score):
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "good"
    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "warn"
    return "muted"


# =====================================================================
# RESULT VIEW -- shown once a verification has run
# =====================================================================
if "verify_result" in st.session_state and "verify_paths" in st.session_state:
    stepper(["Upload photos", "Verify", "Result"], 3)

    result = st.session_state.verify_result
    status = result["status"]

    if result.get("model_loaded") is False:
        callout(
            "warn",
            "The real ML model/gallery could not be loaded, so this is a MOCK result and must not be used for a claim decision.",
            title="Demo mode",
        )

    # --- Fraud flag is ALWAYS raised for these outcomes.
    # No UI path skips it -- it fires as soon as the result is computed.
    if status == "high_confidence":
        m = result["top_matches"][0]

        verdict_banner(
            status,
            m["cow_id"],
            m["score"],
        )

        db.log_verification(
            cow_id=m["cow_id"],
            verification_type="claim",
            result_status="high_confidence",
            photo_path=st.session_state.verify_paths[0],
            top_match_cow_id=m["cow_id"],
            similarity_score=m["score"],
        )

    elif status == "low_confidence":
        best = result["top_matches"][0] if result.get("top_matches") else None

        verdict_banner(
            status,
            best["cow_id"] if best else None,
            best["score"] if best else None,
        )

        if best:
            m = best

            db.log_verification(
                cow_id=m["cow_id"],
                verification_type="claim",
                result_status="low_confidence",
                photo_path=st.session_state.verify_paths[0],
                top_match_cow_id=m["cow_id"],
                similarity_score=m["score"],
            )

            db.add_fraud_flag(
                m["cow_id"],
                "low_confidence_claim",
                f"Score {m['score']:.2f}",
            )

    elif status == "no_match":
        verdict_banner(status)

        db.log_verification(
            cow_id="UNKNOWN",
            verification_type="claim",
            result_status="no_match",
            photo_path=st.session_state.verify_paths[0],
        )

        db.add_fraud_flag(
            "UNKNOWN",
            "no_match_claim",
            "No match above threshold",
        )

    elif status == "inconsistent_images":
        verdict_banner(status)

        per_image = result.get("per_image_matches", [])
        seen_cow_ids = sorted({m["cow_id"] for m in per_image})

        db.log_verification(
            cow_id="UNKNOWN",
            verification_type="claim",
            result_status="inconsistent_images",
            photo_path=st.session_state.verify_paths[0],
        )

        db.add_fraud_flag(
            "UNKNOWN",
            "inconsistent_images_claim",
            f"Uploaded photos matched different cows: {', '.join(seen_cow_ids)}",
        )

    elif status == "invalid_image":
        verdict_banner(status)

        if result.get("invalid_reason"):
            callout("neutral", result["invalid_reason"], title="Why it was rejected")

        db.log_verification(
            cow_id="UNKNOWN",
            verification_type="claim",
            result_status="invalid_image",
            photo_path=st.session_state.verify_paths[0],
        )

        db.add_fraud_flag(
            "UNKNOWN",
            "invalid_image_claim",
            result.get("invalid_reason") or "Uploaded photo does not appear to be a cattle muzzle",
        )

    else:
        verdict_banner(status)
        callout("neutral", "Falls back to the existing manual process.")

        db.log_verification(
            cow_id="UNKNOWN",
            verification_type="claim",
            result_status="unusable",
            photo_path=st.session_state.verify_paths[0],
        )

        db.add_fraud_flag(
            "UNKNOWN",
            "unusable_claim_image",
            "All photos were unusable",
        )

    # --- Top matches (photo · cow ID · similarity, side by side) ---
    matches = result.get("top_matches") or []
    if matches:
        section("Top matches", "Closest enrolled animals, ranked by muzzle similarity.")

        cols = st.columns(3, gap="medium")
        for i, match in enumerate(matches[:3]):
            with cols[i]:
                img = (
                    match.get("photo_path")
                    if match.get("photo_path")
                    and os.path.exists(match["photo_path"])
                    else None
                )

                match_card(
                    match["cow_id"],
                    match["score"],
                    image_path=img,
                    rank=i + 1,
                    tone=_tone(match["score"]),
                )

    section("Submitted photos", "The claim photos that were analysed.")
    photo_grid(st.session_state.verify_paths, prefix="Claim photo")

    if result.get("model_loaded"):
        st.caption("Scored by the trained ResNet50 muzzle model against enrolled animals.")

    if st.button("Verify another cow", type="primary"):
        _reset()
        st.rerun()

    st.stop()


# =====================================================================
# UPLOAD VIEW
# =====================================================================
stepper(["Upload photos", "Verify", "Result"], 0)

section("Upload claim photos", "Three or more clear, close-up muzzle photos of the same cow.")

uploaded = st.file_uploader(
    "Drop 3+ muzzle photos of the same cow",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if not uploaded:
    st.session_state.pop("verify_paths", None)
    callout("info", "Upload the claim photos above to begin. Nothing is analysed until you press Verify.")
    st.stop()

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
    callout("warn", f"{n} photo(s) uploaded — at least 3 are required.", title="Add more photos")
else:
    callout("success", f"{n} photos ready — they will be averaged into one identity.", title="Photos received")

photo_grid(paths, prefix="Claim photo")

if n >= 3:
    if st.button("Verify now", type="primary", use_container_width=True):
        with st.spinner("Analyzing muzzle patterns..."):
            result = _run_verification(
                st.session_state.verify_paths
            )

        st.session_state.verify_result = result
        st.rerun()
