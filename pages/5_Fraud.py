import streamlit as st
import pandas as pd

from backend import db
from utils.ui import inject_css, hero, info_strip

st.set_page_config(page_title="Fraud Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
inject_css()

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

hero("Fraud Dashboard", "Every duplicate, mismatch, and low-confidence claim flagged during registration and verification", "📊")

flags = db.get_all_fraud_flags()

if not flags:
    info_strip("✅ No fraud flags recorded yet — every registration and verification has cleared cleanly.")
    st.stop()

df = pd.DataFrame(flags)

# --- SUMMARY METRICS ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total flags", len(df))
m2.metric("Unique cows involved", df.loc[df["cow_id"] != "UNKNOWN", "cow_id"].nunique())
m3.metric("Flag types", df["flag_type"].nunique())
most_common = df["flag_type"].value_counts().idxmax()
m4.metric("Most common", most_common.replace("_", " ").title())

st.divider()

# --- FILTERS ---
st.markdown("### 🔍 Filter")
f1, f2 = st.columns([2, 1])
with f1:
    flag_types = sorted(df["flag_type"].unique().tolist())
    selected_types = st.multiselect("Flag type", options=flag_types, default=flag_types, label_visibility="collapsed", placeholder="Filter by flag type")
with f2:
    cow_query = st.text_input("Cow ID contains", placeholder="e.g. COW-0004", label_visibility="collapsed")

filtered = df[df["flag_type"].isin(selected_types)]
if cow_query:
    filtered = filtered[filtered["cow_id"].str.contains(cow_query, case=False, na=False)]

st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

if filtered.empty:
    st.info("No fraud flags match the current filter.")
else:
    display = filtered[["created_at", "cow_id", "flag_type", "details"]].copy()
    display.columns = ["Flagged At", "Cow ID", "Flag Type", "Details"]
    display["Flag Type"] = display["Flag Type"].str.replace("_", " ").str.title()
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.caption(f"Showing {len(filtered)} of {len(df)} total flags.")
