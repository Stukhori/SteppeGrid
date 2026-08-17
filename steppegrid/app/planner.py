"""Streamlit workflow for Phase 14 user-defined planning scenarios."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from steppegrid.app.components import callout, metric, page_header, section_header
from steppegrid.app.formatting import energy, money, percent, readable
from steppegrid.equipment.catalog import BATTERIES, INVERTERS, PV_MODULES, WIND_TURBINES
from steppegrid.planning.demand import PlanningDemandError, demand_preview, parse_hourly_demand_csv
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.service import PlanningRun, ScenarioPlanningService

SITE_PRESETS = {
    "Rodina benchmark site": (SitePreset.RODINA, "Rodina", 51.302445, 70.541645, "+05:00"),
    "Shamshi Kaldayakova": (SitePreset.SHAMSHI, "Shamshi Kaldayakova", 50.578333, 57.544722, "+05:00"),
    "Custom coordinates": (SitePreset.CUSTOM, "Custom site", 50.0, 67.0, "+05:00"),
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def result_is_stale(result, scenario: PlanningScenario | None) -> bool:
    return scenario is None or result.scenario_input_hash != scenario.input_hash


def _source_configuration(mode: DemandMode) -> tuple[DemandSourceType, DemandConfidence]:
    if mode is DemandMode.RODINA_BENCHMARK:
        return DemandSourceType.SOURCE_RECONSTRUCTED, DemandConfidence.STRONG_SOURCE_RECONSTRUCTION
    label = st.selectbox(
        "Demand evidence class",
        [DemandSourceType.SYNTHETIC_ESTIMATE, DemandSourceType.PROXY_DERIVED],
        format_func=lambda value: readable(value.value),
        key="planner_demand_source",
    )
    confidence = DemandConfidence.PROXY_ESTIMATE if label is DemandSourceType.PROXY_DERIVED else DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE
    return label, confidence


def _build_inputs() -> tuple[PlanningScenario | None, object | None, str | None]:
    section_header("1 · Site", "Choose a known site or enter explicit coordinates.")
    site_label = st.selectbox("Site preset", list(SITE_PRESETS), key="planner_site")
    preset, default_name, default_lat, default_lon, default_offset = SITE_PRESETS[site_label]
    if preset is SitePreset.CUSTOM:
        name = st.text_input("Site name", value=default_name, key="planner_site_name")
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=default_lat, format="%.6f")
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=default_lon, format="%.6f")
        timezone_offset = st.text_input("Fixed UTC offset", value=default_offset)
    else:
        name, latitude, longitude, timezone_offset = default_name, default_lat, default_lon, default_offset
        st.caption(f"{latitude:.6f}, {longitude:.6f} · fixed offset {timezone_offset}")
    st.info("Weather: Open-Meteo ERA5, 2025 hourly reanalysis. A live request occurs only after Run Planner if the exact cache is absent.")

    section_header("2 · Demand", "Provide the demand magnitude, timing assumption, and evidence class.")
    allowed_modes = [DemandMode.ESTIMATED_ANNUAL, DemandMode.ESTIMATED_MONTHLY, DemandMode.HOURLY_UPLOAD]
    if preset is SitePreset.RODINA:
        allowed_modes.insert(0, DemandMode.RODINA_BENCHMARK)
    mode = st.selectbox("Demand workflow", allowed_modes, format_func=lambda value: readable(value.value), key="planner_demand_mode")
    shape = st.selectbox(
        "Deterministic hourly shape",
        ["community_facility_like", "residential_like", "flat_within_month"],
        format_func=readable, key="planner_shape", disabled=mode is DemandMode.HOURLY_UPLOAD,
    )
    annual = None; monthly = None; uploaded = None
    upload_filename = upload_hash = None
    source_name = source_url = None; source_year = None
    if mode is DemandMode.RODINA_BENCHMARK:
        source_type, confidence = _source_configuration(mode)
        method = "Frozen Phase 9 literature monthly-row reconstruction"
    elif mode is DemandMode.HOURLY_UPLOAD:
        source_type = st.selectbox(
            "Uploaded data classification",
            [DemandSourceType.USER_PROVIDED, DemandSourceType.MEASURED, DemandSourceType.SOURCE_REPORTED, DemandSourceType.PROXY_DERIVED],
            format_func=lambda value: readable(value.value),
        )
        confidence = DemandConfidence.MEASURED if source_type is DemandSourceType.MEASURED else (DemandConfidence.PROXY_ESTIMATE if source_type is DemandSourceType.PROXY_DERIVED else DemandConfidence.USER_PROVIDED_UNVERIFIED)
        upload = st.file_uploader("Hourly CSV", type="csv", help="Exact columns: timestamp,demand_kwh. Values are kWh per hourly interval.")
        method = st.text_input("Demand method / source note", value="User-uploaded hourly demand CSV")
        if upload is not None:
            payload = upload.getvalue(); upload_filename = upload.name
            upload_hash = hashlib.sha256(payload).hexdigest()
            try:
                uploaded = parse_hourly_demand_csv(payload, source_type=source_type, confidence=confidence, method=method, source_name=upload.name)
            except PlanningDemandError as error:
                return None, None, str(error)
    else:
        source_type, confidence = _source_configuration(mode)
        if mode is DemandMode.ESTIMATED_ANNUAL:
            annual = st.number_input(
                "Estimated annual demand (kWh/year)", min_value=10_000.0,
                max_value=20_000_000.0, value=None, step=10_000.0,
                help="Required. SteppeGrid does not insert a site demand estimate.",
            )
        else:
            st.caption("Enter all 12 monthly energy totals in kWh.")
            values = []
            for start in range(0, 12, 4):
                columns = st.columns(4)
                for column, month in zip(columns, MONTHS[start:start + 4], strict=True):
                    with column:
                        values.append(st.number_input(month, min_value=0.0, value=0.0, step=1_000.0, key=f"planner_month_{month}"))
            monthly = tuple(values)
        source_name = st.text_input("Estimate or proxy source name", value="", help="Required for proxy-derived demand; optional for a user-authored synthetic estimate.") or None
        source_url = st.text_input("Source URL (optional)", value="") or None
        source_year_value = st.number_input("Source year (optional; 0 = unknown)", min_value=0, max_value=9998, value=0)
        source_year = int(source_year_value) or None
        method = st.text_area("Estimation method", value="User-specified energy estimate distributed with a deterministic planning profile.")

    section_header("3 · Reliability", "Choose annual served energy; this is not an uptime target.")
    target_label = st.segmented_control("Annual served-energy target", ["95%", "99%"], default="95%", key="planner_target")
    target = 0.95 if target_label == "95%" else 0.99
    section_header("4 · Technologies", "Limit the search to existing sourced catalog equipment.")
    wind_keys = tuple(st.multiselect("Wind turbines", list(WIND_TURBINES), default=["sd6"], format_func=readable))
    pv_options = [f"{module}__{inverter}" for module in PV_MODULES for inverter in INVERTERS]
    pv_keys = tuple(st.multiselect("PV module / inverter blocks", pv_options, default=["trina_tsm_450_neg9r28__sma_core1_stp50_41"], format_func=readable))
    battery_keys = tuple(st.multiselect("Battery systems", list(BATTERIES), default=["tesla_megapack_2h"], format_func=readable))
    with st.expander("Selected technology planning details"):
        details = []
        for key in wind_keys:
            item = WIND_TURBINES[key]
            details.append({"Technology": key, "Type": "Wind", "Rated scale": f"{item.rated_power_kw:g} kW", "Planning basis": "Phase 10 distributed-wind cost reference"})
        for key in pv_keys:
            module_key, inverter_key = key.split("__", 1)
            details.append({"Technology": key, "Type": "PV block", "Rated scale": f"{INVERTERS[inverter_key].rated_ac_power_kw:g} kWac", "Planning basis": "Phase 10 commercial/utility PV scale class"})
        for key in battery_keys:
            item = BATTERIES[key]
            details.append({"Technology": key, "Type": "Battery", "Rated scale": f"{item.usable_energy_capacity_kwh:g} kWh usable", "Planning basis": "Phase 10 generic Li-ion cost reference"})
        st.dataframe(pd.DataFrame(details), hide_index=True, width="stretch")
    scenario_name = st.text_input("Scenario name", value=f"{name} planning scenario")
    try:
        specification = DemandSpecification(
            mode=mode, source_type=source_type, confidence=confidence,
            profile_shape=shape, annual_kwh=annual, monthly_kwh=monthly,
            source_name=source_name, source_url=source_url, source_year=source_year,
            method_notes=method, upload_filename=upload_filename, upload_sha256=upload_hash,
        )
        scenario = PlanningScenario(
            name=scenario_name,
            site=PlanningSite(preset=preset, name=name, latitude=latitude, longitude=longitude, timezone_offset=timezone_offset),
            demand=specification, reliability_target=target,
            technologies=TechnologySelection(wind_keys=wind_keys, pv_keys=pv_keys, battery_keys=battery_keys),
        )
    except (ValidationError, ValueError) as error:
        return None, uploaded, str(error)
    return scenario, uploaded, None


def _render_result(run: PlanningRun) -> None:
    result = run.result
    section_header("Planning result", "This result belongs only to the hashed user scenario below.")
    if not result.feasible or result.design is None:
        callout("No feasible design found", "The supported bounded search did not find a portfolio meeting the selected target.", "critical")
        return
    design = result.design
    a, b, c, d = st.columns(4)
    metrics = result.metrics; economics = result.economics
    assert metrics is not None and economics is not None
    callout(
        "Estimated planning result" if result.demand_source_type is not DemandSourceType.MEASURED else "Measured-demand planning result",
        f"Demand basis: {result.demand_source_type.value} · {result.demand_confidence.value}. "
        f"The modeled system provides {design.wind_capacity_kw:,.1f} kW wind, "
        f"{design.pv_ac_capacity_kw:,.1f} kWac PV, and {design.battery_usable_capacity_kwh:,.1f} kWh usable storage "
        f"to serve {percent(metrics.served_fraction, 3)} of modeled annual energy.",
        "info",
    )
    with a: metric("Annual demand served", percent(metrics.served_fraction, 3))
    with b: metric("Unmet energy", energy(metrics.unmet_energy_kwh))
    with c: metric("Net present cost", money(economics.net_present_cost_usd))
    with d: metric("Loss-of-load hours", f"{metrics.loss_of_load_hours:,} h")
    st.dataframe(pd.DataFrame([
        {"Technology": "Wind", "Selection": readable(design.wind_key) if design.wind_key else "None", "Count": design.wind_count, "Capacity": f"{design.wind_capacity_kw:,.1f} kW"},
        {"Technology": "PV", "Selection": readable(design.pv_key) if design.pv_key else "None", "Count": design.pv_count, "Capacity": f"{design.pv_ac_capacity_kw:,.1f} kWac"},
        {"Technology": "Storage", "Selection": readable(design.battery_key) if design.battery_key else "None", "Count": design.battery_count, "Capacity": f"{design.battery_usable_capacity_kwh:,.1f} kWh usable"},
    ]), hide_index=True, width="stretch")
    st.caption(f"Method: {readable(result.optimizer_method)} · {result.evaluated_portfolios:,} renewable portfolios · {result.dispatch_simulations:,} cached dispatch simulations · {result.elapsed_seconds:.2f} s")
    st.caption(
        f"Longest deficit: {metrics.longest_deficit_hours:,} h · maximum hourly deficit: "
        f"{metrics.maximum_hourly_deficit_kwh:,.1f} kWh · curtailment: {energy(metrics.curtailment_kwh)} · "
        f"CAPEX: {money(economics.initial_capex_usd)} · EAC: {money(economics.equivalent_annual_cost_usd)}/year · "
        f"planning cost per served kWh: ${economics.cost_per_served_kwh_usd:.3f}"
    )
    dispatch = pd.DataFrame(run.dispatch_rows); dispatch["timestamp"] = pd.to_datetime(dispatch["timestamp"])
    window = st.selectbox("Dispatch window", ["First week", "Highest-unmet week", "Highest-curtailment week"])
    if window == "First week":
        start = dispatch["timestamp"].iloc[0]
    else:
        column = "unmet_energy_kwh" if window == "Highest-unmet week" else "curtailment_kwh"
        start = dispatch.loc[dispatch[column].idxmax(), "timestamp"] - timedelta(days=3)
    viewed = dispatch.loc[(dispatch["timestamp"] >= start) & (dispatch["timestamp"] < start + timedelta(days=7))]
    st.line_chart(viewed.set_index("timestamp")[["demand_kwh", "renewable_generation_kwh", "served_energy_kwh"]])
    st.area_chart(viewed.set_index("timestamp")[["battery_soc_end_kwh", "unmet_energy_kwh", "curtailment_kwh"]])
    export_json = json.dumps({"scenario": run.scenario.model_dump(mode="json"), "result": result.model_dump(mode="json")}, indent=2, sort_keys=True)
    summary_csv = pd.DataFrame([{
        "scenario_id": result.scenario_id, "scenario_input_hash": result.scenario_input_hash,
        "demand_sha256": result.demand_sha256, "weather_sha256": result.weather_sha256,
        "demand_source_type": result.demand_source_type.value,
        "demand_confidence": result.demand_confidence.value,
        "annual_demand_kwh": result.annual_demand_kwh, "target": result.reliability_target,
        "wind_key": design.wind_key, "wind_count": design.wind_count,
        "pv_key": design.pv_key, "pv_count": design.pv_count,
        "battery_key": design.battery_key, "battery_count": design.battery_count,
        "served_fraction": metrics.served_fraction,
        "unmet_energy_kwh": metrics.unmet_energy_kwh,
        "loss_of_load_hours": metrics.loss_of_load_hours,
        "curtailment_kwh": metrics.curtailment_kwh,
        "initial_capex_usd": economics.initial_capex_usd,
        "net_present_cost_usd": economics.net_present_cost_usd,
        "equivalent_annual_cost_usd": economics.equivalent_annual_cost_usd,
    }]).to_csv(index=False)
    left, right = st.columns(2)
    with left: st.download_button("Download result JSON", export_json, f"{result.scenario_id}.json", "application/json")
    with right: st.download_button("Download result CSV", summary_csv, f"{result.scenario_id}.csv", "text/csv")


def render_planner(api: ScenarioPlanningService) -> None:
    page_header(
        "Plan a System · Phase 14", "Interactive scenario planner",
        "Define demand explicitly, review provenance and weather coverage, then run the bounded generalized Phase 10 sizing method.",
        [("USER SCENARIO", "info"), ("ERA5 WEATHER", "info"), ("EXPLICIT RUN", "success")],
    )
    callout("Planning-model boundary", "A result is a modeled planning scenario—not a field-validated optimum, procurement quote, confidence interval, or probability distribution.", "warning")
    scenario, uploaded, error = _build_inputs()
    section_header("5 · Review & run", "The hash changes whenever a modeled input changes.")
    if error:
        st.warning(error)
    elif scenario is not None:
        try:
            demand, weather = api.review(scenario, uploaded)
            preview = demand_preview(demand)
            a, b, c, d, e = st.columns(5)
            with a: metric("Annual demand", energy(float(preview["annual_kwh"])))
            with b: metric("Peak hourly demand", energy(float(preview["peak_hourly_kwh"])))
            with c: metric("Demand confidence", str(preview["confidence"]))
            with d: metric("Weather cache", "READY" if weather["cache_available"] else "FETCH ON RUN")
            with e: metric("Load factor", percent(float(preview["load_factor"]), 1))
            st.bar_chart(pd.DataFrame({"month": MONTHS, "demand_kwh": preview["monthly_kwh"]}).set_index("month"))
            preview_frame = pd.DataFrame({"timestamp": demand.timestamps[:168], "demand_kwh": demand.demand_kwh[:168]}).set_index("timestamp")
            st.line_chart(preview_frame)
            st.caption(f"Scenario ID: `{scenario.scenario_id}` · input SHA-256: `{scenario.input_hash}`")
            st.caption(f"Demand: {preview['source_type']} · {preview['method']} · SHA-256 `{preview['sha256']}`")
            if scenario.site.preset is SitePreset.SHAMSHI:
                st.info("This will be labeled an estimated-demand planning scenario for Shamshi, not a field optimum.")
            if st.button("Run Planner", type="primary", width="stretch"):
                with st.status("Running planning workflow…", expanded=True) as status:
                    run = api.run(scenario, uploaded, progress=st.write)
                    status.update(label="Planning run complete", state="complete")
                st.session_state["planner_last_run"] = run
                st.session_state.setdefault("planner_history", []).append(run.result.model_dump(mode="json"))
        except Exception as run_error:
            st.error(str(run_error))
    run = st.session_state.get("planner_last_run")
    if isinstance(run, PlanningRun):
        if result_is_stale(run.result, scenario):
            st.warning("Inputs changed after the last run. The displayed result is stale; run the planner again.")
        _render_result(run)
    history = st.session_state.get("planner_history", [])
    if len(history) > 1:
        section_header("Session comparison", "Compare planning runs created in this browser session.")
        st.dataframe(pd.DataFrame([
            {"Scenario": row["scenario_name"], "Target": row["reliability_target"], "Annual demand (kWh)": row["annual_demand_kwh"], "Demand class": row["demand_source_type"], "Wind (kW)": row["design"]["wind_capacity_kw"] if row["design"] else None, "PV (kWac)": row["design"]["pv_ac_capacity_kw"] if row["design"] else None, "Storage (kWh)": row["design"]["battery_usable_capacity_kwh"] if row["design"] else None, "Served fraction": row["metrics"].get("served_fraction") if row["metrics"] else None, "LOLH": row["metrics"].get("loss_of_load_hours") if row["metrics"] else None, "Curtailment (kWh)": row["metrics"].get("curtailment_kwh") if row["metrics"] else None, "NPC (USD)": row["economics"].get("net_present_cost_usd") if row["economics"] else None, "Method": row["optimizer_method"]}
            for row in history
        ]), hide_index=True, width="stretch")
