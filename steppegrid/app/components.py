"""Reusable Streamlit presentation components for the analytical UI."""

from __future__ import annotations

from html import escape
from typing import Iterable, Mapping

import pandas as pd
import streamlit as st

from steppegrid.app.formatting import energy, money, power

GLOSSARY = {
    "served_energy": "Share of annual electricity demand supplied. It is not the percentage of uninterrupted hours.",
    "lpsp": "Energy-based loss of power supply probability: unmet annual energy divided by annual demand.",
    "lolh": "Loss-of-load hours: hours containing any modeled unmet electricity demand.",
    "npc": "Net present cost: discounted lifetime planning cost under the frozen economic assumptions.",
    "eac": "Equivalent annual cost: the annualized value of net present cost.",
    "curtailment": "Renewable energy available but neither used by load nor accepted by storage.",
    "capacity_factor": "Annual energy divided by rated power multiplied by all hours in the year.",
    "poa": "Plane-of-array solar irradiation incident on the modeled tilted PV surface.",
    "binding_profile": "Reconstructed load shape with the lowest served-energy fraction for the selected robust design.",
}


def app_header() -> None:
    st.markdown(
        '<header class="sg-appbar"><div class="sg-appbar__brand"><span class="sg-appbar__mark">SG</span>'
        '<span><strong>SteppeGrid</strong><small>Village microgrid planning</small></span></div>'
        '<div class="sg-appbar__context"><span>Kazakhstan</span><a href="https://github.com/Stukhori/SteppeGrid" '
        'target="_blank" rel="noopener noreferrer">Project methods ↗</a></div></header>',
        unsafe_allow_html=True,
    )


def overview_intro() -> None:
    st.markdown(
        '<section class="sg-overview-intro"><div class="sg-eyebrow">Kazakhstan village energy planning</div>'
        '<h1>Plan a resilient village microgrid</h1><p>Explore how hourly demand and local weather shape '
        'wind, solar, storage, reliability, and lifetime cost.</p></section>',
        unsafe_allow_html=True,
    )


def microgrid_schematic() -> None:
    st.markdown(
        '<figure class="sg-schematic" aria-label="Energy flows from wind and solar generation through battery storage to village electricity demand">'
        '<svg viewBox="0 0 680 280" role="img"><title>Village microgrid energy-flow schematic</title>'
        '<path class="sg-grid" d="M30 224H650M52 248H628"/><path class="sg-flowline" d="M157 171H284M392 171H522"/>'
        '<g class="sg-wind"><path d="M130 94v110M112 204h36"/><circle cx="130" cy="88" r="7"/>'
        '<path d="M130 80l-8-52M136 90l48-24M126 94l-38 37"/></g>'
        '<g class="sg-sun"><circle cx="236" cy="48" r="19"/><path d="M236 15v-9M236 90v-9M203 48h-9M278 48h-9M213 25l-7-7M266 78l-7-7M259 25l7-7M206 78l7-7"/></g>'
        '<g class="sg-solar"><path d="M196 132h82l16 55h-114zM207 132l-8 55M234 132v55M261 132l8 55M188 158h98M218 187l-8 18M270 187l8 18"/></g>'
        '<g class="sg-battery"><rect x="304" y="124" width="88" height="96" rx="7"/><path d="M337 111h22v13M326 151h44M326 174h44M326 197h26"/></g>'
        '<g class="sg-village"><path d="M500 159l46-38 46 38v62h-92zM516 221v-35h24v35M566 221v-29h15v29M612 221v-48h22v48M607 173h32"/></g>'
        '<text x="92" y="242">Wind</text><text x="205" y="242">Solar</text><text x="310" y="242">Storage</text><text x="512" y="242">Village load</text>'
        '</svg><figcaption>Hourly renewable generation → storage dispatch → village load</figcaption></figure>',
        unsafe_allow_html=True,
    )


def resource_strip() -> None:
    items = (
        ("7", "villages"),
        ("8,760", "hourly steps"),
        ("Wind + solar", "resource models"),
        ("95% / 99%", "planning targets"),
    )
    rendered = "".join(f'<div><strong>{escape(value)}</strong><span>{escape(label)}</span></div>' for value, label in items)
    st.markdown(f'<div class="sg-resource-strip">{rendered}</div>', unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, lead: str, badges: Iterable[tuple[str, str]] = ()) -> None:
    rendered = "".join(f'<span class="sg-badge sg-badge--{escape(tone)}">{escape(label)}</span>' for label, tone in badges)
    badge_row = f'<div class="sg-badges">{rendered}</div>' if rendered else ""
    st.markdown(f'<header class="sg-pagehead"><div class="sg-eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(lead)}</p>{badge_row}</header>', unsafe_allow_html=True)


def section_header(title: str, description: str = "") -> None:
    copy = f"<p>{escape(description)}</p>" if description else ""
    st.markdown(f'<div class="sg-section"><h2>{escape(title)}</h2>{copy}</div>', unsafe_allow_html=True)


def callout(title: str, body: str, tone: str = "info") -> None:
    modifier = "" if tone == "info" else f" sg-callout--{tone}"
    st.markdown(f'<div class="sg-callout{modifier}"><strong>{escape(title)}</strong>{escape(body)}</div>', unsafe_allow_html=True)


def metric(label: str, value: str, *, help_key: str | None = None, delta: str | None = None) -> None:
    st.metric(label, value, delta=delta, help=GLOSSARY.get(help_key) if help_key else None)


def equipment_card(kicker: str, title: str, value: str, stats: Mapping[str, str]) -> None:
    items = "".join(f'<div class="sg-stat"><span>{escape(label)}</span><b>{escape(item)}</b></div>' for label, item in stats.items())
    st.markdown(f'<div class="sg-card"><div class="sg-card__kicker">{escape(kicker)}</div><div class="sg-card__title">{escape(title)}</div><div class="sg-card__value">{escape(value)}</div><div class="sg-stat-grid">{items}</div></div>', unsafe_allow_html=True)


def design_card(kind: str, headline: str, capacity: str, detail: str) -> None:
    st.markdown(f'<div class="sg-card"><div class="sg-card__kicker">{escape(kind)}</div><div class="sg-card__title">{escape(headline)}</div><div class="sg-card__value">{escape(capacity)}</div><div class="sg-card__meta">{escape(detail)}</div></div>', unsafe_allow_html=True)


def workflow(steps: Iterable[str]) -> None:
    nodes = "".join(
        f'<div class="sg-workflow__step"><b>{index:02d}</b><span>{escape(step)}</span></div>'
        for index, step in enumerate(steps, start=1)
    )
    st.markdown(f'<div class="sg-workflow">{nodes}</div>', unsafe_allow_html=True)


def site_status(name: str, status: str, details: Iterable[str], *, pending: bool = False) -> None:
    tone, modifier = ("warning", " sg-site--pending") if pending else ("success", "")
    copy = "".join(f"<p>{escape(detail)}</p>" for detail in details)
    st.markdown(f'<div class="sg-site{modifier}"><span class="sg-badge sg-badge--{tone}">{escape(status)}</span><h3>{escape(name)}</h3>{copy}</div>', unsafe_allow_html=True)


def energy_flow(wind_kwh: float, pv_kwh: float, served_kwh: float, curtailed_kwh: float, unmet_kwh: float) -> None:
    st.markdown('<div class="sg-flow">' f'<div class="sg-flow__node"><b>Wind + solar</b><span>{escape(energy(wind_kwh + pv_kwh))} renewable generation</span></div>' '<div class="sg-flow__arrow">→</div>' f'<div class="sg-flow__node"><b>Hourly dispatch + storage</b><span>{escape(energy(served_kwh))} load served</span></div>' '<div class="sg-flow__arrow">→</div>' f'<div class="sg-flow__node"><b>Annual balance</b><span>{escape(energy(curtailed_kwh))} curtailed · {escape(energy(unmet_kwh))} unmet</span></div>' '</div>', unsafe_allow_html=True)


def comparison_table(rows: list[dict]) -> None:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def audit_status(checks: int, blockers: int, warnings: int, tests: int) -> None:
    cols = st.columns(4)
    cols[0].metric("Validation checks", checks); cols[1].metric("Correctness blockers", blockers)
    cols[2].metric("Scope warnings", warnings); cols[3].metric("Regression tests", tests)


def limitations(groups: Mapping[str, Iterable[str]]) -> None:
    for title, items in groups.items():
        with st.expander(title, expanded=False):
            for item in items: st.markdown(f"- {item}")


def design_comparison_rows(lower: dict, higher: dict) -> list[dict]:
    def change(a: float, b: float) -> str: return f"{100 * (b / a - 1):+.1f}%" if a else "—"
    return [
        {"Measure": "Wind capacity", "95%": power(lower["installed_wind_kw"]), "99%": power(higher["installed_wind_kw"]), "Change": change(lower["installed_wind_kw"], higher["installed_wind_kw"])},
        {"Measure": "PV AC capacity", "95%": power(lower["installed_pv_ac_kw"]), "99%": power(higher["installed_pv_ac_kw"]), "Change": change(lower["installed_pv_ac_kw"], higher["installed_pv_ac_kw"])},
        {"Measure": "Usable storage", "95%": energy(lower["installed_usable_battery_kwh"]), "99%": energy(higher["installed_usable_battery_kwh"]), "Change": change(lower["installed_usable_battery_kwh"], higher["installed_usable_battery_kwh"])},
        {"Measure": "Net present cost", "95%": money(lower["net_present_cost_usd"]), "99%": money(higher["net_present_cost_usd"]), "Change": change(lower["net_present_cost_usd"], higher["net_present_cost_usd"])},
        {"Measure": "Loss-of-load hours", "95%": f"{lower['loss_of_load_hours']} h", "99%": f"{higher['loss_of_load_hours']} h", "Change": change(lower["loss_of_load_hours"], higher["loss_of_load_hours"])},
        {"Measure": "Curtailment", "95%": energy(lower["curtailment_kwh"]), "99%": energy(higher["curtailment_kwh"]), "Change": change(lower["curtailment_kwh"], higher["curtailment_kwh"])},
    ]
