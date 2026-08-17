"""SteppeGrid Phase 13 interactive planning MVP."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from steppegrid.app.charts import date_window, monthly_energy
from steppegrid.app.data import AppDataError
from steppegrid.app.formatting import RECONSTRUCTION_NOTICE, SCENARIO_NOTICE, energy, money, percent, power, readable
from steppegrid.app.services import PlanningService
from steppegrid.app.state import PAGES, PROFILE_LABELS, SHAMSHI_STATUS, TARGET_LABELS

st.set_page_config(page_title="SteppeGrid Planning", page_icon="⚡", layout="wide")
st.markdown("""<style>.block-container{max-width:1280px;padding-top:1.7rem}[data-testid="stMetric"]{background:#f3f7f4;border:1px solid #d9e4db;border-radius:10px;padding:14px}.status-note{padding:12px 14px;border-left:4px solid #2f7d5a;background:#f3f7f4;border-radius:4px}</style>""", unsafe_allow_html=True)


@st.cache_resource
def service() -> PlanningService:
    return PlanningService()


def target_select(key: str) -> float:
    return TARGET_LABELS[st.selectbox("Frozen system design", TARGET_LABELS, key=key)]


def profile_select(key: str) -> str:
    return PROFILE_LABELS[st.selectbox("Reconstructed load profile", PROFILE_LABELS, key=key)]


def show_notice() -> None:
    st.info(RECONSTRUCTION_NOTICE)


def overview(api: PlanningService) -> None:
    st.title("SteppeGrid — Rodina planning benchmark")
    st.caption("Phase 13 interactive view of frozen, validated Phase 9–12 research results")
    st.write("SteppeGrid combines hourly weather and reconstructed demand with commercial-equipment generation models, battery dispatch, reliability targets, planning economics, and deterministic sensitivity analysis.")
    st.markdown('<div class="status-note"><b>Rodina benchmark:</b> literature-derived/reconstructed case — validated and frozen through Phase 12.</div>', unsafe_allow_html=True)
    st.warning(SHAMSHI_STATUS)
    columns = st.columns(4)
    manifest = api.provenance()
    site, demand = manifest["site"], manifest["demand"]
    columns[0].metric("Annual reconstructed demand", energy(demand["monthly_rows_reconstructed_annual_kwh"]))
    columns[1].metric("Weather coverage", "8,760 hours")
    columns[2].metric("Location", f"{site['latitude']:.3f}°, {site['longitude']:.3f}°")
    columns[3].metric("Validation blockers", api.validation()["blockers"])
    st.markdown("**Weather + Demand → Physical Models → Hourly Dispatch → Reliability → Optimization → Economics → Sensitivity**")
    st.subheader("Frozen design outcomes")
    for column, target in zip(st.columns(2), (0.95, 0.99), strict=True):
        design = api.design(target)
        with column:
            st.markdown(f"#### {target:.0%} annual served-energy target")
            a, b, c, d = st.columns(4)
            a.metric("Worst served energy", percent(design["worst_served_fraction"], 3))
            b.metric("NPC", money(design["net_present_cost_usd"]))
            c.metric("Unmet energy", energy(design["unmet_energy_kwh"]))
            d.metric("Loss-of-load hours", f"{design['loss_of_load_hours']:,} h")
            st.caption(f"{design['wind_count']} wind turbines · {design['pv_count']} PV blocks · {design['battery_count']} battery systems")
    show_notice()
    st.caption("Navigation changes the view only. This application does not run an optimizer.")


def demand_weather(api: PlanningService) -> None:
    st.title("Demand & Weather")
    profile = profile_select("demand_profile")
    with st.spinner("Loading the frozen aligned hourly inputs…"):
        frame = api.demand_weather_frame(profile)
    show_notice()
    st.subheader("Reconstructed demand")
    manifest = api.provenance()
    source = manifest["demand"]
    a, b, c = st.columns(3)
    a.metric("Paper printed annual demand", energy(source["printed_annual_kwh"]))
    b.metric("Published monthly rows sum", energy(source["monthly_rows_reconstructed_annual_kwh"]))
    c.metric("Benchmark value", energy(source["monthly_rows_reconstructed_annual_kwh"]))
    st.bar_chart(monthly_energy(frame, "load_kwh"), x="month", y="energy_kwh")
    start = st.date_input("Hourly view start", frame["timestamp"].iloc[0].date(), key="demand_start")
    end = st.date_input("Hourly view end", min(start + pd.Timedelta(days=6), frame["timestamp"].iloc[-1].date()), key="demand_end")
    if start > end:
        st.error("Start date must not be after end date.")
        window = frame.iloc[:0]
    else:
        window = date_window(frame, start, end)
        st.line_chart(window, x="timestamp", y="load_kwh", y_label="Hourly energy (kWh)")
    comparison = api.demand_comparison_frame()
    comparison = date_window(comparison, start, min(end, start + pd.Timedelta(days=6)))
    st.subheader("Load-shape comparison")
    st.line_chart(comparison, x="timestamp", y=list(PROFILE_LABELS.values()), y_label="Hourly demand (kWh)")
    st.subheader("ERA5-derived weather")
    a, b, c = st.columns(3)
    a.metric("Mean wind at 100 m", f"{frame['wind_speed_100m_m_s'].mean():.2f} m/s")
    b.metric("Annual GHI", f"{frame['ghi_w_m2'].sum()/1000:,.0f} kWh/m²")
    c.metric("Mean temperature", f"{frame['temperature_c'].mean():.1f} °C")
    if not window.empty:
        st.line_chart(window, x="timestamp", y=["wind_speed_10m_m_s", "wind_speed_100m_m_s"], y_label="Wind speed (m/s)")
        st.line_chart(window, x="timestamp", y="ghi_w_m2", y_label="GHI (W/m²)")
    st.caption("ERA5 is gridded reanalysis, not an on-site measurement campaign.")
    site = manifest["site"]
    st.caption(f"2025 · 8,760 hours · Open-Meteo cached ERA5 · {site['latitude']:.6f}, {site['longitude']:.6f} · {site['timezone']}")


def renewable_generation(api: PlanningService) -> None:
    st.title("Renewable Generation")
    wind_rows, pv_rows = api.generation_catalog()
    wind = pd.DataFrame(wind_rows)
    pv = pd.DataFrame(pv_rows)
    st.subheader("Wind equipment comparison")
    st.dataframe(wind[["equipment_key", "manufacturer", "model", "rated_power_kw", "hub_height_m", "annual_generation_kwh", "capacity_factor"]], hide_index=True, width="stretch")
    st.subheader("PV block")
    st.dataframe(pv[["equipment_key", "module", "inverter", "dc_capacity_kw", "ac_capacity_kw", "annual_ac_kwh", "ac_specific_yield_kwh_per_kwp", "annual_poa_kwh_m2", "clipping_kwh"]], hide_index=True, width="stretch")
    design = api.design(0.95)
    with st.spinner("Loading frozen Phase 9 unit-generation traces…"):
        frame = api.generation_frame(design["wind_key"], design["pv_key"])
    start = frame["timestamp"].iloc[0].date()
    example = date_window(frame, start, start + pd.Timedelta(days=6))
    st.subheader("Representative unit traces — first week of 2025")
    st.line_chart(example, x="timestamp", y=["wind_kwh_per_unit", "pv_kwh_per_block"], y_label="Hourly energy (kWh)")
    st.caption("Power curves come from certification/reference documents; Rodina shear is ERA5-derived. No wake or layout model is included. PV and wind traces are modeled, not measured.")


def design_table(api: PlanningService) -> pd.DataFrame:
    rows = []
    for target in (0.95, 0.99):
        design = api.design(target)
        rows.append({"target": f"{target:.0%}", "wind turbines": design["wind_count"], "wind MW": design["installed_wind_kw"] / 1000, "PV blocks": design["pv_count"], "PV AC MW": design["installed_pv_ac_kw"] / 1000, "batteries": design["battery_count"], "usable storage MWh": design["installed_usable_battery_kwh"] / 1000, "CAPEX (USD)": design["initial_capex_usd"], "NPC (USD)": design["net_present_cost_usd"], "EAC (USD/y)": design["equivalent_annual_cost_usd"], "unmet MWh": design["unmet_energy_kwh"] / 1000, "LOLH": design["loss_of_load_hours"], "curtailment GWh": design["curtailment_kwh"] / 1_000_000, "served energy": percent(design["worst_served_fraction"], 3)})
    return pd.DataFrame(rows)


def system_design(api: PlanningService) -> None:
    st.title("System Design")
    target = target_select("design_target")
    design = api.design(target)
    st.caption("Least-cost feasible robust design from the frozen Phase 10 staged discrete search.")
    a, b, c, d = st.columns(4)
    a.metric("Wind", f"{design['wind_count']} × {readable(design['wind_key'])}", power(design["installed_wind_kw"]))
    b.metric("PV", f"{design['pv_count']} blocks", power(design["installed_pv_ac_kw"]) + " AC")
    c.metric("Battery", f"{design['battery_count']} systems", energy(design["installed_usable_battery_kwh"]) + " usable")
    d.metric("Worst served energy", percent(design["worst_served_fraction"], 3))
    annual_by_key = {row["item"]: row["value"] for row in api.benchmark_rows() if row["category"] in {"wind", "pv"}}
    annual_generation = design["wind_count"] * annual_by_key[design["wind_key"]] + design["pv_count"] * annual_by_key[design["pv_key"]]
    st.subheader("Performance & economics")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Annual generation", energy(annual_generation))
    p2.metric("Unmet energy", energy(design["unmet_energy_kwh"]))
    p3.metric("Curtailment", energy(design["curtailment_kwh"]))
    p4.metric("Binding profile", readable(design["binding_load_profile"]))
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Initial CAPEX", money(design["initial_capex_usd"]))
    e2.metric("Net present cost", money(design["net_present_cost_usd"]))
    e3.metric("Equivalent annual cost", money(design["equivalent_annual_cost_usd"]) + "/year")
    e4.metric("Cost per served kWh", f"${design['cost_per_served_kwh_usd']:.3f}")
    st.subheader("95% versus 99%")
    st.dataframe(design_table(api), hide_index=True, width="stretch")
    lower, higher = api.design(0.95), api.design(0.99)
    st.info(f"For this Rodina benchmark, moving from 95% to 99% adds {power(higher['installed_wind_kw']-lower['installed_wind_kw'])} wind, {power(higher['installed_pv_ac_kw']-lower['installed_pv_ac_kw'])} PV AC, {energy(higher['installed_usable_battery_kwh']-lower['installed_usable_battery_kwh'])} usable storage, and {money(higher['net_present_cost_usd']-lower['net_present_cost_usd'])} NPC, while reducing unmet energy by {energy(lower['unmet_energy_kwh']-higher['unmet_energy_kwh'])}.")
    st.subheader("Hourly dispatch explorer")
    profile = profile_select("dispatch_profile")
    with st.spinner("Replaying the frozen design through the existing hourly dispatch model…"):
        frame = api.dispatch_frame(target, profile)
    first = frame["timestamp"].iloc[0].date()
    dates = st.date_input("Date window", (first, first + pd.Timedelta(days=6)), min_value=first, max_value=frame["timestamp"].iloc[-1].date())
    if isinstance(dates, (tuple, list)) and len(dates) == 2:
        window = date_window(frame, dates[0], dates[1])
        st.line_chart(window, x="timestamp", y=["load_kwh", "wind_generation_kwh", "pv_generation_kwh", "total_generation_kwh"], y_label="Hourly energy (kWh)")
        st.line_chart(window, x="timestamp", y="battery_soc_kwh", y_label="Battery SOC (kWh)")
        st.area_chart(window, x="timestamp", y=["unmet_energy_kwh", "curtailment_kwh"], y_label="Hourly energy (kWh)")
        st.dataframe(window, hide_index=True, width="stretch")
    st.caption("Replay only: equipment and dispatch rules remain frozen; no optimization is performed.")


def reliability(api: PlanningService) -> None:
    st.title("Reliability")
    target = target_select("reliability_target")
    design = api.design(target)
    a, b, c = st.columns(3)
    a.metric("Worst served-energy fraction", percent(design["worst_served_fraction"], 3))
    b.metric("Energy-based LPSP", percent(design["lpsp"], 3))
    c.metric("Unmet energy", energy(design["unmet_energy_kwh"]))
    d, e, f = st.columns(3)
    d.metric("Loss-of-load hours", f"{design['loss_of_load_hours']:,}")
    e.metric("Longest deficit run", f"{design['longest_deficit_hours']} h")
    f.metric("Maximum hourly deficit", energy(design["maximum_hourly_deficit_kwh"]))
    frame = pd.DataFrame(api.reliability_rows(target))
    st.bar_chart(frame, x="load_profile", y="served_fraction", y_label="Annual served-energy fraction")
    st.dataframe(frame, hide_index=True, width="stretch")
    show_notice()


def economics(api: PlanningService) -> None:
    st.title("Economics")
    rows = []
    for target in (0.95, 0.99):
        design = api.design(target)
        rows.append({"target": f"{target:.0%}", "initial CAPEX (USD)": design["initial_capex_usd"], "net present cost (USD)": design["net_present_cost_usd"], "equivalent annual cost (USD/y)": design["equivalent_annual_cost_usd"], "cost per served kWh (USD)": design["cost_per_served_kwh_usd"]})
    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True, width="stretch")
    st.bar_chart(frame, x="target", y=["initial CAPEX (USD)", "net present cost (USD)"])
    st.caption("Research reference economics are frozen Phase 10 assumptions, not quotations, forecasts, or investment advice.")


def sensitivity(api: PlanningService) -> None:
    st.title("Sensitivity")
    target = target_select("sensitivity_target")
    frame = pd.DataFrame(api.fixed_sensitivity_rows(target))
    st.bar_chart(frame, x="scenario", y="served_fraction", color="passes_target", y_label="Annual served-energy fraction")
    st.dataframe(frame, hide_index=True, width="stretch")
    margins = next(row for row in api.margin_rows() if row["target"] == target)
    st.subheader("Deterministic robustness margins")
    a, b, c = st.columns(3)
    a.metric("Demand headroom", f"{100 * (margins['maximum_demand_multiplier_for_target'] - 1):.2f}%")
    b.metric("Minimum PV multiplier", f"{margins['minimum_pv_multiplier_for_target']:.4f}×")
    c.metric("Maximum shear α", f"{margins['maximum_wind_shear_for_target']:.4f}")
    st.info(SCENARIO_NOTICE)
    st.markdown("**Finding:** the nominal least-cost systems sit close to their reliability constraints.")
    st.caption("Higher α is adverse here because every modeled turbine hub is below the ERA5 100 m reference height.")


def methodology(api: PlanningService) -> None:
    st.title("Methodology & Provenance")
    manifest, audit = api.provenance(), api.validation()
    st.subheader("Validation status")
    a, b = st.columns(2)
    a.metric("Correctness blockers", audit["blockers"])
    b.metric("Documented scope warnings", audit["warnings"])
    st.dataframe(pd.DataFrame(audit["checks"])[["category", "check", "status", "message"]], hide_index=True, width="stretch")
    st.subheader("Assumptions registry")
    assumptions = pd.DataFrame(api.assumptions())
    classification = st.multiselect("Classification", sorted(assumptions["classification"].unique()), default=[])
    if classification:
        assumptions = assumptions[assumptions["classification"].isin(classification)]
    st.dataframe(assumptions, hide_index=True, width="stretch")
    st.subheader("Provenance summary")
    st.write(f"**Site:** {manifest['site']['name']}, {manifest['site']['region']} · {manifest['site']['reference_year']} · {manifest['site']['timezone']}")
    st.write(f"**Weather:** {manifest['weather']['dataset']} via {manifest['weather']['provider']} · {manifest['weather']['records']:,} cached records")
    st.write(f"**Demand:** {manifest['demand']['status']} · benchmark total {energy(manifest['demand']['monthly_rows_reconstructed_annual_kwh'])}")
    st.write(f"**Frozen git provenance:** `{manifest['software']['git']}`")
    st.write(f"**Phase 12 repository tests:** {manifest['software']['repository_test_count_at_phase12']}")
    st.dataframe(pd.DataFrame([api.adaptation_metadata()["single_profile_comparison_provenance"]]), hide_index=True, width="stretch")
    st.json({key: api.adaptation_metadata()[key] for key in ("adaptation_method", "full_reoptimization_performed")})
    st.info(SCENARIO_NOTICE)
    st.warning(SHAMSHI_STATUS)


ROUTES = {"Overview": overview, "Demand & Weather": demand_weather, "Renewable Generation": renewable_generation, "System Design": system_design, "Reliability": reliability, "Economics": economics, "Sensitivity": sensitivity, "Methodology & Provenance": methodology}
with st.sidebar:
    st.title("⚡ SteppeGrid")
    page = st.radio("Planning view", PAGES)
    st.divider()
    st.caption("Frozen Rodina benchmark · Phase 13 MVP")
try:
    ROUTES[page](service())
except AppDataError as error:
    st.error(str(error))
    st.code("python scripts/run_phase12.py --mode verify", language="powershell")
    st.stop()
