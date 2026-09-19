from html import escape

import pandas as pd
import streamlit as st

from backend import db
from utils.ui import setup_page, page_header, html, section, stat_grid, empty_state, callout, fmt_ts

setup_page("Fraud Dashboard", "📊", "fraud")

page_header(
    "Fraud Dashboard",
    "Every duplicate, mismatch and low-confidence claim flagged during registration and verification.",
    "📊", eyebrow="Risk & compliance",
)

# Illustrative assumption used ONLY for the exposure estimate below -- not a
# measured figure. Change it here to match the insurer's real average sum insured.
ASSUMED_SUM_INSURED_INR = 50_000

# flag_type -> (severity colour, label). Red = serious, amber = needs review, grey = unusable input.
FLAG_META = {
    "duplicate_registration": ("red", "Duplicate registration"),
    "duplicate_photo": ("red", "Duplicate photo"),
    "no_match_claim": ("red", "No match on claim"),
    "inconsistent_images_claim": ("red", "Inconsistent photos"),
    "low_confidence_claim": ("amber", "Low confidence"),
    "unusable_claim_image": ("grey", "Unusable image"),
    "invalid_image_claim": ("grey", "Invalid image"),
}


def meta(flag_type):
    return FLAG_META.get(flag_type, ("grey", str(flag_type).replace("_", " ").title()))


def inr(n):
    """Format an integer in Indian digit grouping: 1,23,456."""
    s = str(int(n))
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


def inr_short(n):
    """Compact rupee figure: 1250000 -> ₹12.5 L, 25000000 -> ₹2.5 Cr."""
    if n >= 10_000_000:
        return f"₹{n / 10_000_000:.1f} Cr"
    if n >= 100_000:
        return f"₹{n / 100_000:.1f} L"
    return inr(n)


flags = db.get_all_fraud_flags()

if not flags:
    empty_state(
        "✅", "No flags raised",
        "Every registration and verification so far has cleared cleanly. Flags appear here the moment a duplicate, mismatch or low-confidence claim is detected.",
    )
    st.stop()

df = pd.DataFrame(flags)
df["sev"] = df["flag_type"].map(lambda t: meta(t)[0])

n_red = int((df["sev"] == "red").sum())
n_amber = int((df["sev"] == "amber").sum())
n_grey = int((df["sev"] == "grey").sum())
exposure = (n_red + n_amber) * ASSUMED_SUM_INSURED_INR

# --- SUMMARY CARDS ---
stat_grid([
    {"value": len(df), "label": "Total flags", "tone": "dark",
     "note": f"{df.loc[df['cow_id'] != 'UNKNOWN', 'cow_id'].nunique()} identified cows involved"},
    {"value": n_red, "label": "Serious", "tone": "red", "note": "Duplicates, no match, mixed animals"},
    {"value": n_amber, "label": "Needs review", "tone": "amber", "note": "Low-confidence matches"},
    {"value": n_grey, "label": "Unusable input", "tone": "grey", "note": "Invalid or unreadable photos"},
    {"value": f"≈ {inr_short(exposure)}", "label": "Estimated exposure", "tone": "red",
     "note": f"Estimate only: {n_red + n_amber} flags × {inr(ASSUMED_SUM_INSURED_INR)} assumed sum insured (= {inr(exposure)})"},
], cols=5)

# --- JUMP TO PASSPORT ---
flagged_cow_ids = sorted({cid for cid in df["cow_id"].unique() if cid != "UNKNOWN"})
if flagged_cow_ids:
    section("View a flagged animal")
    j1, j2 = st.columns([3, 1], vertical_alignment="bottom")
    with j1:
        jump_cow_id = st.selectbox("Cow ID", options=flagged_cow_ids, label_visibility="collapsed")
    with j2:
        if st.button("Open passport", use_container_width=True):
            st.session_state["selected_cow_id"] = jump_cow_id
            st.switch_page("pages/4_Passport.py")

# --- FILTERS ---
section("Flags", "Colour shows severity: red serious · amber needs review · grey unusable input.")
f1, f2 = st.columns([2, 1])
with f1:
    flag_types = sorted(df["flag_type"].unique().tolist())
    selected_types = st.multiselect(
        "Flag type", options=flag_types, default=flag_types,
        format_func=lambda t: meta(t)[1],
        label_visibility="collapsed", placeholder="Filter by flag type",
    )
with f2:
    cow_query = st.text_input("Cow ID contains", placeholder="Search Cow ID, e.g. COW-0004", label_visibility="collapsed")

filtered = df[df["flag_type"].isin(selected_types)]
if cow_query:
    filtered = filtered[filtered["cow_id"].str.contains(cow_query, case=False, na=False)]

st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)

MAX_ROWS = 200

if filtered.empty:
    callout("neutral", "No flags match the current filters. Clear the search or add flag types to see more.")
else:
    rows = []
    for r in filtered.head(MAX_ROWS).itertuples():
        sev, label = meta(r.flag_type)
        cow = r.cow_id if r.cow_id != "UNKNOWN" else "Unidentified"
        rows.append(
            f'<tr class="sev-{sev}"><td class="mono">{escape(str(cow))}</td>'
            f'<td><span class="badge {sev}">{escape(label)}</span></td>'
            f'<td class="ts">{escape(fmt_ts(r.created_at))}</td>'
            f'<td>{escape(str(r.details or "—"))}</td></tr>'
        )
    html(
        '<div class="dt-wrap"><table class="dt"><thead><tr><th>Cow ID</th><th>Flag type</th><th>Timestamp</th><th>Details</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

    shown = min(len(filtered), MAX_ROWS)
    st.caption(f"Showing {shown} of {len(df)} total flags" + (f" (latest {MAX_ROWS} of {len(filtered)} matching)" if len(filtered) > MAX_ROWS else "."))
