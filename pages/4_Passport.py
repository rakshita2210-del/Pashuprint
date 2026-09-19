import base64
from html import escape
from io import BytesIO

import qrcode
import streamlit as st

from backend import db
from utils.ui import (
    setup_page, page_header, html, section, empty_state, callout, img_uri, fmt_ts,
)

setup_page("Livestock Passport", "🪪", "passport")

page_header(
    "Livestock Passport",
    "Official identity record, muzzle photo and verification history for a registered cow.",
    "🪪", eyebrow="Registry",
)

# result_status -> (label, tone). Tones share colours with the rest of the app.
EVENT_LABELS = {
    "registered": ("Registered", "good"),
    "high_confidence": ("Verified — match confirmed", "good"),
    "low_confidence": ("Low confidence — manual review", "warn"),
    "no_match": ("No match", "bad"),
    "inconsistent_images": ("Inconsistent photos", "bad"),
    "invalid_image": ("Invalid image", "muted"),
    "unusable": ("Image unusable", "muted"),
}
TYPE_LABELS = {"register": "Registration", "claim": "Claim verification", "verify": "Verification"}

# --- EMPTY STATE HANDLING ---
all_animals = db.get_all_animals()

if not all_animals:
    empty_state(
        "🪪", "No passports yet",
        "A passport is issued as soon as a cow is registered. Register an animal and its identity record will appear here.",
        cta=("pages/1_Register.py", "Register a cow", "📝"),
    )
    st.stop()

cow_ids = [animal["cow_id"] for animal in all_animals]

default_index = 0
if "selected_cow_id" in st.session_state and st.session_state["selected_cow_id"] in cow_ids:
    default_index = cow_ids.index(st.session_state["selected_cow_id"])

section("Find an animal")
selected_cow_id = st.selectbox(
    "Select or type a Cow ID to view its passport",
    options=cow_ids, index=default_index,
)

cow_data = db.get_animal(selected_cow_id)
history_data = db.get_verification_history(selected_cow_id)

# --- QR code: no fixed public URL for this local/demo deployment, so the QR
# encodes a structured text payload built from the selected cow's real record. ---
passport_payload = (
    "PashuPrint Livestock Passport\n"
    f"Cow ID: {cow_data.get('cow_id')}\n"
    f"Breed: {cow_data.get('breed')}\n"
    f"Age: {cow_data.get('age')} Yrs\n"
    f"Owner: {cow_data.get('owner_name')}\n"
    f"Policy ID: {cow_data.get('policy_id')}\n"
    f"Status: {cow_data.get('status')}\n"
    f"Registered: {cow_data.get('registration_date')}"
)
qr = qrcode.QRCode(box_size=4, border=1)
qr.add_data(passport_payload)
qr.make(fit=True)
buf = BytesIO()
qr.make_image(fill_color="#022c22", back_color="white").save(buf, format="PNG")
qr_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

photo = img_uri(cow_data.get("muzzle_photo_path"), 640)
photo_html = f'<img src="{photo}" alt="Muzzle photo"/>' if photo else '<div class="noimg">No muzzle photo on file</div>'

status = cow_data.get("status") or "active"
status_tone = "good" if status == "active" else "warn"


def field(label, value):
    return f'<div><div class="k">{label}</div><div class="v">{escape(str(value)) if value not in (None, "") else "—"}</div></div>'


html(f"""
<div class="pp">
  <div class="pp-head">
    <div class="t">PashuPrint <b>·</b> Livestock Identity Passport</div>
    <div class="n">No. {escape(str(cow_data.get('cow_id')))}</div>
  </div>
  <div class="pp-body">
    <div class="pp-photo">{photo_html}<div class="pcap">Muzzle print</div></div>
    <div>
      <div class="pp-id-lab">Cow ID</div>
      <div class="pp-id">{escape(str(cow_data.get('cow_id')))}</div>
      <div class="pp-grid">
        {field("Owner", cow_data.get("owner_name"))}
        {field("Policy ID", cow_data.get("policy_id"))}
        {field("Breed", (cow_data.get("breed") or "").title() or None)}
        {field("Age", f"{cow_data.get('age')} yrs" if cow_data.get("age") is not None else None)}
        <div><div class="k">Status</div><div class="v"><span class="pill {status_tone}">{escape(str(status)).title()}</span></div></div>
        {field("Registered", fmt_ts(cow_data.get("registration_date")))}
      </div>
    </div>
  </div>
  <div class="pp-foot">
    <div class="note">This record is generated from the PashuPrint registry. Identity is established by the animal's muzzle print;
    every verification below is logged and time-stamped.</div>
    <div class="pp-qr"><img src="{qr_uri}" alt="Passport QR code"/><div class="cap">Scan to verify</div></div>
  </div>
</div>
""")

# --- VERIFICATION HISTORY TIMELINE ---
section("Verification & claim history", "Newest first. Every check made against this animal.")

if not history_data:
    callout("neutral", "No verification history has been recorded for this animal yet.")
else:
    items = []
    for ev in history_data:
        label, tone = EVENT_LABELS.get(ev.get("result_status"), (str(ev.get("result_status")).replace("_", " ").title(), "muted"))
        kind = TYPE_LABELS.get(ev.get("verification_type"), str(ev.get("verification_type")).title())
        score = ev.get("similarity_score")
        score_html = f'<div class="tl-score">{score * 100:.1f}%</div>' if score is not None else ""
        items.append(
            f'<div class="tl-item {tone}"><div><div class="tl-title">{escape(label)}</div>'
            f'<div class="tl-sub">{escape(kind)} · {escape(fmt_ts(ev.get("timestamp")))}</div></div>{score_html}</div>'
        )
    html(f'<div class="tl">{"".join(items)}</div>')
