"""Shared UI layer for PashuPrint: design tokens, page chrome and components.

Every page goes through setup_page() so the look, navigation bar and login
state are identical everywhere. Nothing in here touches the database or the
ML code -- it only renders what the pages hand it.
"""

import base64
import os
from datetime import datetime, timezone
from html import escape
from io import BytesIO

import streamlit as st

# (key, label, page path, icon, href Streamlit renders for the link)
NAV_ITEMS = [
    ("home", "Home", "app.py", "🏠", ""),
    ("register", "Register", "pages/1_Register.py", "📝", "Register"),
    ("verify", "Verify", "pages/2_Verify.py", "🔍", "Verify"),
    ("passport", "Passport", "pages/4_Passport.py", "🪪", "Passport"),
    ("fraud", "Fraud", "pages/5_Fraud.py", "📊", "Fraud"),
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --g900:#022c22; --g800:#064e3b; --g700:#047857; --g600:#059669;
  --e500:#10b981; --e400:#34d399; --e100:#d1fae5; --e50:#ecfdf5;
  --s900:#0f172a; --s700:#334155; --s600:#475569; --s500:#64748b;
  --s400:#94a3b8; --s300:#cbd5e1; --s200:#e2e8f0; --s100:#f1f5f9; --s50:#f8fafc;
  --a700:#b45309; --a600:#d97706; --a500:#f59e0b; --a100:#fef3c7; --a50:#fffbeb;
  --r800:#991b1b; --r700:#b91c1c; --r600:#dc2626; --r100:#fee2e2; --r50:#fef2f2;
  --shadow:0 1px 2px rgba(15,23,42,.04), 0 4px 16px rgba(15,23,42,.05);
}

/* ---------- chrome & base ---------- */
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none !important;}
html, body, .stApp, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--s900);
}
.stApp {background: var(--s50);}
.block-container {padding-top: 1rem !important; padding-bottom: 4rem !important; max-width: 1180px !important;}
h1, h2, h3, h4 {color: var(--g900); letter-spacing: -0.02em;}
hr {border:none; border-top:1px solid var(--s200); margin:1.5rem 0;}
[data-testid="stElementContainer"] {margin-bottom: 0;}

/* ---------- top navigation ---------- */
.st-key-topnav {
  background:#fff; border:1px solid var(--s200); border-radius:16px;
  padding:.45rem .9rem; margin-bottom:1.25rem; box-shadow:var(--shadow);
}
.brand {display:flex; align-items:center; gap:.55rem; font-weight:800; font-size:1.15rem; color:var(--g900); letter-spacing:-.02em;}
.brand-mark {width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,var(--g900),var(--g700));
  display:flex; align-items:center; justify-content:center; font-size:1.05rem;}
.brand b {color:var(--e500); font-weight:800;}
[data-testid="stPageLink-NavLink"] {
  border-radius:10px; padding:.45rem .6rem; white-space:nowrap; color:var(--s600); font-weight:600; font-size:.9rem;
  justify-content:center; border-bottom:2px solid transparent;
}
[data-testid="stPageLink-NavLink"]:hover {background:var(--s100); color:var(--g900);}
[data-testid="stPageLink-NavLink"], [data-testid="stPageLink-NavLink"] * {overflow:visible !important; text-overflow:clip !important; white-space:nowrap !important;}
.st-key-emptycta {display:flex; justify-content:center; margin:-.25rem 0 1.5rem 0;}
.st-key-emptycta [data-testid="stPageLink-NavLink"] {background:var(--g900); color:#fff; padding:.7rem 1.6rem; border-radius:12px; box-shadow:0 6px 18px -6px rgba(2,44,34,.55);}
.st-key-emptycta [data-testid="stPageLink-NavLink"]:hover {background:var(--g700);}
.st-key-emptycta [data-testid="stPageLink-NavLink"] p, .st-key-emptycta [data-testid="stPageLink-NavLink"] span {color:#fff !important; font-weight:700;}
[data-testid="stPageLink-NavLink"] p {font-weight:inherit; font-size:.9rem; margin:0;}
.user-chip {display:inline-flex; align-items:center; gap:.5rem; background:var(--s100); border:1px solid var(--s200);
  border-radius:999px; padding:.35rem .85rem; font-size:.82rem; font-weight:600; color:var(--s700); white-space:nowrap;}
.user-chip .dot {width:8px; height:8px; border-radius:50%; background:var(--e500); box-shadow:0 0 0 3px var(--e100);}
.user-chip.out .dot {background:var(--s400); box-shadow:0 0 0 3px var(--s200);}
.user-chip em {font-style:normal; color:var(--s500); font-weight:500; text-transform:capitalize;}

/* ---------- page header ---------- */
.ph {background:linear-gradient(120deg,var(--g900) 0%,var(--g800) 70%,var(--g700) 100%);
  border-radius:20px; padding:1.6rem 2rem; color:#fff; display:flex; align-items:center; gap:1.1rem; margin-bottom:1.5rem;
  position:relative; overflow:hidden;}
.ph::after {content:""; position:absolute; right:-80px; top:-120px; width:320px; height:320px; border-radius:50%;
  background:radial-gradient(circle,rgba(52,211,153,.35),transparent 65%);}
.ph-icon {width:52px; height:52px; border-radius:14px; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.2);
  display:flex; align-items:center; justify-content:center; font-size:1.6rem; flex:none; position:relative; z-index:1;}
.ph-text {position:relative; z-index:1;}
.ph-eyebrow {font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--e400); margin-bottom:.15rem;}
.ph h1 {font-size:1.75rem; font-weight:800; color:#fff; margin:0; letter-spacing:-.02em; line-height:1.2; padding:0;}
.ph p {color:#a7f3d0; font-size:.95rem; margin:.25rem 0 0 0; max-width:680px; line-height:1.5;}

/* ---------- landing hero ---------- */
.hero {background:linear-gradient(135deg,var(--g900) 0%,var(--g800) 50%,var(--g700) 100%); border-radius:24px;
  padding:3.25rem 3rem; color:#fff; position:relative; overflow:hidden; margin-bottom:1.5rem;}
.hero::before {content:""; position:absolute; top:-150px; right:-120px; width:460px; height:460px; border-radius:50%;
  background:radial-gradient(circle,rgba(52,211,153,.5) 0%,transparent 65%); filter:blur(24px);}
.hero-inner {position:relative; z-index:1;}
.hero .eyebrow {display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--e400); border:1px solid rgba(52,211,153,.4); border-radius:999px; padding:.3rem .8rem; margin-bottom:1rem;}
.hero h1 {font-size:3.1rem; font-weight:800; color:#fff; letter-spacing:-.035em; margin:0 0 .75rem 0; line-height:1.08; padding:0;}
.hero h1 .accent {color:var(--e400);}
.hero p {color:#d1fae5; font-size:1.1rem; max-width:640px; line-height:1.6; margin:0;}
.flow {display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1.75rem;}
.flow-chip {background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18); padding:.4rem .9rem; border-radius:10px;
  font-size:.88rem; color:#ecfdf5; font-weight:500;}

/* ---------- cards, stats, sections ---------- */
.card {background:#fff; border:1px solid var(--s200); border-radius:16px; padding:1.4rem 1.5rem; box-shadow:var(--shadow);}
.sec-title {font-size:1.25rem; font-weight:800; color:var(--g900); margin:2rem 0 .25rem 0; letter-spacing:-.02em;}
.sec-sub {color:var(--s500); font-size:.92rem; margin:0 0 1.1rem 0;}
.stats {display:grid; gap:1rem; margin:0 0 1rem 0;}
.stat {background:#fff; border:1px solid var(--s200); border-radius:16px; padding:1.15rem 1.25rem; box-shadow:var(--shadow); border-top:3px solid var(--e500);}
.stat.red {border-top-color:var(--r600);} .stat.amber {border-top-color:var(--a500);} .stat.grey {border-top-color:var(--s400);} .stat.dark {border-top-color:var(--g900);}
.stat-value {font-size:1.9rem; font-weight:800; color:var(--g900); line-height:1.1; letter-spacing:-.03em;}
.stat-label {font-size:.72rem; color:var(--s500); text-transform:uppercase; letter-spacing:.09em; margin-top:.4rem; font-weight:600;}
.stat-note {font-size:.75rem; color:var(--s500); margin-top:.3rem; line-height:1.4;}
.features {display:grid; grid-template-columns:repeat(3,1fr); gap:1.1rem;}
.feature {background:#fff; border:1px solid var(--s200); border-radius:16px; padding:1.5rem; box-shadow:var(--shadow);}
.feature-icon {width:44px; height:44px; background:var(--e50); border:1px solid var(--e100); border-radius:12px;
  display:flex; align-items:center; justify-content:center; font-size:1.3rem; margin-bottom:.9rem;}
.feature-title {font-weight:700; font-size:1.02rem; color:var(--g900); margin:0 0 .35rem 0;}
.feature-text {color:var(--s600); font-size:.9rem; line-height:1.55; margin:0;}

/* ---------- callouts / empty state ---------- */
.callout {display:flex; gap:.8rem; align-items:flex-start; border-radius:12px; padding:.9rem 1.1rem; margin:.75rem 0;
  font-size:.92rem; line-height:1.5; border:1px solid; border-left-width:5px;}
.callout .ci {font-size:1.1rem; line-height:1.4;}
.callout .ct {font-weight:700; margin-bottom:.1rem;}
.callout.info {background:var(--e50); border-color:var(--e100); border-left-color:var(--e500); color:var(--g800);}
.callout.success {background:var(--e50); border-color:var(--e100); border-left-color:var(--g700); color:var(--g800);}
.callout.warn {background:var(--a50); border-color:var(--a100); border-left-color:var(--a500); color:#78350f;}
.callout.danger {background:var(--r50); border-color:var(--r100); border-left-color:var(--r600); color:var(--r800);}
.callout.neutral {background:var(--s100); border-color:var(--s200); border-left-color:var(--s400); color:var(--s700);}
.empty {background:#fff; border:2px dashed var(--s300); border-radius:18px; text-align:center; padding:3rem 2rem; margin:1rem 0;}
.empty .ei {font-size:2.4rem; margin-bottom:.5rem;}
.empty .et {font-size:1.2rem; font-weight:800; color:var(--g900); margin-bottom:.35rem;}
.empty .ex {color:var(--s500); font-size:.95rem; max-width:460px; margin:0 auto; line-height:1.55;}

/* ---------- stepper ---------- */
.stepper {display:flex; align-items:center; gap:.6rem; margin:0 0 1.25rem 0; flex-wrap:wrap;}
.step {display:flex; align-items:center; gap:.55rem; font-size:.88rem; font-weight:600; color:var(--s500);}
.step .n {width:28px; height:28px; border-radius:50%; background:var(--s200); color:var(--s500); display:flex;
  align-items:center; justify-content:center; font-size:.8rem; font-weight:700;}
.step.active {color:var(--g900);} .step.active .n {background:var(--g900); color:#fff; box-shadow:0 0 0 4px var(--e100);}
.step.done {color:var(--g700);} .step.done .n {background:var(--e500); color:#fff;}
.step-line {flex:0 0 40px; height:2px; background:var(--s200);} .step-line.done {background:var(--e500);}

/* ---------- photo grid ---------- */
.pgrid {display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:.8rem; margin:.5rem 0 1rem 0;}
.pitem {background:#fff; border:1px solid var(--s200); border-radius:12px; overflow:hidden; box-shadow:var(--shadow);}
.pitem img {width:100%; aspect-ratio:1/1; object-fit:cover; display:block;}
.pitem .pcap {font-size:.75rem; font-weight:600; color:var(--s600); padding:.4rem .6rem; border-top:1px solid var(--s100);}
.noimg {aspect-ratio:1/1; width:100%; background:var(--s100); color:var(--s400); display:flex; align-items:center;
  justify-content:center; font-size:.78rem; font-weight:500;}

/* ---------- verdict banner (the money shot) ---------- */
.vb {display:flex; align-items:center; gap:1.75rem; border-radius:22px; padding:2.25rem 2.5rem; margin:.5rem 0 1.5rem 0; color:#fff;
  position:relative; overflow:hidden; box-shadow:0 20px 50px -18px rgba(15,23,42,.45); animation:vbIn .5s cubic-bezier(.16,1,.3,1);}
.vb::after {content:""; position:absolute; right:-90px; top:-130px; width:380px; height:380px; border-radius:50%; background:rgba(255,255,255,.09);}
.vb-icon {flex:none; width:84px; height:84px; border-radius:50%; background:rgba(255,255,255,.18); border:3px solid rgba(255,255,255,.55);
  display:flex; align-items:center; justify-content:center; font-size:2.6rem; font-weight:800; z-index:1;}
.vb-main {flex:1; z-index:1; min-width:0;}
.vb-eyebrow {font-size:.75rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase; opacity:.85; margin-bottom:.25rem;}
.vb-title {font-size:2.7rem; font-weight:800; letter-spacing:-.03em; line-height:1.05;}
.vb-sub {font-size:1.02rem; margin-top:.5rem; opacity:.95; line-height:1.5; max-width:640px;}
.vb-score {flex:none; text-align:right; z-index:1; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.3);
  border-radius:16px; padding:.9rem 1.4rem;}
.vb-score-num {font-size:2.5rem; font-weight:800; letter-spacing:-.03em; line-height:1;}
.vb-score-lab {font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; opacity:.85; margin-top:.3rem; font-weight:600;}
.vb-matched {background:linear-gradient(120deg,#022c22 0%,#047857 100%);}
.vb-low {background:linear-gradient(120deg,#92400e 0%,#d97706 100%); border:3px solid #fbbf24;}
.vb-low .vb-icon {animation:vbPulse 1.6s ease-in-out infinite;}
.vb-none {background:linear-gradient(120deg,#7f1d1d 0%,#dc2626 100%);}
.vb-unusable {background:linear-gradient(120deg,#334155 0%,#64748b 100%);}
@keyframes vbIn {from {opacity:0; transform:translateY(-12px) scale(.985);} to {opacity:1; transform:none;}}
@keyframes vbPulse {0%,100% {box-shadow:0 0 0 0 rgba(254,243,199,.7);} 50% {box-shadow:0 0 0 14px rgba(254,243,199,0);}}

/* ---------- match cards ---------- */
.mc {display:flex; gap:1rem; background:#fff; border:1px solid var(--s200); border-radius:16px; padding:.9rem; box-shadow:var(--shadow); align-items:stretch;}
.mc.top {border:2px solid var(--e500);}
.mc-photo {flex:none; width:118px; border-radius:12px; overflow:hidden; background:var(--s100);}
.mc-photo img, .mc-photo .noimg {width:100%; height:100%; min-height:118px; object-fit:cover; display:block; aspect-ratio:auto;}
.mc-body {flex:1; min-width:0; display:flex; flex-direction:column; justify-content:center;}
.mc-rank {font-size:.68rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--s500);}
.mc.top .mc-rank {color:var(--g700);}
.mc-id {font-family:ui-monospace,"SF Mono",Consolas,monospace; font-weight:700; font-size:1.05rem; color:var(--g900); margin:.15rem 0 .35rem 0;}
.mc-score {font-size:2rem; font-weight:800; line-height:1; letter-spacing:-.03em; color:var(--g900);}
.mc-score small {font-size:1rem; font-weight:700;}
.mc-lab {font-size:.7rem; color:var(--s500); text-transform:uppercase; letter-spacing:.09em; font-weight:600; margin-top:.2rem;}
.mc-bar {height:6px; background:var(--s200); border-radius:3px; margin-top:.6rem; overflow:hidden;}
.mc-bar i {display:block; height:100%; border-radius:3px; background:var(--e500);}
.mc.warn .mc-bar i {background:var(--a500);} .mc.muted .mc-bar i {background:var(--s400);}

/* ---------- fraud duplicate card ---------- */
.fraud {background:#fff; border:2px solid var(--r600); border-radius:20px; overflow:hidden; margin:1rem 0; box-shadow:0 18px 44px -20px rgba(220,38,38,.5);}
.fraud-head {background:linear-gradient(120deg,var(--r800),var(--r600)); color:#fff; padding:1.1rem 1.6rem; display:flex; align-items:center; gap:.9rem;}
.fraud-head .fi {font-size:1.8rem;}
.fraud-head .ft {font-size:1.25rem; font-weight:800; letter-spacing:-.01em;}
.fraud-head .fs {font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; opacity:.85; font-weight:700;}
.fraud-body {display:grid; grid-template-columns:1fr 1fr 1fr; gap:1.25rem; padding:1.4rem 1.6rem; align-items:stretch;}
.fraud-photo {border:1px solid var(--s200); border-radius:14px; overflow:hidden;}
.fraud-photo img, .fraud-photo .noimg {width:100%; aspect-ratio:4/3; object-fit:cover; display:block;}
.fraud-photo .pcap {font-size:.78rem; font-weight:600; color:var(--s600); padding:.5rem .8rem; border-top:1px solid var(--s100);}
.fraud-facts {display:flex; flex-direction:column; justify-content:center; gap:.4rem;}
.fraud-facts .big {font-size:2.6rem; font-weight:800; color:var(--r700); line-height:1; letter-spacing:-.03em;}
.fraud-facts .lab {font-size:.7rem; text-transform:uppercase; letter-spacing:.12em; color:var(--s500); font-weight:600;}
.fraud-facts .cid {font-family:ui-monospace,Consolas,monospace; font-weight:700; font-size:1.15rem; color:var(--g900);}
.fraud-foot {background:var(--r50); border-top:1px solid var(--r100); color:var(--r800); padding:.85rem 1.6rem; font-size:.9rem; line-height:1.5;}

/* ---------- success card ---------- */
.donecard {background:#fff; border:2px solid var(--e500); border-radius:22px; overflow:hidden; box-shadow:0 20px 50px -22px rgba(16,185,129,.55); margin:.5rem 0 1.25rem 0;}
.done-head {background:linear-gradient(120deg,var(--g900),var(--g700)); color:#fff; padding:1.6rem 2rem; display:flex; align-items:center; gap:1.2rem;}
.done-head .ok {width:56px; height:56px; border-radius:50%; background:rgba(255,255,255,.18); border:2px solid rgba(255,255,255,.5);
  display:flex; align-items:center; justify-content:center; font-size:1.7rem; font-weight:800;}
.done-head .dt {font-size:.75rem; letter-spacing:.14em; text-transform:uppercase; opacity:.85; font-weight:700;}
.done-head .dm {font-size:1.5rem; font-weight:800; letter-spacing:-.02em;}
.done-body {padding:1.6rem 2rem; display:grid; grid-template-columns:auto 1fr; gap:2rem; align-items:center;}
.done-id {font-family:ui-monospace,Consolas,monospace; font-size:3rem; font-weight:800; color:var(--g900); letter-spacing:-.02em; line-height:1;}
.done-id-lab {font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--s500); font-weight:700; margin-bottom:.35rem;}
.kv {display:grid; grid-template-columns:repeat(2,1fr); gap:.9rem 1.5rem;}
.kv .k {font-size:.68rem; letter-spacing:.11em; text-transform:uppercase; color:var(--s500); font-weight:700;}
.kv .v {font-size:1rem; font-weight:600; color:var(--s900); margin-top:.1rem;}

/* ---------- passport ---------- */
.pp {background:#fff; border:1px solid var(--s300); border-radius:20px; overflow:hidden; box-shadow:0 18px 44px -24px rgba(2,44,34,.5); margin-bottom:1.5rem;}
.pp-head {background:linear-gradient(120deg,var(--g900),var(--g800)); color:#fff; padding:1rem 1.75rem; display:flex; justify-content:space-between; align-items:center;}
.pp-head .t {font-size:.78rem; font-weight:700; letter-spacing:.2em; text-transform:uppercase;}
.pp-head .t b {color:var(--e400);}
.pp-head .n {font-family:ui-monospace,Consolas,monospace; font-size:.85rem; color:#a7f3d0;}
.pp-body {display:grid; grid-template-columns:260px 1fr; gap:2rem; padding:1.75rem; position:relative;}
.pp-photo {border:1px solid var(--s200); border-radius:14px; overflow:hidden; align-self:start;}
.pp-photo img, .pp-photo .noimg {width:100%; aspect-ratio:1/1; object-fit:cover; display:block;}
.pp-photo .pcap {font-size:.72rem; color:var(--s500); text-align:center; padding:.5rem; border-top:1px solid var(--s100); font-weight:600; letter-spacing:.06em; text-transform:uppercase;}
.pp-id-lab {font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:var(--s500); font-weight:700;}
.pp-id {font-family:ui-monospace,Consolas,monospace; font-size:2.2rem; font-weight:800; color:var(--g900); letter-spacing:-.02em; line-height:1.1; margin-bottom:1.25rem;}
.pp-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:1.1rem 1.5rem;}
.pp-grid .k {font-size:.68rem; letter-spacing:.11em; text-transform:uppercase; color:var(--s500); font-weight:700;}
.pp-grid .v {font-size:1.05rem; font-weight:600; color:var(--s900); margin-top:.15rem; word-break:break-word;}
.pill {display:inline-block; padding:.2rem .7rem; border-radius:999px; font-size:.78rem; font-weight:700; letter-spacing:.02em;}
.pill.good {background:var(--e100); color:var(--g800);} .pill.warn {background:var(--a100); color:var(--a700);}
.pill.bad {background:var(--r100); color:var(--r700);} .pill.muted {background:var(--s200); color:var(--s600);}
.pp-foot {display:flex; justify-content:space-between; align-items:flex-end; padding:1rem 1.75rem 1.4rem; border-top:1px dashed var(--s300); background:var(--s50);}
.pp-foot .note {font-size:.78rem; color:var(--s500); line-height:1.5; max-width:520px;}
.pp-qr {text-align:center;} .pp-qr img {width:112px; height:112px; border:1px solid var(--s200); border-radius:10px; padding:4px; background:#fff; display:block;}
.pp-qr .cap {font-size:.66rem; letter-spacing:.12em; text-transform:uppercase; color:var(--s500); font-weight:700; margin-top:.35rem;}

/* ---------- timeline ---------- */
.tl {position:relative; margin:.5rem 0 1rem 0; padding-left:1.6rem;}
.tl::before {content:""; position:absolute; left:.5rem; top:.4rem; bottom:.4rem; width:2px; background:var(--s200);}
.tl-item {position:relative; background:#fff; border:1px solid var(--s200); border-radius:12px; padding:.8rem 1.1rem; margin-bottom:.7rem;
  display:flex; justify-content:space-between; align-items:center; gap:1rem; box-shadow:var(--shadow);}
.tl-item::before {content:""; position:absolute; left:-1.42rem; top:50%; transform:translateY(-50%); width:12px; height:12px; border-radius:50%;
  background:var(--e500); border:3px solid #fff; box-shadow:0 0 0 2px var(--e500);}
.tl-item.warn::before {background:var(--a500); box-shadow:0 0 0 2px var(--a500);}
.tl-item.bad::before {background:var(--r600); box-shadow:0 0 0 2px var(--r600);}
.tl-item.muted::before {background:var(--s400); box-shadow:0 0 0 2px var(--s400);}
.tl-title {font-weight:700; color:var(--g900); font-size:.95rem;}
.tl-sub {font-size:.8rem; color:var(--s500); margin-top:.1rem;}
.tl-score {font-family:ui-monospace,Consolas,monospace; font-weight:700; color:var(--s700); font-size:.9rem; white-space:nowrap;}

/* ---------- data table (fraud) ---------- */
.dt-wrap {background:#fff; border:1px solid var(--s200); border-radius:16px; overflow:hidden; box-shadow:var(--shadow);}
table.dt {width:100%; border-collapse:collapse; font-size:.88rem;}
table.dt th {text-align:left; background:var(--s50); color:var(--s500); font-size:.68rem; letter-spacing:.1em; text-transform:uppercase;
  font-weight:700; padding:.75rem 1rem; border-bottom:1px solid var(--s200);}
table.dt td {padding:.8rem 1rem; border-bottom:1px solid var(--s100); color:var(--s700); vertical-align:middle;}
table.dt tr:last-child td {border-bottom:none;}
table.dt tr.sev-red td {background:var(--r50);} table.dt tr.sev-red td:first-child {box-shadow:inset 4px 0 0 var(--r600);}
table.dt tr.sev-amber td {background:var(--a50);} table.dt tr.sev-amber td:first-child {box-shadow:inset 4px 0 0 var(--a500);}
table.dt tr.sev-grey td {background:#fff;} table.dt tr.sev-grey td:first-child {box-shadow:inset 4px 0 0 var(--s400);}
table.dt td.mono {font-family:ui-monospace,Consolas,monospace; font-weight:700; color:var(--g900);}
table.dt td.ts {white-space:nowrap; color:var(--s500);}
.badge {display:inline-block; padding:.22rem .65rem; border-radius:999px; font-size:.74rem; font-weight:700; white-space:nowrap;}
.badge.red {background:var(--r100); color:var(--r700);} .badge.amber {background:var(--a100); color:var(--a700);} .badge.grey {background:var(--s200); color:var(--s600);}

/* ---------- streamlit widgets ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {background:var(--g900); border:1px solid var(--g900); color:#fff; border-radius:12px; font-weight:700;
  padding:.65rem 1.2rem; box-shadow:0 6px 18px -6px rgba(2,44,34,.55); transition:all .15s ease;}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {background:var(--g700); border-color:var(--g700); color:#fff; transform:translateY(-1px);}
[data-testid="stBaseButton-secondary"] {background:#fff; border:1px solid var(--s300); color:var(--g900); border-radius:12px; font-weight:600; padding:.65rem 1.2rem; transition:all .15s ease;}
[data-testid="stBaseButton-secondary"]:hover {border-color:var(--e500); color:var(--g800); background:var(--e50);}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-secondary"] p {font-size:.92rem;}

[data-testid="stFileUploaderDropzone"] {
  background:linear-gradient(180deg,#f0fdf4,#ecfdf5); border:2px dashed var(--e500); border-radius:20px;
  min-height:220px; display:flex !important; flex-direction:column; align-items:center; justify-content:center; text-align:center;
  padding:2rem; gap:.9rem; transition:all .2s;}
[data-testid="stFileUploaderDropzone"]::before {content:"📸  Drop muzzle photos here"; font-size:1.4rem; font-weight:800; color:var(--g900); letter-spacing:-.02em;}
[data-testid="stFileUploaderDropzone"]:hover {background:#d1fae5; border-color:var(--g700);}
[data-testid="stFileUploaderDropzone"] button {background:var(--g900) !important; color:#fff !important; border:1px solid var(--g900) !important; border-radius:12px; padding:.6rem 1.6rem; font-weight:700;}
[data-testid="stFileUploaderDropzone"] button:hover {background:var(--g700) !important; border-color:var(--g700) !important;}
[data-testid="stFileUploaderDropzone"] button * {color:#fff !important;}
[data-testid="stFileUploaderDropzoneInstructions"] {flex-direction:column; align-items:center; text-align:center;}
[data-testid="stFileUploaderDropzoneInstructions"] span {font-size:.85rem; font-weight:500; color:var(--s500);}
[data-baseweb="tag"] {background:var(--e50) !important; border:1px solid var(--e100); border-radius:8px !important;}
[data-baseweb="tag"] span {color:var(--g800) !important; font-weight:600;}

[data-testid="stWidgetLabel"] p {font-weight:600; color:var(--s700); font-size:.85rem;}
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {border-radius:10px !important;}
[data-baseweb="input"], [data-baseweb="select"] > div {background:#fff !important; border-color:var(--s300) !important;}
[data-testid="stForm"] {border:none; padding:0; background:transparent;}
.st-key-logincard, .st-key-formcard, .st-key-chartcard {background:#fff; border:1px solid var(--s200); border-radius:18px; padding:1.5rem 1.6rem; box-shadow:var(--shadow);}
.login-title {font-size:1.35rem; font-weight:800; color:var(--g900); margin:0 0 .2rem 0;}
.login-sub {font-size:.9rem; color:var(--s500); margin:0 0 1rem 0;}
</style>
"""


# ---------------------------------------------------------------- helpers

def _h(html: str) -> str:
    """Flatten an HTML snippet so Markdown never treats indentation as a code block."""
    return " ".join(line.strip() for line in html.splitlines() if line.strip())


def html(snippet: str) -> None:
    st.markdown(_h(snippet), unsafe_allow_html=True)


def fmt_ts(value) -> str:
    """ISO-8601 string -> '19 Sep 2026, 14:32 UTC'."""
    try:
        d = datetime.fromisoformat(str(value))
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc)
        return d.strftime("%d %b %Y, %H:%M") + " UTC"
    except (ValueError, TypeError):
        return str(value) if value else "—"


@st.cache_data(show_spinner=False)
def _thumb_uri(path: str, mtime: float, max_px: int) -> str:
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def img_uri(path, max_px: int = 520):
    """Embeddable data-URI for a local image, or None if it can't be read.

    Browsers can't load local file paths, so images shown inside HTML cards
    have to be inlined."""
    if not path or not os.path.exists(path):
        return None
    try:
        return _thumb_uri(str(path), os.path.getmtime(path), max_px)
    except Exception:
        return None


def _img_or_placeholder(path, label="No photo on file", max_px=520) -> str:
    uri = img_uri(path, max_px)
    if uri:
        return f'<img src="{uri}" alt=""/>'
    return f'<div class="noimg">{escape(label)}</div>'


# ---------------------------------------------------------------- page chrome

def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def setup_page(title: str, icon: str, active: str, require_auth: bool = True):
    """First call on every page: config, theme, top nav and (optionally) the login gate."""
    st.set_page_config(page_title=f"{title} · PashuPrint", page_icon=icon, layout="wide",
                       initial_sidebar_state="collapsed")
    inject_css()
    if "user" not in st.session_state:
        st.session_state.user = None
    render_nav(active)
    if require_auth and not st.session_state.user:
        login_gate()
        st.stop()


def render_nav(active: str):
    user = st.session_state.get("user")
    href = next((h for k, _, _, _, h in NAV_ITEMS if k == active), None)
    if href is not None:
        st.markdown(
            f'<style>.st-key-topnav [data-testid="stPageLink-NavLink"][href="{href}"] '
            '{background:var(--e50) !important; border-bottom:2px solid var(--e500);} '
            f'.st-key-topnav [data-testid="stPageLink-NavLink"][href="{href}"] p '
            '{color:var(--g800) !important; font-weight:700 !important;}</style>',
            unsafe_allow_html=True,
        )
    with st.container(key="topnav"):
        cols = st.columns([1.45, 1.0, 1.1, 1.0, 1.25, 1.1, 3.1], vertical_alignment="center")
        with cols[0]:
            html('<div class="brand"><div class="brand-mark">🐄</div><span>Pashu<b>Print</b></span></div>')
        for col, (_, label, path, icon, _) in zip(cols[1:6], NAV_ITEMS):
            with col:
                st.page_link(path, label=label, icon=icon)
        with cols[6]:
            chip, action = st.columns([1.5, 1.05], vertical_alignment="center")
            with chip:
                if user:
                    html(f'<div style="text-align:right"><span class="user-chip"><span class="dot"></span>'
                         f'{escape(str(user["name"]))} <em>{escape(str(user["role"]))}</em></span></div>')
                else:
                    html('<div style="text-align:right"><span class="user-chip out"><span class="dot"></span>'
                         'Not signed in</span></div>')
            with action:
                if user:
                    if st.button("Sign out", key="nav_signout", use_container_width=True):
                        st.session_state.user = None
                        st.session_state.need_login = None
                        st.rerun()
                else:
                    if st.button("Sign in", key="nav_signin", type="primary", use_container_width=True):
                        st.session_state.need_login = "home"
                        if active != "home":
                            st.switch_page("app.py")
                        st.rerun()


def login_card(target=None):
    """Agent login form. `target` is a page path to open after signing in (None = stay and refresh)."""
    from utils.mock_backend import check_agent_login

    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        with st.container(key="logincard"):
            html('<div class="login-title">🔐 Agent sign-in</div>'
                 '<div class="login-sub">Access is limited to authorised vets and field surveyors.</div>')
            with st.form("login_form", border=False):
                agent_id = st.text_input("Agent ID", placeholder="vet01")
                password = st.text_input("Password", type="password", placeholder="••••")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submitted:
                result = check_agent_login(agent_id, password)
                if result["ok"]:
                    st.session_state.user = result
                    st.session_state.need_login = None
                    if target:
                        st.switch_page(target)
                    st.rerun()
                else:
                    callout("danger", "Those credentials weren't recognised. Check the Agent ID and password.",
                            title="Sign-in failed")


def login_gate():
    empty_state("🔒", "Sign in to continue",
                "This page is restricted to authorised agents. Sign in below to register, verify and review animals.")
    login_card()


def page_header(title: str, subtitle: str, icon: str = "🐄", eyebrow: str = "PashuPrint"):
    html(f'<div class="ph"><div class="ph-icon">{icon}</div><div class="ph-text">'
         f'<div class="ph-eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div></div>')


def hero(title, subtitle, emoji="🐄"):
    """Back-compat alias for page_header()."""
    page_header(title, subtitle, emoji)


# ---------------------------------------------------------------- generic components

def callout(kind: str, text: str, title: str = None):
    icons = {"info": "ℹ️", "success": "✅", "warn": "⚠️", "danger": "⛔", "neutral": "•"}
    t = f'<div class="ct">{escape(title)}</div>' if title else ""
    html(f'<div class="callout {kind}"><div class="ci">{icons.get(kind, "•")}</div><div>{t}{escape(text)}</div></div>')


def info_strip(text):
    callout("info", text)


def warn_strip(text):
    callout("warn", text)


def empty_state(icon: str, title: str, text: str, cta=None):
    """Friendly placeholder. cta = (page_path, label, icon) renders a button-styled link under it."""
    html(f'<div class="empty"><div class="ei">{icon}</div><div class="et">{escape(title)}</div><div class="ex">{escape(text)}</div></div>')
    if cta:
        with st.container(key="emptycta"):
            st.page_link(cta[0], label=cta[1], icon=cta[2])


def section(title: str, sub: str = ""):
    s = f'<div class="sec-sub">{escape(sub)}</div>' if sub else ""
    html(f'<div class="sec-title">{escape(title)}</div>{s}')


def stat_grid(items, cols=None):
    """items: dicts with value, label and optional note / tone (red|amber|grey|dark)."""
    cols = cols or len(items)
    cells = "".join(
        f'<div class="stat {it.get("tone", "")}"><div class="stat-value">{it["value"]}</div>'
        f'<div class="stat-label">{escape(it["label"])}</div>'
        + (f'<div class="stat-note">{escape(it["note"])}</div>' if it.get("note") else "")
        + "</div>"
        for it in items
    )
    html(f'<div class="stats" style="grid-template-columns:repeat({cols},1fr)">{cells}</div>')


def stepper(steps, current: int):
    parts = []
    for i, label in enumerate(steps):
        state = "done" if i < current else "active" if i == current else ""
        mark = "✓" if i < current else str(i + 1)
        parts.append(f'<div class="step {state}"><div class="n">{mark}</div>{escape(label)}</div>')
        if i < len(steps) - 1:
            parts.append(f'<div class="step-line {"done" if i < current else ""}"></div>')
    html(f'<div class="stepper">{"".join(parts)}</div>')


def photo_grid(paths, prefix="Photo"):
    cells = "".join(
        f'<div class="pitem">{_img_or_placeholder(p, "Unreadable", 360)}<div class="pcap">{escape(prefix)} {i + 1}</div></div>'
        for i, p in enumerate(paths)
    )
    html(f'<div class="pgrid">{cells}</div>')


# ---------------------------------------------------------------- verification components

_VERDICTS = {
    "high_confidence": ("vb-matched", "&#10003;", "Identity verified", "MATCHED"),
    "low_confidence": ("vb-low", "&#33;", "Action required", "LOW CONFIDENCE"),
    "no_match": ("vb-none", "&#10005;", "Verification failed", "NO MATCH"),
    "inconsistent_images": ("vb-none", "&#10005;", "Verification failed", "INCONSISTENT PHOTOS"),
    "invalid_image": ("vb-none", "&#10005;", "Verification failed", "INVALID IMAGE"),
}


def verdict_banner(status, cow_id=None, score=None):
    cls, icon, eyebrow, title = _VERDICTS.get(status, ("vb-unusable", "&#63;", "Inconclusive", "CANNOT VERIFY"))
    cid = escape(str(cow_id)) if cow_id else None

    if status == "high_confidence":
        sub = f"Animal <b>{cid}</b> is enrolled and the muzzle print matches the stored record."
    elif status == "low_confidence":
        best = f" Closest enrolled animal: <b>{cid}</b>." if cid else ""
        sub = f"The match is too weak to approve automatically.{best} Send to a human reviewer before any claim is processed — a fraud flag has been logged."
    elif status == "no_match":
        sub = "No enrolled animal matches these photos. This claim cannot be tied to a registered cow — a fraud flag has been logged."
    elif status == "inconsistent_images":
        sub = "The uploaded photos appear to show different animals. Retake all photos of a single cow — a fraud flag has been logged."
    elif status == "invalid_image":
        sub = "At least one photo is not a clear cattle muzzle. Upload clear, close-up muzzle photos."
    else:
        sub = "The images are too poor to analyse. Retake them, or fall back to the manual process."

    score_html = ""
    if score is not None and cow_id:
        score_html = f'<div class="vb-score"><div class="vb-score-num">{score * 100:.1f}%</div><div class="vb-score-lab">similarity</div></div>'

    html(f'<div class="vb {cls}"><div class="vb-icon">{icon}</div><div class="vb-main">'
         f'<div class="vb-eyebrow">{eyebrow}</div><div class="vb-title">{title}</div><div class="vb-sub">{sub}</div>'
         f'</div>{score_html}</div>')


def match_card(cow_id, score, image_path=None, rank=1, tone="good"):
    pct = score * 100
    cls = "top" if rank == 1 else ""
    if tone in ("warn", "muted"):
        cls += f" {tone}"
    label = "Best match" if rank == 1 else f"Match #{rank}"
    html(f'<div class="mc {cls}"><div class="mc-photo">{_img_or_placeholder(image_path, "No photo", 300)}</div>'
         f'<div class="mc-body"><div class="mc-rank">{label}</div><div class="mc-id">{escape(str(cow_id))}</div>'
         f'<div class="mc-score">{pct:.1f}<small>%</small></div><div class="mc-lab">similarity</div>'
         f'<div class="mc-bar"><i style="width:{min(max(pct, 0), 100):.1f}%"></i></div></div></div>')


def duplicate_card(uploaded_path, stored_path, cow_id, score=None, title="Duplicate registration blocked",
                   note=None, score_label="similarity"):
    """Red fraud-signal card: uploaded photo beside the already-enrolled one."""
    fact = (f'<div class="big">{score * 100:.1f}%</div><div class="lab">{escape(score_label)}</div>'
            if score is not None else "")
    note = note or "This animal is already enrolled. Registering it again would create a second policy on the same cow, so registration was refused and a fraud flag has been logged for review."
    html(f'<div class="fraud"><div class="fraud-head"><div class="fi">🚨</div><div>'
         f'<div class="fs">Fraud signal</div><div class="ft">{escape(title)}</div></div></div>'
         f'<div class="fraud-body">'
         f'<div class="fraud-photo">{_img_or_placeholder(uploaded_path, "Photo unavailable", 640)}<div class="pcap">Photo you uploaded</div></div>'
         f'<div class="fraud-photo">{_img_or_placeholder(stored_path, "Stored photo unavailable", 640)}<div class="pcap">Already on file · {escape(str(cow_id))}</div></div>'
         f'<div class="fraud-facts"><div class="lab">Matched record</div><div class="cid">{escape(str(cow_id))}</div>{fact}</div>'
         f'</div><div class="fraud-foot">{escape(note)}</div></div>')
