import streamlit as st
import os, time
from utils.mock_backend import find_matches, log_verification, add_fraud_flag

st.set_page_config(page_title="Verify Cow", page_icon="🔍", layout="wide")

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

st.title("🔍 Verify Cow")
st.caption("Upload a muzzle photo to verify the animal's identity")

uploaded = st.file_uploader("Upload muzzle photo", type=["jpg", "jpeg", "png"])

if uploaded:
    os.makedirs("uploads", exist_ok=True)
    path = f"uploads/claim_{int(time.time())}.jpg"
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    st.image(path, caption="Uploaded photo", width=300)

    if st.button("Verify", type="primary"):
        with st.spinner("Analyzing..."):
            result = find_matches(path, top_k=3)

        status = result["status"]

        # --- Verdict banner ---
        if status == "high_confidence":
            st.success(f"✅ MATCHED — Cow #{result['top_matches'][0]['cow_id']}")
            log_verification(result["top_matches"][0]["cow_id"], "claim", path,
                             result["top_matches"][0]["cow_id"],
                             result["top_matches"][0]["score"], "high_confidence")
        elif status == "low_confidence":
            st.warning("⚠️ LOW CONFIDENCE — MANUAL REVIEW REQUIRED")
            log_verification(result["top_matches"][0]["cow_id"], "claim", path,
                             result["top_matches"][0]["cow_id"],
                             result["top_matches"][0]["score"], "low_confidence")
            add_fraud_flag(result["top_matches"][0]["cow_id"], "low_confidence_claim",
                           f"Score {result['top_matches'][0]['score']:.2f} below threshold")
        elif status == "no_match":
            st.error("❌ NO MATCH FOUND")
            log_verification(None, "claim", path, None, None, "no_match")
            add_fraud_flag(None, "no_match_claim", "No match above threshold")
        else:
            st.info("⚪ CANNOT VERIFY — image unusable")
            st.caption("Falls back to existing manual process")
            log_verification(None, "claim", path, None, None, "unusable")
            add_fraud_flag(None, "unusable_claim_image", "Image quality too poor")

        # --- Top-3 matches ---
        if result["top_matches"]:
            st.subheader("Top 3 matches")
            cols = st.columns(3)
            for i, m in enumerate(result["top_matches"]):
                with cols[i]:
                    if os.path.exists(m["photo_path"]):
                        st.image(m["photo_path"], width=200)
                    else:
                        st.write("_(no image)_")
                    st.write(f"**Cow #{m['cow_id']}**")
                    st.progress(min(m["score"], 1.0))
                    st.write(f"Score: {m['score']*100:.1f}%")

        if st.button("Verify Another"):
            st.rerun()