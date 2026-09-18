import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO

from backend import db
from utils.ui import inject_css, hero

st.set_page_config(page_title="Livestock Passport", page_icon="🪪", layout="wide", initial_sidebar_state="collapsed")
inject_css()

if not st.session_state.get("user"):
    st.warning("Please login first")
    st.stop()

hero("Livestock Passport", "Official identity record, muzzle photo, and verification history for a registered cow", "🪪")

# --- EMPTY STATE HANDLING ---
all_animals = db.get_all_animals()

if not all_animals:
    st.info("ℹ️ No animals currently registered in the database.")
else:
    # --- UI/UX: Better selector design ---
    st.markdown("### 🔍 Search Registry")
    cow_ids = [animal['cow_id'] for animal in all_animals]

    default_index = 0
    if 'selected_cow_id' in st.session_state and st.session_state['selected_cow_id'] in cow_ids:
        default_index = cow_ids.index(st.session_state['selected_cow_id'])

    selected_cow_id = st.selectbox("Select or type Cow ID to view passport:", options=cow_ids, index=default_index, label_visibility="collapsed")
    st.divider()

    # --- DISPLAY AREA ---
    if selected_cow_id:
        cow_data = db.get_animal(selected_cow_id)
        history_data = db.get_verification_history(selected_cow_id)

        # UI/UX: Use a container to group the passport data like a real ID card
        with st.container(border=True):
            col1, col2, col3 = st.columns([1.5, 2, 1])

            with col1:
                # Muzzle Photo with nice caption
                photo_path = cow_data.get('muzzle_photo_path')
                if photo_path:
                    st.image(photo_path, caption=f"Verified Muzzle: {selected_cow_id}", use_container_width=True)
                else:
                    st.info("No muzzle photo on file for this animal.")

            with col2:
                st.markdown(f"## ID: {cow_data.get('cow_id')}")
                st.markdown(f"**👤 Owner:** {cow_data.get('owner_name')} &nbsp;|&nbsp; **📄 Policy:** `{cow_data.get('policy_id')}`")

                # UI/UX: Use Metric cards for quick stats
                met1, met2, met3 = st.columns(3)
                met1.metric("Breed", cow_data.get('breed'))
                met2.metric("Age", f"{cow_data.get('age')} Yrs")

                status = cow_data.get('status', 'active')
                # Add emoji to metric based on status
                met3.metric("Status", f"🟢 {status}" if status == "active" else f"🔴 {status}")

                st.caption(f"**Registered on:** {cow_data.get('registration_date')}")

            with col3:
                # --- QR CODE GENERATION ---
                st.markdown("<div style='text-align: center; color: gray;'>Scan to Verify</div>", unsafe_allow_html=True)
                qr = qrcode.QRCode(box_size=4, border=1)
                qr.add_data(str(selected_cow_id))
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="#064e3b", back_color="white")

                buf = BytesIO()
                img_qr.save(buf, format="PNG")
                st.image(buf, use_container_width=True)

        # --- VERIFICATION HISTORY TABLE ---
        st.markdown("### 📋 Verification & Claim History")

        if not history_data:
            st.info("No verification history available for this animal.")
        else:
            df_history = pd.DataFrame(history_data)

            # UI/UX: Format the dataframe to look much cleaner
            display_cols = ['timestamp', 'verification_type', 'result_status', 'similarity_score']
            existing_cols = [col for col in display_cols if col in df_history.columns]

            df_display = df_history[existing_cols].copy()

            # Clean up column names for display (e.g., 'result_status' -> 'Result Status')
            df_display.columns = [col.replace('_', ' ').title() for col in df_display.columns]

            # Use Streamlit's new dataframe styling to hide the index column (numbers on the left)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
