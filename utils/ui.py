import streamlit as st


def inject_css():
    st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem !important; max-width: 1200px !important;}
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #0f172a;
    }

    .hero {
        background: linear-gradient(135deg, #022c22 0%, #064e3b 45%, #10b981 100%);
        border-radius: 22px;
        padding: 2.5rem;
        color: white;
        position: relative;
        overflow: hidden;
        margin-bottom: 1.5rem;
    }
    .hero::before {
        content:"";
        position:absolute;
        top:-120px; right:-100px;
        width:380px; height:380px;
        background: radial-gradient(circle, rgba(52,211,153,0.55) 0%, transparent 65%);
        border-radius: 50%;
        filter: blur(28px);
    }
    .hero-inner {position: relative; z-index: 1;}
    .hero h1 {font-size: 2.1rem; font-weight: 800; color: white; letter-spacing: -0.02em; margin: 0 0 0.4rem 0;}
    .hero p  {color: #d1fae5; font-size: 1rem; margin: 0; line-height: 1.5; max-width: 640px;}

    .verdict {
        padding: 1.4rem 1.75rem;
        border-radius: 16px;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 1.25rem 0;
        display: flex; align-items: center; gap: 0.75rem;
        animation: slideDown 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .verdict-matched  {background:#ecfdf5; color:#064e3b; border-left:6px solid #10b981;}
    .verdict-low      {background:#fffbeb; color:#78350f; border-left:6px solid #f59e0b;}
    .verdict-none     {background:#fef2f2; color:#7f1d1d; border-left:6px solid #ef4444;}
    .verdict-unusable {background:#f1f5f9; color:#334155; border-left:6px solid #94a3b8;}
    @keyframes slideDown {
        from {opacity: 0; transform: translateY(-10px);}
        to   {opacity: 1; transform: translateY(0);}
    }

    .match-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    .match-card:hover {
        transform: translateY(-4px);
        border-color: #10b981;
        box-shadow: 0 14px 32px rgba(16,185,129,0.12);
    }
    .match-rank {font-size: 1.4rem; margin-bottom: 0.4rem;}
    .match-score {font-size: 1.9rem; font-weight: 800; color: #10b981; line-height: 1; letter-spacing: -0.03em;}
    .match-id {font-family: ui-monospace, "SF Mono", monospace; color: #64748b; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 0.5rem;}
    .match-bar {height: 6px; background: #e2e8f0; border-radius: 3px; margin-top: 0.7rem; overflow: hidden;}
    .match-bar-fill {height: 100%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 3px;}

    .info-strip {background:#f0fdf4; border-left:4px solid #10b981; border-radius: 10px; padding: 0.85rem 1rem; margin: 0.75rem 0; font-size: 0.9rem; color: #064e3b;}
    .warn-strip {background:#fffbeb; border-left:4px solid #f59e0b; border-radius: 10px; padding: 0.85rem 1rem; margin: 0.75rem 0; font-size: 0.9rem; color: #78350f;}

    .stButton > button {border-radius: 10px; font-weight: 600; padding: 0.55rem 1.1rem; border: 1px solid #e2e8f0; transition: all 0.15s ease;}
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        border: none; color: white;
        box-shadow: 0 4px 14px rgba(16,185,129,0.3);
    }
    .stButton > button[kind="primary"]:hover {transform: translateY(-1px); box-shadow: 0 8px 20px rgba(16,185,129,0.4);}

    [data-testid="stFileUploader"] {
        background: #f8fafc;
        border: 2px dashed #cbd5e1;
        border-radius: 14px;
        padding: 0.75rem;
        transition: all 0.2s;
    }
    [data-testid="stFileUploader"]:hover {border-color: #10b981; background: #ecfdf5;}

    hr {border:none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0;}
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle, emoji="🐄"):
    st.markdown(f"""
    <div class="hero">
      <div class="hero-inner">
        <h1>{emoji} {title}</h1>
        <p>{subtitle}</p>
      </div>
    </div>
    """, unsafe_allow_html=True)


def verdict_banner(status, cow_id=None, score=None):
    if status == "high_confidence":
        st.markdown(f'<div class="verdict verdict-matched">✅ MATCHED &nbsp;·&nbsp; Cow #{cow_id} &nbsp;·&nbsp; {score*100:.1f}%</div>', unsafe_allow_html=True)
    elif status == "low_confidence":
        st.markdown('<div class="verdict verdict-low">⚠️ LOW CONFIDENCE — MANUAL REVIEW REQUIRED</div>', unsafe_allow_html=True)
    elif status == "no_match":
        st.markdown('<div class="verdict verdict-none">❌ NO MATCH FOUND</div>', unsafe_allow_html=True)
    elif status == "inconsistent_images":
        st.markdown('<div class="verdict verdict-none">🚫 INCONSISTENT PHOTOS — Images do not match the same cow</div>', unsafe_allow_html=True)
    elif status == "invalid_image":
        st.markdown('<div class="verdict verdict-none">❌ INVALID IMAGE — Please upload a clear cattle muzzle photo</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="verdict verdict-unusable">⚪ CANNOT VERIFY — image unusable</div>', unsafe_allow_html=True)


def match_card(cow_id, score, image_path=None, rank=1):
    medals = ["🥇", "🥈", "🥉"]
    if image_path:
        img_html = f'<img src="{image_path}" style="width:100%;height:120px;object-fit:cover;border-radius:10px;margin-bottom:0.6rem;"/>'
    else:
        img_html = '<div style="height:120px;background:#f1f5f9;border-radius:10px;margin-bottom:0.6rem;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:0.8rem;">no image</div>'
    pct = score * 100
    st.markdown(f"""
    <div class="match-card">
      <div class="match-rank">{medals[rank-1] if rank <= 3 else "•"}</div>
      {img_html}
      <div class="match-score">{pct:.1f}%</div>
      <div class="match-id">Cow #{cow_id}</div>
      <div class="match-bar"><div class="match-bar-fill" style="width:{min(pct,100)}%;"></div></div>
    </div>
    """, unsafe_allow_html=True)


def info_strip(text):
    st.markdown(f'<div class="info-strip">{text}</div>', unsafe_allow_html=True)


def warn_strip(text):
    st.markdown(f'<div class="warn-strip">{text}</div>', unsafe_allow_html=True)
    