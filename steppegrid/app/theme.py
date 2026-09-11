"""Central visual design tokens and global Streamlit styling."""

from __future__ import annotations

import streamlit as st


COLORS = {
    "primary": "#0F6B5C",
    "primary_dark": "#0B2730",
    "wind": "#3E88B5",
    "solar": "#D89D2B",
    "storage": "#7665A7",
    "served": "#218265",
    "unmet": "#C64D47",
    "curtailment": "#B66C2F",
    "neutral": "#627078",
    "muted": "#718087",
    "success": "#218265",
    "caution": "#B4771B",
    "critical": "#C64D47",
    "surface": "#FFFFFF",
    "surface_alt": "#ECEEEA",
    "border": "#D6DBD6",
    "text": "#14262D",
    "featured_site": "#D89D2B",
}


GLOBAL_CSS = """
<style>
:root {
  --sg-ink:#0B2730;
  --sg-ink-soft:#183A43;
  --sg-primary:#0F6B5C;
  --sg-primary-bright:#168573;
  --sg-featured-site:#D89D2B;
  --sg-wind:#3E88B5;
  --sg-solar:#D89D2B;
  --sg-storage:#7665A7;
  --sg-unmet:#C64D47;
  --sg-curtail:#B66C2F;
  --sg-text:#14262D;
  --sg-muted:#617078;
  --sg-border:#D6DBD6;
  --sg-surface:#FFFFFF;
  --sg-surface-alt:#ECEEEA;
  --sg-canvas:#F4F3EE;
}

.stApp {
  color:var(--sg-text);
  background:var(--sg-canvas);
}
.block-container {
  max-width:1200px;
  padding-top:1.75rem;
  padding-bottom:4.5rem;
}
p, li, label, [data-testid="stMarkdownContainer"] { line-height:1.55; }
h1, h2, h3 {
  color:var(--sg-text);
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  letter-spacing:-.035em;
}
h1 { font-size:2.45rem!important; line-height:1.05!important; font-weight:720!important; }
h2 { font-size:1.35rem!important; font-weight:700!important; }
h3 { font-weight:690!important; }

/* Controls */
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {
  min-height:2.65rem;
  border:1px solid #C8D0CB;
  border-radius:6px;
  background:#FFFFFF;
  color:var(--sg-text);
  font-weight:650;
  box-shadow:none;
  transition:background .15s ease,border-color .15s ease,transform .15s ease;
}
[data-testid="stButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {
  border-color:var(--sg-primary);
  background:#F7FAF8;
  color:var(--sg-primary);
  transform:translateY(-1px);
}
[data-testid="stButton"] button:focus-visible,
[data-testid="stDownloadButton"] button:focus-visible {
  outline:3px solid rgba(216,157,43,.34);
  outline-offset:2px;
}
[data-testid="stButton"] button[kind="primary"] {
  border-color:var(--sg-primary);
  background:var(--sg-primary);
  color:#FFFFFF;
}
[data-testid="stButton"] button[kind="primary"]:hover {
  border-color:var(--sg-primary-bright);
  background:var(--sg-primary-bright);
  color:#FFFFFF;
}
[data-baseweb="select"] > div,
[data-testid="stDateInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stFileUploaderDropzone"] {
  border-radius:6px!important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap:1.4rem;
  border-bottom:1px solid var(--sg-border);
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  padding-left:0;
  padding-right:0;
  font-weight:650;
}

/* Sidebar */
[data-testid="stSidebar"] {
  border-right:0;
  background:var(--sg-ink);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top:1.15rem; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#AFC0C5; }
[data-testid="stSidebar"] hr { border-color:#29464E; }
.sg-brand {
  display:flex;
  align-items:center;
  gap:.75rem;
  margin:.1rem 0 1rem;
  padding:0 .05rem;
}
.sg-brand__mark {
  display:grid;
  place-items:center;
  width:2.45rem;
  height:2.45rem;
  border:1px solid #E4B95C;
  background:#E4B95C;
  color:var(--sg-ink);
  font-size:.75rem;
  font-weight:850;
  letter-spacing:.08em;
}
.sg-brand__name { color:#FFFFFF; font-size:1.08rem; font-weight:760; letter-spacing:-.02em; }
.sg-brand__sub { display:block; color:#8FA6AD; font-size:.66rem; font-weight:650; letter-spacing:.1em; text-transform:uppercase; }
.sg-mode-label,
.sg-nav-group {
  color:#80979E;
  font-size:.64rem;
  font-weight:800;
  letter-spacing:.13em;
  text-transform:uppercase;
}
.sg-mode-label { margin:.25rem 0 .4rem; }
.sg-nav-group { margin:1.15rem 0 .3rem; }
[data-testid="stSidebar"] .stButton > button {
  justify-content:flex-start;
  min-height:2.35rem;
  border:1px solid #29464E;
  border-radius:5px;
  padding:.44rem .66rem;
  background:#102F38;
  color:#DCE7E8;
  font-weight:620;
  white-space:nowrap;
  overflow:visible;
}
[data-testid="stSidebar"] .stButton > button:hover {
  border-color:#55717A;
  background:#183A43;
  color:#FFFFFF;
  transform:none;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  border-color:#E4B95C;
  background:#E4B95C;
  color:var(--sg-ink);
}
[data-testid="stSidebar"] .stAlert {
  border:1px solid #29464E;
  border-radius:5px;
  background:#102F38;
  color:#DCE7E8;
}

/* Page masthead */
.sg-hero {
  position:relative;
  overflow:hidden;
  margin:0 0 1.45rem;
  padding:1.45rem 1.6rem 1.25rem;
  border-left:5px solid var(--sg-featured-site);
  border-radius:6px;
  background:var(--sg-ink);
  color:#FFFFFF;
}
.sg-hero:after {
  content:"";
  position:absolute;
  inset:0 0 0 62%;
  background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);
  background-size:28px 28px;
  pointer-events:none;
}
.sg-hero__body { position:relative; z-index:1; display:flex; align-items:flex-end; justify-content:space-between; gap:2rem; }
.sg-hero__copy { max-width:830px; }
.sg-hero h1 { max-width:790px; margin:.2rem 0 .55rem!important; color:#FFFFFF; }
.sg-eyebrow { color:#E4B95C; font-size:.72rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
.sg-lead { max-width:800px; margin:0; color:#C1CED1; font-size:1rem; line-height:1.55; }
.sg-hero__stamp {
  position:relative;
  z-index:1;
  flex:0 0 104px;
  border-top:1px solid #55717A;
  border-bottom:1px solid #55717A;
  padding:.55rem 0;
  color:#93A8AE;
  text-align:right;
  font-size:.63rem;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.sg-hero__stamp strong { display:block; color:#FFFFFF; font-size:1.8rem; line-height:1.05; letter-spacing:-.06em; }
.sg-badges { position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:.55rem 1.25rem; margin:.95rem 0 0; padding-top:.8rem; border-top:1px solid #29464E; }
.sg-badge { display:inline-flex; align-items:center; gap:.45rem; color:#C1CED1; font-size:.7rem; font-weight:760; letter-spacing:.06em; text-transform:uppercase; }
.sg-badge:before { content:""; width:.42rem; height:.42rem; background:#82969C; }
.sg-badge--success:before { background:#41B894; }
.sg-badge--warning:before { background:#E4B95C; }
.sg-badge--critical:before { background:#E26C66; }
.sg-badge--info:before { background:#68A9CF; }
.sg-badge--featured:before { background:#E4B95C; }

/* Content hierarchy */
.sg-section { display:grid; grid-template-columns:auto 1fr; column-gap:.75rem; margin:2rem 0 .85rem; align-items:start; }
.sg-section:before { content:""; width:.35rem; height:1.35rem; margin-top:.18rem; background:var(--sg-featured-site); }
.sg-section h2 { margin:0!important; font-size:1.35rem!important; }
.sg-section p { grid-column:2; margin:.18rem 0 0; color:var(--sg-muted); }
.sg-callout {
  border-left:3px solid var(--sg-primary);
  background:#FFFFFF;
  padding:.95rem 1.05rem;
  margin:1rem 0;
  line-height:1.5;
}
.sg-callout strong { display:block; margin-bottom:.18rem; }
.sg-callout--warning { border-left-color:var(--sg-curtail); background:#FFF9EE; }
.sg-callout--critical { border-left-color:var(--sg-unmet); background:#FFF4F3; }

/* Data surfaces */
[data-testid="stMetric"] {
  min-height:108px;
  border:1px solid var(--sg-border);
  border-top:3px solid var(--sg-primary);
  border-radius:5px;
  background:#FFFFFF;
  padding:.9rem 1rem;
  box-shadow:none;
}
[data-testid="stMetricLabel"] { color:var(--sg-muted); font-size:.84rem; font-weight:650; }
[data-testid="stMetricValue"] { color:var(--sg-text); letter-spacing:-.04em; }
[data-testid="stDataFrame"],
[data-testid="stVegaLiteChart"],
[data-testid="stDeckGlJsonChart"] {
  border:1px solid var(--sg-border);
  border-radius:5px;
  background:#FFFFFF;
  padding:.22rem;
}
.sg-card {
  height:100%;
  border:1px solid var(--sg-border);
  border-top:3px solid var(--sg-primary);
  border-radius:5px;
  background:#FFFFFF;
  padding:1rem 1.05rem;
}
.sg-card__kicker { color:var(--sg-primary); font-size:.68rem; font-weight:800; letter-spacing:.11em; text-transform:uppercase; }
.sg-card__title { margin:.25rem 0 .65rem; font-size:1.08rem; font-weight:720; }
.sg-card__value { font-size:1.5rem; font-weight:760; letter-spacing:-.04em; }
.sg-card__meta { margin-top:.25rem; color:var(--sg-muted); font-size:.86rem; line-height:1.5; }
.sg-stat-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.65rem; margin-top:.75rem; }
.sg-stat { border-top:1px solid var(--sg-border); padding-top:.55rem; }
.sg-stat span { display:block; color:var(--sg-muted); font-size:.67rem; letter-spacing:.06em; text-transform:uppercase; }
.sg-stat b { display:block; margin-top:.15rem; font-size:.91rem; }

.sg-featured-site { border:1px solid #E3C37F!important; border-left:5px solid var(--sg-featured-site)!important; background:#FFFDF7!important; box-shadow:none!important; }
.sg-featured-badge { display:inline-flex; color:#8A5D08; font-size:.68rem; font-weight:820; letter-spacing:.11em; text-transform:uppercase; }
.sg-site-detail { margin:1.2rem 0; border:1px solid var(--sg-border); border-left:5px solid var(--sg-primary); border-radius:5px; background:#FFFFFF; padding:1.05rem 1.2rem; }
.sg-site-detail h2 { margin:.32rem 0 .12rem!important; }
.sg-site-detail p { margin:0; color:var(--sg-muted); }

.sg-map-legend { display:flex; flex-wrap:wrap; align-items:center; gap:.55rem 1.1rem; margin:.45rem 0 1rem; color:var(--sg-muted); font-size:.8rem; }
.sg-map-legend span { display:inline-flex; align-items:center; gap:.38rem; }
.sg-map-dot { display:inline-block; width:.62rem; height:.62rem; border-radius:50%; box-shadow:0 0 0 2px #FFFFFF; }
.sg-map-dot--featured { background:#D89D2B; }
.sg-map-dot--site { background:#0F6B5C; }
.sg-map-hint { margin-left:auto; color:var(--sg-primary); font-weight:650; }

.sg-workflow { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin:1rem 0 1.35rem; border-top:1px solid var(--sg-border); border-bottom:1px solid var(--sg-border); background:#FFFFFF; }
.sg-workflow__step { display:grid; grid-template-columns:auto 1fr; gap:.65rem; align-items:center; min-height:66px; padding:.72rem .8rem; border-right:1px solid var(--sg-border); font-size:.8rem; font-weight:680; }
.sg-workflow__step:last-child { border-right:0; }
.sg-workflow__step b { color:var(--sg-featured-site); font-size:.68rem; letter-spacing:.06em; }
.sg-site { min-height:164px; border:1px solid var(--sg-border); border-top:3px solid var(--sg-primary); border-radius:5px; background:#FFFFFF; padding:1rem; }
.sg-site--pending { border-top-color:var(--sg-featured-site); background:#FFFDF7; }
.sg-site h3 { margin:.45rem 0 .35rem!important; font-size:1.05rem!important; }
.sg-site p { margin:.18rem 0; color:var(--sg-muted); font-size:.86rem; line-height:1.48; }
.sg-site .sg-badge { color:var(--sg-muted); }

.sg-flow { display:grid; grid-template-columns:1fr auto 1.15fr auto 1fr; gap:.6rem; align-items:center; margin:1rem 0; }
.sg-flow__node { border:1px solid var(--sg-border); border-top:3px solid var(--sg-primary); border-radius:5px; background:#FFFFFF; padding:.85rem; text-align:center; }
.sg-flow__node b { display:block; }
.sg-flow__node span { color:var(--sg-muted); font-size:.78rem; }
.sg-flow__arrow { color:var(--sg-featured-site); font-size:1.2rem; font-weight:800; }

.sg-sidebar-status { margin:.45rem 0; border-left:3px solid #4C6870; background:#102F38; padding:.65rem .72rem; }
.sg-sidebar-status b { display:block; color:#E5ECED; font-size:.72rem; letter-spacing:.04em; }
.sg-sidebar-status span { color:#91A7AD; font-size:.68rem; }
.sg-sidebar-status.sg-featured-site { border:0!important; border-left:3px solid #E4B95C!important; background:#102F38!important; }

@media(max-width:900px) {
  .block-container { padding-left:1rem; padding-right:1rem; }
  .sg-workflow { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .sg-workflow__step:nth-child(2) { border-right:0; }
  .sg-flow { grid-template-columns:1fr; }
  .sg-flow__arrow { transform:rotate(90deg); text-align:center; }
  .sg-stat-grid { grid-template-columns:1fr; }
}
@media(max-width:640px) {
  .block-container { padding-top:1rem; padding-bottom:2.5rem; }
  h1 { font-size:1.9rem!important; }
  .sg-hero { padding:1.15rem 1rem 1rem; }
  .sg-hero__body { display:block; }
  .sg-hero__stamp { display:none; }
  .sg-lead { font-size:.94rem; }
  .sg-workflow { grid-template-columns:1fr; }
  .sg-workflow__step { border-right:0; border-bottom:1px solid var(--sg-border); }
  .sg-workflow__step:last-child { border-bottom:0; }
  [data-testid="stMetric"] { min-height:94px; padding:.75rem .85rem; }
  .sg-map-hint { width:100%; margin-left:0; padding-top:.25rem; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
