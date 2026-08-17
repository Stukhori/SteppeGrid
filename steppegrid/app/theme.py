"""Central visual design tokens and global Streamlit styling."""

from __future__ import annotations

import streamlit as st

COLORS = {
    "primary": "#1F6B5B", "primary_dark": "#174C41", "wind": "#2878A6",
    "solar": "#D59A16", "storage": "#7359A6", "served": "#2F7D5A",
    "unmet": "#B84A45", "curtailment": "#B06F2E", "neutral": "#66736D",
    "muted": "#8A9690", "success": "#2F7D5A", "caution": "#A66A1F",
    "critical": "#B84A45", "surface": "#FFFFFF", "surface_alt": "#EDF2EE",
    "border": "#D8E0DB", "text": "#17211D", "featured_site": "#2878D8",
}

GLOBAL_CSS = """
<style>
:root { --sg-primary:#1F6B5B;--sg-featured-site:#2878D8;--sg-wind:#2878A6;--sg-solar:#D59A16;--sg-storage:#7359A6;--sg-unmet:#B84A45;--sg-curtail:#B06F2E;--sg-text:#17211D;--sg-muted:#66736D;--sg-border:#D8E0DB;--sg-surface:#FFFFFF;--sg-surface-alt:#EDF2EE; }
.stApp{color:var(--sg-text)}.block-container{max-width:1180px;padding-top:2.2rem;padding-bottom:4rem}h1,h2,h3{letter-spacing:-.025em}h1{font-size:2.35rem!important;line-height:1.08!important;margin-bottom:.35rem!important}h2{font-size:1.4rem!important;margin-top:1.8rem!important}
[data-testid="stSidebar"]{border-right:1px solid var(--sg-border)}[data-testid="stSidebar"] .stButton>button{justify-content:flex-start;border:0;border-radius:7px;padding:.42rem .65rem;font-weight:560}[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:var(--sg-primary);color:white}
[data-testid="stMetric"]{background:var(--sg-surface);border:1px solid var(--sg-border);border-radius:10px;padding:1rem 1.05rem;min-height:116px;box-shadow:0 1px 2px rgba(23,33,29,.03)}[data-testid="stMetricLabel"]{color:var(--sg-muted);font-weight:650;letter-spacing:.015em}[data-testid="stMetricValue"]{color:var(--sg-text);letter-spacing:-.035em}
.sg-eyebrow{color:var(--sg-primary);font-size:.76rem;font-weight:760;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.45rem}.sg-lead{color:var(--sg-muted);font-size:1.05rem;max-width:820px;line-height:1.55;margin:.25rem 0 1.25rem}.sg-badges{display:flex;flex-wrap:wrap;gap:.45rem;margin:.8rem 0 1.35rem}.sg-badge{display:inline-flex;align-items:center;border:1px solid var(--sg-border);background:var(--sg-surface);border-radius:999px;padding:.28rem .58rem;color:var(--sg-muted);font-size:.72rem;font-weight:720;letter-spacing:.04em}.sg-badge--success{color:#1E654A;border-color:#BBD8CB;background:#EDF7F2}.sg-badge--warning{color:#835315;border-color:#E6D0AD;background:#FBF6ED}.sg-badge--critical{color:#963A36;border-color:#E4BCBA;background:#FCF0EF}
.sg-section{margin:2rem 0 .75rem;padding-bottom:.55rem;border-bottom:1px solid var(--sg-border)}.sg-section h2{margin:0!important;font-size:1.35rem!important}.sg-section p{margin:.25rem 0 0;color:var(--sg-muted)}.sg-callout{border-left:4px solid var(--sg-primary);background:var(--sg-surface-alt);border-radius:6px;padding:1rem 1.15rem;margin:1rem 0;line-height:1.5}.sg-callout strong{display:block;margin-bottom:.15rem}.sg-callout--warning{border-left-color:var(--sg-curtail);background:#FBF6ED}.sg-callout--critical{border-left-color:var(--sg-unmet);background:#FCF0EF}
.sg-card{height:100%;border:1px solid var(--sg-border);background:var(--sg-surface);border-radius:10px;padding:1rem 1.05rem}.sg-card__kicker{color:var(--sg-muted);font-size:.7rem;font-weight:760;letter-spacing:.1em;text-transform:uppercase}.sg-card__title{font-size:1.12rem;font-weight:720;margin:.25rem 0 .65rem}.sg-card__value{font-size:1.55rem;font-weight:760;letter-spacing:-.035em}.sg-card__meta{color:var(--sg-muted);font-size:.86rem;line-height:1.5;margin-top:.25rem}.sg-stat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin-top:.65rem}.sg-stat{border-top:1px solid var(--sg-border);padding-top:.55rem}.sg-stat span{display:block;color:var(--sg-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em}.sg-stat b{display:block;font-size:.93rem;margin-top:.15rem}
.sg-featured-site{border:2px solid var(--sg-featured-site)!important;background:#F3F8FF!important;box-shadow:0 8px 28px rgba(40,120,216,.10)}.sg-featured-badge{display:inline-flex;background:var(--sg-featured-site);color:white;border-radius:999px;padding:.3rem .65rem;font-size:.72rem;font-weight:800;letter-spacing:.1em}.sg-site-detail{border:1px solid var(--sg-border);border-radius:12px;padding:1.2rem 1.35rem;margin:1.2rem 0}.sg-site-detail h2{margin:.55rem 0 .2rem!important}.sg-site-detail p{color:var(--sg-muted);margin:0}
.sg-workflow{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.4rem;align-items:center;margin:1rem 0 1.5rem}.sg-workflow__step{background:var(--sg-surface);border:1px solid var(--sg-border);border-radius:8px;padding:.72rem .45rem;text-align:center;font-size:.77rem;font-weight:650;min-height:58px;display:flex;align-items:center;justify-content:center}.sg-site{border:1px solid var(--sg-border);border-radius:10px;background:var(--sg-surface);padding:1rem;min-height:164px}.sg-site--pending{background:#FAF8F3}.sg-site h3{margin:.2rem 0 .45rem!important;font-size:1.08rem!important}.sg-site p{color:var(--sg-muted);font-size:.86rem;line-height:1.5;margin:.2rem 0}
.sg-flow{display:grid;grid-template-columns:1fr auto 1.15fr auto 1fr;gap:.55rem;align-items:center;margin:1rem 0}.sg-flow__node{border:1px solid var(--sg-border);background:var(--sg-surface);border-radius:9px;padding:.85rem;text-align:center}.sg-flow__node b{display:block}.sg-flow__node span{color:var(--sg-muted);font-size:.78rem}.sg-flow__arrow{color:var(--sg-primary);font-size:1.35rem;font-weight:800}.sg-nav-group{color:#7A8781;font-size:.65rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin:1rem 0 .25rem}.sg-sidebar-status{border:1px solid var(--sg-border);background:var(--sg-surface);border-radius:8px;padding:.72rem;margin:.4rem 0}.sg-sidebar-status b{display:block;font-size:.78rem}.sg-sidebar-status span{color:var(--sg-muted);font-size:.7rem}
@media(max-width:900px){.block-container{padding-left:1rem;padding-right:1rem}.sg-workflow{grid-template-columns:repeat(2,minmax(0,1fr))}.sg-flow{grid-template-columns:1fr}.sg-flow__arrow{transform:rotate(90deg);text-align:center}.sg-stat-grid{grid-template-columns:1fr}}
</style>
"""


def apply_theme() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
