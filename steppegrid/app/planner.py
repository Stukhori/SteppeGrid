"""Streamlit workflow for catalog-versioned user planning scenarios."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from steppegrid.app.components import callout, metric, page_header, section_header
from steppegrid.app.formatting import energy, money, percent, readable
from steppegrid.equipment.catalog import PLANNER_V2
from steppegrid.equipment.models import ProjectScale
from steppegrid.planning.demand import PlanningDemandError, demand_preview, parse_hourly_demand_csv
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    CatalogFilterMode,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.service import PlanningRun, ScenarioPlanningService
from steppegrid.sites import SiteRegistry
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WIND_TURBINES = PLANNER_V2.wind_turbines
PV_MODULES = PLANNER_V2.pv_modules
INVERTERS = PLANNER_V2.inverters
BATTERIES = PLANNER_V2.batteries


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


def _build_inputs(registry: SiteRegistry) -> tuple[PlanningScenario | None, object | None, str | None]:
    section_header("1 · Site", "Choose a registered village or use temporary custom coordinates.")
    # Keep the established benchmark as the neutral landing state while exposing
    # every registered village. This ordering is not a site recommendation.
    classification_order = {"BENCHMARK": 0, "FIELD_CASE": 1, "PLANNING_SITE": 2}
    sites = sorted(
        registry.list_sites(),
        key=lambda site: (classification_order.get(site.classification.value, 99), site.name.casefold()),
    )
    options = {
        ("Rodina benchmark site" if site.site_id == "rodina" else site.name): site.site_id
        for site in sites
    }
    options["Custom coordinates"] = None
    site_label = st.selectbox("Site preset", list(options), key="planner_site")
    selected_site_id = options[site_label]
    registered_site = registry.get_site(selected_site_id) if selected_site_id else None
    if registered_site is None:
        name = st.text_input("Site name", value="Custom site", key="planner_site_name")
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=50.0, format="%.6f")
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=67.0, format="%.6f")
        timezone_offset = st.text_input("Fixed UTC offset", value="+05:00")
        try:
            planning_site = PlanningSite(
                preset=SitePreset.CUSTOM, name=name, latitude=latitude,
                longitude=longitude, timezone_offset=timezone_offset,
            )
        except ValidationError as error:
            return None, None, str(error)
    else:
        planning_site = registry.planning_site(registered_site.site_id)
        name = registered_site.name
        st.caption(
            f"{registered_site.latitude:.6f}, {registered_site.longitude:.6f} · "
            f"{registered_site.timezone} · {registry.get_planning_readiness(registered_site.site_id).value}"
        )
    st.info("Weather: Open-Meteo ERA5, 2025 hourly reanalysis. A live request occurs only after Run Planner if the exact cache is absent.")

    section_header("2 · Demand", "Provide the demand magnitude, timing assumption, and evidence class.")
    allowed_modes: list[DemandMode | str] = [DemandMode.ESTIMATED_ANNUAL, DemandMode.ESTIMATED_MONTHLY, DemandMode.HOURLY_UPLOAD]
    if registered_site and registered_site.demand_datasets:
        allowed_modes.append("registered_dataset")
    if registered_site and registered_site.classification.value == "BENCHMARK":
        allowed_modes.insert(0, DemandMode.RODINA_BENCHMARK)
    mode = st.selectbox(
        "Demand workflow", allowed_modes,
        format_func=lambda value: "Existing registered demand dataset" if value == "registered_dataset" else readable(value.value),
        key="planner_demand_mode",
    )
    shape = "community_facility_like"
    if mode != "registered_dataset":
        shape = st.selectbox(
            "Deterministic hourly shape",
            ["community_facility_like", "residential_like", "flat_within_month"],
            format_func=readable, key="planner_shape", disabled=mode is DemandMode.HOURLY_UPLOAD,
        )
    annual = None; monthly = None; uploaded = None
    upload_filename = upload_hash = None
    source_name = source_url = None; source_year = None
    demand_id = registered_demand_sha256 = None
    registered_specification = None
    if mode == "registered_dataset":
        assert registered_site is not None
        demand_options = {f"{item.name} · {item.classification.value}": item.demand_id for item in registered_site.demand_datasets}
        demand_label = st.selectbox("Registered demand dataset", list(demand_options), key="planner_registered_demand")
        demand_id = demand_options[demand_label]
        dataset = registry.get_demand_dataset(registered_site.site_id, demand_id)
        registered_demand_sha256 = dataset.demand_sha256
        registered_specification = registry.demand_specification(registered_site.site_id, demand_id)
        uploaded = registry.build_demand(registered_site.site_id, demand_id)
        st.caption(
            f"{dataset.annual_energy_kwh:,.0f} kWh/year · {dataset.classification.value} · "
            f"SHA-256 {dataset.demand_sha256[:12]}…"
        )
        source_type, confidence, method = dataset.classification, dataset.confidence, dataset.profile_method
        shape = dataset.profile_shape
    elif mode is DemandMode.RODINA_BENCHMARK:
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
    filter_mode = st.selectbox(
        "Catalog filter", list(CatalogFilterMode), index=0,
        format_func=lambda value: readable(value.value),
        help="All verified equipment evaluates the complete V2 catalog. Other filters are explicit scenario inputs.",
    )
    if filter_mode is CatalogFilterMode.SMALL_COMMUNITY:
        scales = (ProjectScale.SMALL_COMMUNITY, ProjectScale.COMMUNITY)
    elif filter_mode is CatalogFilterMode.MEDIUM_LARGE:
        scales = (ProjectScale.COMMERCIAL, ProjectScale.UTILITY)
    else:
        scales = tuple(ProjectScale)
    eligible_wind = [key for key, item in WIND_TURBINES.items() if item.scale_class in scales]
    eligible_inverters = [key for key, item in INVERTERS.items() if item.scale_class in scales]
    eligible_batteries = [key for key, item in BATTERIES.items() if item.scale_class in scales]
    pv_options = [f"{module}__{inverter}" for module in PV_MODULES for inverter in INVERTERS]
    eligible_pv = [key for key in pv_options if key.split("__", 1)[1] in eligible_inverters]
    if filter_mode is CatalogFilterMode.CUSTOM:
        wind_keys = tuple(st.multiselect("Wind turbines", list(WIND_TURBINES), default=["sd6"], format_func=readable))
        pv_keys = tuple(st.multiselect("PV module / inverter blocks", pv_options, default=["trina_tsm_450_neg9r28__sma_core1_stp50_41"], format_func=readable))
        battery_keys = tuple(st.multiselect("Battery systems", list(BATTERIES), default=["sungrow_powerstack_st255_2h"], format_func=readable))
    else:
        wind_keys, pv_keys, battery_keys = tuple(eligible_wind), tuple(eligible_pv), tuple(eligible_batteries)
        st.caption(f"Explicit filter includes {len(wind_keys)} wind models, {len(pv_keys)} PV configurations, and {len(battery_keys)} battery systems.")
    with st.expander("Catalog / technology details"):
        details = []
        for key in wind_keys:
            item = WIND_TURBINES[key]
            details.append({"Technology": key, "Type": "Wind", "Rated scale": f"{item.rated_power_kw:g} kW", "Planning hub height": f"{item.planning_hub_height_m or item.supported_hub_heights_m[0]:g} m", "Scale class": readable(item.scale_class.value), "Source": item.provenance[0].source_url})
        for key in pv_keys:
            module_key, inverter_key = key.split("__", 1)
            inverter = INVERTERS[inverter_key]
            details.append({"Technology": key, "Type": "PV block", "Rated scale": f"{inverter.rated_ac_power_kw:g} kWac", "Planning hub height": "—", "Scale class": readable(inverter.scale_class.value), "Source": inverter.provenance[0].source_url})
        for key in battery_keys:
            item = BATTERIES[key]
            details.append({"Technology": key, "Type": "Battery", "Rated scale": f"{item.usable_energy_capacity_kwh:g} kWh / {item.maximum_discharge_power_kw:g} kW", "Planning hub height": "—", "Scale class": readable(item.scale_class.value), "Source": item.provenance[0].source_url})
        st.dataframe(pd.DataFrame(details), hide_index=True, width="stretch")
    scenario_name = st.text_input("Scenario name", value=f"{name} planning scenario")
    try:
        specification = registered_specification or DemandSpecification(
            mode=mode, source_type=source_type, confidence=confidence,
            profile_shape=shape, annual_kwh=annual, monthly_kwh=monthly,
            source_name=source_name, source_url=source_url, source_year=source_year,
            method_notes=method, upload_filename=upload_filename, upload_sha256=upload_hash,
        )
        scenario = PlanningScenario(
            name=scenario_name,
            site=planning_site,
            demand=specification, reliability_target=target,
            demand_id=demand_id, registered_demand_sha256=registered_demand_sha256,
            technologies=TechnologySelection(wind_keys=wind_keys, pv_keys=pv_keys, battery_keys=battery_keys, filter_mode=filter_mode, scale_classes=scales),
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
    st.info(
        f"Site: {result.site_id or 'temporary custom'} · Demand: {result.demand_id or 'scenario input'} · "
        f"Catalog: {result.equipment_catalog_version.value} · Economics: {result.economics_version.value} · "
        f"options considered: {result.catalog_option_counts.get('wind', 0)} wind, "
        f"{result.catalog_option_counts.get('pv', 0)} PV, {result.catalog_option_counts.get('battery', 0)} battery."
    )
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
    st.caption(f"Method: {readable(result.optimizer_method)} · {result.theoretical_design_combinations:,} theoretical combinations · {result.evaluated_portfolios:,} renewable portfolios · {result.dispatch_simulations:,} dispatch simulations · {result.dispatch_cache_hits:,} cache hits · {result.elapsed_seconds:.2f} s")
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
        "site_id": result.site_id, "site_metadata_hash": result.site_metadata_hash,
        "demand_id": result.demand_id,
        "equipment_catalog_version": result.equipment_catalog_version.value,
        "economics_version": result.economics_version.value,
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


def render_planner(api: ScenarioPlanningService, registry: SiteRegistry | None = None) -> None:
    registry = registry or api.registry
    page_header(
        "Plan a System · Phase 16", "Multi-village scenario planner",
        "Select a registered site and demand dataset, or use temporary coordinates, then run Planner V2.",
        [("USER SCENARIO", "info"), ("ERA5 WEATHER", "info"), ("EXPLICIT RUN", "success")],
    )
    callout("Planning-model boundary", "A result is a modeled planning scenario—not a field-validated optimum, procurement quote, confidence interval, or probability distribution.", "warning")
    scenario, uploaded, error = _build_inputs(registry)
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
            if scenario.site.site_classification == "FIELD_CASE":
                st.info("FIELD_CASE is descriptive only. Synthetic or proxy demand does not make this a field-validated result.")
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
    if scenario is not None and scenario.site.site_id:
        persisted = registry.scenario_history(scenario.site.site_id)
        if persisted:
            section_header("Site scenario history", "Local historical results retain their original site and demand hashes.")
            st.dataframe(pd.DataFrame(persisted), hide_index=True, width="stretch")
