"""SteppeGrid Phase 13.5 analytical application."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from steppegrid.app.charts import (
    area_chart, bar_chart, date_window, line_chart, monthly_energy, preset_dates,
    sensitivity_chart, wind_comparison,
)
from steppegrid.app.components import (
    GLOSSARY, audit_status, callout, comparison_table, design_card,
    design_comparison_rows, energy_flow, equipment_card, limitations, metric,
    page_header, section_header, sidebar_status, site_status, workflow,
)
from steppegrid.app.data import AppDataError
from steppegrid.app.formatting import RECONSTRUCTION_NOTICE, SCENARIO_NOTICE, energy, money, percent, power, readable
from steppegrid.app.services import PlanningService
from steppegrid.app.planner import render_planner
from steppegrid.app.state import NAVIGATION, PROFILE_LABELS, SHAMSHI_STATUS, TARGET_LABELS
from steppegrid.app.theme import COLORS, apply_theme
from steppegrid.planning.service import ScenarioPlanningService

st.set_page_config(page_title="SteppeGrid | Rodina Benchmark", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
apply_theme()


@st.cache_resource
def service() -> PlanningService:
    return PlanningService()


@st.cache_resource
def scenario_service() -> ScenarioPlanningService:
    return ScenarioPlanningService()


def target_selector(key: str) -> float:
    label = st.segmented_control("Reliability target", list(TARGET_LABELS), default=list(TARGET_LABELS)[0], key=key)
    return TARGET_LABELS[label]


def profile_selector(key: str) -> str:
    label = st.selectbox("Reconstructed load profile", list(PROFILE_LABELS), key=key)
    return PROFILE_LABELS[label]


def overview(api: PlanningService) -> None:
    manifest = api.provenance(); site = manifest["site"]; demand = manifest["demand"]
    lower, higher = api.design(0.95), api.design(0.99)
    page_header(
        "SteppeGrid · Explore benchmark",
        "Renewable microgrid planning for rural Kazakhstan",
        f"Rodina benchmark · {site['region']} · 2025 ERA5 · {energy(demand['monthly_rows_reconstructed_annual_kwh'])} reconstructed demand",
        [("VALIDATED", "success"), ("RECONSTRUCTED DEMAND", "warning"), ("ERA5 WEATHER", "info"), ("FROZEN BENCHMARK", "success")],
    )
    section_header("Study status", "One completed literature benchmark and one explicit-estimate planning site.")
    left, right = st.columns(2)
    with left:
        site_status("Rodina, Akmola Region", "BENCHMARK COMPLETE", ["Data: reconstructed demand + cached ERA5 weather", "Optimization: frozen 95% and 99% designs available"])
    with right:
        site_status("Shamshi Kaldayakova, Aktobe Region", "ESTIMATE WORKFLOW ENABLED", ["Weather: ERA5 support available", "Demand: user estimate, proxy, monthly totals, or hourly CSV required"], pending=True)

    section_header("The result in one view", "Annual served energy is an energy metric—not uptime.")
    for column, design, label in zip(st.columns(2), (lower, higher), ("95% DESIGN", "99% DESIGN"), strict=True):
        with column:
            equipment_card(label, f"{percent(design['worst_served_fraction'], 2)} annual demand served", money(design["net_present_cost_usd"]), {
                "Net present cost": money(design["net_present_cost_usd"]),
                "Loss-of-load": f"{design['loss_of_load_hours']} h",
                "Unmet energy": energy(design["unmet_energy_kwh"]),
            })
    npc_change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout(
        "The Rodina reliability-cost tradeoff",
        f"Moving from 95% to 99% annual energy served increases modeled NPC by {npc_change:.1f}%—from {money(lower['net_present_cost_usd'])} to {money(higher['net_present_cost_usd'])}. This finding is specific to the frozen Rodina assumptions.",
    )
    comparison_table(design_comparison_rows(lower, higher))

    section_header("How the benchmark works")
    workflow(("Weather + demand", "Wind / PV models", "Hourly dispatch", "Reliability", "Sizing", "Economics", "Sensitivity"))
    st.caption("Ordinary navigation reads frozen outputs. It never launches the Phase 10 optimizer or Phase 11/12 pipelines.")


def demand_weather(api: PlanningService) -> None:
    page_header("Study · Inputs", "Demand & weather", "Inspect what drives the benchmark—and distinguish reconstructed, reanalysis-derived, and modeled quantities.", [("2025", "info"), ("8,760 HOURS", "success"), ("UTC+05:00", "info")])
    demand_tab, weather_tab = st.tabs(["Demand reconstruction", "ERA5 weather"])
    with demand_tab:
        profile = profile_selector("demand_profile")
        with st.spinner("Preparing aligned local benchmark traces…"):
            frame = api.demand_weather_frame(profile)
        source = api.provenance()["demand"]
        section_header("Published values and benchmark choice")
        a, b, c = st.columns(3)
        with a: metric("Published annual value", energy(source["printed_annual_kwh"]))
        with b: metric("Published monthly rows", energy(source["monthly_rows_reconstructed_annual_kwh"]))
        with c: metric("SteppeGrid benchmark", energy(source["monthly_rows_reconstructed_annual_kwh"]))
        callout("Why 8.02 GWh?", "The printed annual row is 7.72 GWh, while the published monthly rows sum to 8.02 GWh. SteppeGrid preserves both and uses the monthly-row sum for reconstruction.", "warning")
        section_header("Monthly energy", "Every load shape preserves the same published monthly totals.")
        st.altair_chart(bar_chart(monthly_energy(frame, "load_kwh"), "month", "energy_kwh", y_title="Monthly demand (kWh)"), width="stretch")
        first, last = frame["timestamp"].iloc[0].date(), frame["timestamp"].iloc[-1].date()
        dates = st.date_input("Representative hourly window", (first, min(first + timedelta(days=6), last)), min_value=first, max_value=last, key="demand_dates")
        if isinstance(dates, (tuple, list)) and len(dates) == 2:
            selected = date_window(frame, dates[0], dates[1])
            st.altair_chart(line_chart(selected, {"load_kwh": (readable(profile), COLORS["served"])}, "Hourly demand (kWh)"), width="stretch")
        comparison = date_window(api.demand_comparison_frame(), first, first + timedelta(days=6))
        section_header("Load-shape comparison", "The first week illustrates timing differences without implying measured hourly behavior.")
        st.altair_chart(line_chart(comparison, {
            "flat_within_month": ("Flat within month", COLORS["neutral"]),
            "residential_like": ("Residential-like", COLORS["primary"]),
            "community_facility_like": ("Community-facility-like", COLORS["solar"]),
        }, "Hourly demand (kWh)"), width="stretch")
        with st.expander("View selected hourly data"):
            st.dataframe(selected if "selected" in locals() else frame.head(168), hide_index=True, width="stretch")
        callout("Demand provenance", RECONSTRUCTION_NOTICE)

    with weather_tab:
        with st.spinner("Reading the frozen local ERA5 cache…"):
            weather = api.demand_weather_frame("residential_like")
        manifest = api.provenance(); site = manifest["site"]
        section_header("Resource summary", f"Cached Open-Meteo ERA5 for {site['latitude']:.6f}, {site['longitude']:.6f}; no live fetch occurs during navigation.")
        a, b, c, d = st.columns(4)
        with a: metric("Mean wind at 100 m", f"{weather['wind_speed_100m_m_s'].mean():.2f} m/s")
        with b: metric("Annual GHI", f"{weather['ghi_w_m2'].sum()/1000:,.0f} kWh/m²")
        with c: metric("Mean temperature", f"{weather['temperature_c'].mean():.1f} °C")
        with d: metric("Coverage", f"{len(weather):,} h")
        first = weather["timestamp"].iloc[0].date(); sample = date_window(weather, first, first + timedelta(days=13))
        wind_tab, solar_tab, temperature_tab = st.tabs(["Wind", "Solar", "Temperature"])
        with wind_tab:
            st.altair_chart(line_chart(sample, {"wind_speed_10m_m_s": ("10 m", COLORS["neutral"]), "wind_speed_100m_m_s": ("100 m", COLORS["wind"])}, "Wind speed (m/s)"), width="stretch")
        with solar_tab:
            st.altair_chart(area_chart(sample, {"ghi_w_m2": ("GHI", COLORS["solar"])}, "Irradiance (W/m²)"), width="stretch")
        with temperature_tab:
            st.altair_chart(line_chart(sample, {"temperature_c": ("Temperature", COLORS["curtailment"])}, "Temperature (°C)"), width="stretch")
        st.info("ERA5 is gridded reanalysis, not an on-site weather measurement campaign.")


def renewable_generation(api: PlanningService) -> None:
    page_header("Study · Physical models", "Renewable generation", "Compare catalogued commercial equipment and inspect frozen Phase 9 modeled output traces.", [("CERTIFICATION SOURCES", "success"), ("ERA5-DERIVED SHEAR", "warning")])
    with st.spinner("Preparing frozen Phase 9 equipment traces…"):
        wind_rows, pv_rows = api.generation_catalog()
    wind, pv = pd.DataFrame(wind_rows), pd.DataFrame(pv_rows)
    section_header("Wind equipment", "Annual energy and capacity factor are shown separately so rated scale remains explicit.")
    for column, row in zip(st.columns(3), wind.to_dict("records"), strict=True):
        with column:
            equipment_card("WIND TURBINE", f"{row['manufacturer']} {row['model']}", energy(row["annual_generation_kwh"]), {
                "Rated power": power(row["rated_power_kw"]), "Hub height": f"{row['hub_height_m']:.1f} m", "Capacity factor": percent(row["capacity_factor"], 2),
            })
    left, right = st.columns(2)
    with left: st.altair_chart(wind_comparison(wind, "annual_generation_kwh", "Annual energy per turbine (kWh)"), width="stretch")
    with right: st.altair_chart(wind_comparison(wind, "capacity_factor", "Capacity factor", COLORS["primary"]), width="stretch")
    selected_wind = st.selectbox("Inspect turbine trace", wind["equipment_key"].tolist(), format_func=lambda key: wind.loc[wind["equipment_key"] == key, "model"].iloc[0])

    section_header("PV equipment blocks", "Select a supported module/inverter pairing for compact modeled-performance details.")
    selected_pv = st.selectbox("PV module / inverter block", pv["equipment_key"].tolist(), format_func=lambda key: f"{pv.loc[pv['equipment_key'] == key, 'module'].iloc[0]} · {pv.loc[pv['equipment_key'] == key, 'inverter'].iloc[0]}")
    pv_row = pv.loc[pv["equipment_key"] == selected_pv].iloc[0]
    equipment_card("PV BLOCK", f"{pv_row['module']} · {pv_row['inverter']}", energy(pv_row["annual_ac_kwh"]), {
        "Block capacity": f"{pv_row['dc_capacity_kw']:.1f} kWdc / {pv_row['ac_capacity_kw']:.1f} kWac",
        "Specific yield": f"{pv_row['ac_specific_yield_kwh_per_kwp']:,.1f} kWh/kWp",
        "POA / clipping": f"{pv_row['annual_poa_kwh_m2']:,.1f} kWh/m² · {pv_row['clipping_kwh']:,.1f} kWh",
    })
    trace = api.generation_frame(selected_wind, selected_pv); first = trace["timestamp"].iloc[0].date(); example = date_window(trace, first, first + timedelta(days=6))
    section_header("Representative unit traces", "Interactive first-week output from the selected wind turbine and PV block.")
    st.altair_chart(line_chart(example, {"wind_kwh_per_unit": ("Wind turbine", COLORS["wind"]), "pv_kwh_per_block": ("PV block", COLORS["solar"])}, "Hourly modeled energy (kWh)"), width="stretch")
    callout("Model boundary", "Power curves come from certification/reference documentation. Rodina shear is ERA5-derived; wake and turbine-layout effects are not modeled.")


def system_design(api: PlanningService) -> None:
    page_header("Planning · Frozen portfolios", "System design", "Explore the two final robust designs and replay their hourly dispatch without running an optimizer.", [("PHASE 10 DESIGN", "success"), ("REPLAY ONLY", "info")])
    target = target_selector("design_target"); design = api.design(target); summary = api.nominal_dispatch_summary(target)
    section_header(f"{target:.0%} annual served-energy target", "Least-cost feasible robust design from the frozen Phase 10 staged discrete search.")
    wind_col, solar_col, storage_col = st.columns(3)
    with wind_col: design_card("WIND", f"{design['wind_count']} × {readable(design['wind_key'])}", power(design["installed_wind_kw"]), "Installed commercial-turbine capacity")
    with solar_col: design_card("SOLAR", f"{design['pv_count']} PV blocks", f"{power(design['installed_pv_ac_kw'])} AC", f"{power(design['installed_pv_dc_kw'])} DC")
    with storage_col: design_card("STORAGE", f"{design['battery_count']} × {readable(design['battery_key'])}", energy(design["installed_usable_battery_kwh"]), f"{power(design['battery_power_kw'])} charge/discharge power")
    section_header("Annual performance", "Binding-profile totals from the frozen nominal replay.")
    a, b, c, d = st.columns(4)
    with a: metric("Annual demand served", percent(design["worst_served_fraction"], 3), help_key="served_energy")
    with b: metric("Unmet energy", energy(design["unmet_energy_kwh"]))
    with c: metric("Curtailment", energy(design["curtailment_kwh"]), help_key="curtailment")
    with d: metric("Binding profile", readable(design["binding_load_profile"]), help_key="binding_profile")
    energy_flow(summary["wind_generation_kwh"], summary["pv_generation_kwh"], summary["served_energy_kwh"], summary["curtailed_energy_kwh"], summary["unmet_energy_kwh"])

    section_header("95% versus 99%", "Increasing the Rodina target requires substantial additional renewable capacity and lifetime modeled cost.")
    lower, higher = api.design(0.95), api.design(0.99)
    comparison_table(design_comparison_rows(lower, higher))
    npc_change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout("Cost of the higher target", f"The 99% design has {npc_change:.1f}% higher NPC and reduces annual unmet energy by {energy(lower['unmet_energy_kwh'] - higher['unmet_energy_kwh'])} under the declared Rodina assumptions.")

    section_header("Hourly dispatch explorer", "Use computed presets or choose a custom window; all charts share the selected interval.")
    profile = profile_selector("dispatch_profile")
    with st.spinner("Replaying the selected frozen design through hourly dispatch…"):
        frame = api.dispatch_frame(target, profile); events = api.deficit_events(target, profile)
    preset = st.segmented_control("Window", ["First week", "Longest deficit event", "Highest-curtailment week", "Custom"], default="First week", key="dispatch_preset")
    first, last = frame["timestamp"].iloc[0].date(), frame["timestamp"].iloc[-1].date()
    if preset == "Custom":
        dates = st.date_input("Custom date window", (first, min(first + timedelta(days=6), last)), min_value=first, max_value=last, key="dispatch_dates")
        if not isinstance(dates, (tuple, list)) or len(dates) != 2:
            st.info("Select both a start and end date to display dispatch."); return
        start, end = dates
    else:
        start, end = preset_dates(frame, preset, events)
        st.caption(f"Showing {start:%d %b %Y} to {end:%d %b %Y}")
    window = date_window(frame, start, end)
    st.altair_chart(line_chart(window, {"load_kwh": ("Load", COLORS["text"]), "wind_generation_kwh": ("Wind", COLORS["wind"]), "pv_generation_kwh": ("PV", COLORS["solar"]), "total_generation_kwh": ("Total renewable", COLORS["served"])}, "Hourly energy (kWh)", height=320), width="stretch")
    st.altair_chart(area_chart(window, {"battery_soc_kwh": ("Battery SOC", COLORS["storage"])}, "Stored energy (kWh)"), width="stretch")
    st.altair_chart(area_chart(window, {"unmet_energy_kwh": ("Unmet", COLORS["unmet"]), "curtailment_kwh": ("Curtailment", COLORS["curtailment"])}, "Hourly energy (kWh)"), width="stretch")
    with st.expander("View hourly dispatch data"):
        st.dataframe(window, hide_index=True, width="stretch")
    st.caption("Equipment counts and dispatch rules remain frozen. This explorer performs no optimization.")


def reliability(api: PlanningService) -> None:
    page_header("Planning · Performance", "Reliability", "Start with what the result means, then inspect energy deficits and their timing.", [("ENERGY-BASED", "info"), ("NOT UPTIME", "warning")])
    target = target_selector("reliability_target"); profile = profile_selector("reliability_profile")
    row = next(item for item in api.reliability_rows(target) if item["load_profile"] == profile)
    with st.spinner("Summarizing existing deficit timing…"):
        dispatch = api.dispatch_frame(target, profile); events = api.deficit_events(target, profile)
    callout(f"{target:.0%} DESIGN · {readable(profile)}", f"{percent(row['served_fraction'], 2)} of annual electricity demand is served. Unmet demand occurs during {row['loss_of_load_hours']} hours, with the longest continuous deficit lasting {row['longest_deficit_hours']} hours.")
    a, b, c = st.columns(3)
    with a: metric("Annual demand served", percent(row["served_fraction"], 3), help_key="served_energy")
    with b: metric("Energy-based LPSP", percent(1 - row["served_fraction"], 3), help_key="lpsp")
    with c: metric("Unmet energy", energy(row["unmet_energy_kwh"]))
    d, e, f = st.columns(3)
    with d: metric("Loss-of-load hours", f"{row['loss_of_load_hours']} h", help_key="lolh")
    with e: metric("Longest deficit", f"{row['longest_deficit_hours']} h")
    with f: metric("Maximum hourly deficit", energy(dispatch["unmet_energy_kwh"].max()))
    section_header("Across reconstructed load shapes")
    reliability_frame = pd.DataFrame(api.reliability_rows(target)); reliability_frame["served_percent"] = reliability_frame["served_fraction"] * 100; reliability_frame["profile"] = reliability_frame["load_profile"].map(readable)
    st.altair_chart(bar_chart(reliability_frame, "profile", "served_percent", y_title="Annual demand served (%)", color=COLORS["served"]), width="stretch")
    section_header("Deficit-event explorer", "Contiguous runs are summarized from the existing hourly unmet-energy trace; no new reliability standard is applied.")
    e1, e2, e3 = st.columns(3)
    with e1: metric("Deficit events", f"{len(events):,}")
    with e2: metric("Median duration", f"{events['duration_hours'].median():.1f} h" if not events.empty else "0 h")
    with e3: metric("Longest event", f"{events['duration_hours'].max():.0f} h" if not events.empty else "0 h")
    if not events.empty:
        durations = events["duration_hours"].value_counts().sort_index().rename_axis("duration_hours").reset_index(name="events")
        st.altair_chart(bar_chart(durations, "duration_hours", "events", x_title="Event duration (hours)", y_title="Number of events", color=COLORS["unmet"]), width="stretch")
        start, end = preset_dates(dispatch, "Longest deficit event", events); longest = date_window(dispatch, start, end)
        st.altair_chart(area_chart(longest, {"unmet_energy_kwh": ("Unmet energy", COLORS["unmet"])}, "Hourly unmet energy (kWh)"), width="stretch")
    st.info("Served-energy fraction measures the proportion of annual demand supplied. It is not equivalent to the percentage of hours with uninterrupted supply.")


def economics(api: PlanningService) -> None:
    page_header("Planning · Reference economics", "Economics", "Compare frozen planning-cost results without implying contractor bids or procurement quotations.", [("PHASE 10 ASSUMPTIONS", "success"), ("COMPARATIVE ESTIMATE", "warning")])
    target = target_selector("economics_target"); selected = api.design(target)
    section_header(f"{target:.0%} design economics")
    a, b, c, d = st.columns(4)
    with a: metric("Initial CAPEX", money(selected["initial_capex_usd"]))
    with b: metric("Net present cost", money(selected["net_present_cost_usd"]), help_key="npc")
    with c: metric("Equivalent annual cost", money(selected["equivalent_annual_cost_usd"]) + "/year", help_key="eac")
    with d: metric("Cost per served kWh", f"${selected['cost_per_served_kwh_usd']:.3f}")
    rows = []
    for value in (0.95, 0.99):
        design = api.design(value); rows.append({"target": f"{value:.0%}", "CAPEX": design["initial_capex_usd"], "NPC": design["net_present_cost_usd"], "EAC": design["equivalent_annual_cost_usd"]})
    frame = pd.DataFrame(rows)
    section_header("Cost comparison", "Totals only: the final output does not expose a validated component-level cost breakdown for display.")
    left, right = st.columns(2)
    with left: st.altair_chart(bar_chart(frame, "target", "NPC", y_title="Net present cost (USD)", color=COLORS["primary"]), width="stretch")
    with right: st.altair_chart(bar_chart(frame, "target", "EAC", y_title="Equivalent annual cost (USD/year)", color=COLORS["storage"]), width="stretch")
    lower, higher = api.design(0.95), api.design(0.99); change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout("Rodina cost interpretation", f"The 99% target increases modeled lifetime NPC by {change:.1f}% relative to the 95% target under the frozen Rodina assumptions.")
    st.caption("PV uses the final scale-aware economic class. Battery pricing is a reference methodology, not a procurement quote.")


def sensitivity(api: PlanningService) -> None:
    page_header("Analysis · Robustness", "Sensitivity", "See which deterministic research perturbations preserve or violate each frozen design target.", [("DETERMINISTIC", "warning"), ("NOT PROBABILISTIC", "warning")])
    target = target_selector("sensitivity_target"); frame = pd.DataFrame(api.fixed_sensitivity_rows(target))
    section_header("Physical scenarios", "The dashed threshold and explicit status text make pass/fail visible without relying on color alone.")
    st.altair_chart(sensitivity_chart(frame, target), width="stretch")
    scenario_names = [name for name in ("demand_low", "nominal", "demand_high", "pv_low", "pv_high", "wind_shear_low", "wind_shear_high", "resource_favorable", "resource_stress") if name in set(frame["scenario"])]
    selected_name = st.selectbox("Inspect scenario", scenario_names, format_func=readable)
    selected = frame.loc[frame["scenario"] == selected_name].iloc[0]; status = "MEETS TARGET" if selected["passes_target"] else "BELOW TARGET"
    callout(status, f"{readable(selected_name)} serves {percent(selected['served_fraction'], 3)} of annual demand, with {selected['loss_of_load_hours']} loss-of-load hours and a {selected['longest_deficit_hours']}-hour longest deficit.", "info" if selected["passes_target"] else "critical")
    section_header("Robustness margins", "The nominal least-cost systems sit very close to their reliability constraints.")
    margins = next(row for row in api.margin_rows() if row["target"] == target)
    a, b, c = st.columns(3)
    headroom = 100 * (margins["maximum_demand_multiplier_for_target"] - 1)
    with a: metric("Demand headroom", f"+{headroom:.2f}%")
    with b: metric("Minimum PV multiplier", f"{margins['minimum_pv_multiplier_for_target']:.4f}×")
    with c: metric("Maximum feasible shear α", f"{margins['maximum_wind_shear_for_target']:.4f}")
    callout("Small reliability margin", f"The nominal {target:.0%} design tolerates only about +{headroom:.2f}% additional annual demand before falling below its target.", "warning")
    with st.expander("Economic one-factor scenarios"):
        economic = frame.loc[frame["varied_assumption"].isin(["wind_capex_multiplier", "pv_capex_multiplier", "battery_capex_multiplier"]), ["scenario", "net_present_cost_usd", "equivalent_annual_cost_usd", "served_fraction"]]
        st.dataframe(economic, hide_index=True, width="stretch")
    st.info(SCENARIO_NOTICE)
    st.caption("Higher α is adverse because all modeled turbine hubs are below the ERA5 100 m reference height.")


def methodology(api: PlanningService) -> None:
    page_header("Research · Traceability", "Methodology & provenance", "Trace source classifications, validation evidence, limitations, and candidate-selection semantics.", [("FROZEN THROUGH PHASE 12", "success"), ("0 BLOCKERS", "success")])
    manifest, audit = api.provenance(), api.validation(); software = manifest["software"]
    section_header("Validation state")
    audit_status(len(audit["checks"]), audit["blockers"], audit["warnings"], software["repository_test_count_at_phase12"])
    with st.expander("View validation checks"):
        st.dataframe(pd.DataFrame(audit["checks"])[["category", "check", "status", "message"]], hide_index=True, width="stretch")
    section_header("Assumptions by evidence class", "Expand only the provenance category you need.")
    assumptions = pd.DataFrame(api.assumptions())
    for classification, rows in assumptions.groupby("classification", sort=False):
        with st.expander(readable(classification)):
            st.dataframe(rows[["input", "value", "unit", "provenance_or_note"]], hide_index=True, width="stretch")
    section_header("Provenance summary")
    a, b, c = st.columns(3)
    with a: design_card("SITE", f"{manifest['site']['name']}, {manifest['site']['region']}", str(manifest['site']['reference_year']), manifest['site']['timezone'])
    with b: design_card("WEATHER", manifest['weather']['dataset'], f"{manifest['weather']['records']:,} records", manifest['weather']['provider'])
    with c: design_card("DEMAND", "Literature reconstruction", energy(manifest['demand']['monthly_rows_reconstructed_annual_kwh']), "Not measured hourly demand")
    st.caption(f"Frozen git provenance: {software['git']}")
    metadata = api.adaptation_metadata()
    callout("Saved-candidate adaptation", "Adaptive results mean the least-cost feasible design among the saved Phase 10 candidate set. Full perturbed-scenario re-optimization was not performed.")
    st.caption(f"Single-profile label: {metadata['single_profile_comparison_provenance']['label']}")
    section_header("Scientific limitations", "Organized by the part of the evidence chain they affect.")
    limitations({
        "Data": ("Rodina hourly demand is reconstructed from published monthly energy.", "The benchmark uses one ERA5 weather year."),
        "Physical modeling": ("No wake or turbine-layout model.", "No detailed degradation or electrical power-flow model."),
        "Economics": ("Planning/reference assumptions are comparative estimates, not bids."),
        "Sensitivity": ("Scenario ranges are deterministic, not probability distributions or confidence intervals."),
        "Field case": (SHAMSHI_STATUS,),
    })


ROUTES = {
    "Overview": overview, "Demand & Weather": demand_weather, "Renewable Generation": renewable_generation,
    "System Design": system_design, "Reliability": reliability, "Economics": economics,
    "Sensitivity": sensitivity, "Methodology & Provenance": methodology,
}

if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Explore Benchmark"
with st.sidebar:
    st.markdown("## ⚡ SteppeGrid")
    left, right = st.columns(2)
    with left:
        if st.button("Explore", type="primary" if st.session_state.app_mode == "Explore Benchmark" else "tertiary", width="stretch"):
            st.session_state.app_mode = "Explore Benchmark"
            st.rerun()
    with right:
        if st.button("Plan", type="primary" if st.session_state.app_mode == "Plan a System" else "tertiary", width="stretch"):
            st.session_state.app_mode = "Plan a System"
            st.rerun()
    if st.session_state.app_mode == "Explore Benchmark":
        st.caption("EXPLORE BENCHMARK · RODINA")
        for group, pages in NAVIGATION.items():
            st.markdown(f'<div class="sg-nav-group">{group}</div>', unsafe_allow_html=True)
            for name in pages:
                if st.button(name, key=f"nav_{name}", type="primary" if st.session_state.active_page == name else "tertiary", width="stretch"):
                    st.session_state.active_page = name
                    st.rerun()
        st.divider()
        sidebar_status()
    else:
        st.caption("PLAN A SYSTEM · USER SCENARIO")
        st.info("Demand is always explicit. User scenarios are isolated from frozen benchmark outputs.")

try:
    if st.session_state.app_mode == "Plan a System":
        render_planner(scenario_service())
    else:
        ROUTES[st.session_state.active_page](service())
except AppDataError as error:
    st.error(str(error))
    st.code("python scripts/run_phase12.py --mode verify", language="powershell")
    st.stop()
