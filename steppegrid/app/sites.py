"""Integrated Phase 16 site browser and local onboarding workflow."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from steppegrid.app.components import callout, metric, page_header, section_header
from steppegrid.app.formatting import readable
from steppegrid.planning.models import DemandConfidence, DemandSourceType
from steppegrid.sites import (
    SiteClassification,
    SiteOrigin,
    SiteRegistry,
    suggest_site_id,
)


def _site_rows(registry: SiteRegistry) -> list[dict[str, object]]:
    rows = []
    for site in registry.list_sites():
        demand_classes = sorted({item.classification.value for item in site.demand_datasets})
        rows.append({
            "Site": site.name,
            "Site ID": site.site_id,
            "Region": site.region,
            "Coordinates": f"{site.latitude:.6f}, {site.longitude:.6f}",
            "Classification": site.classification.value,
            "Origin": site.origin.value,
            "Weather": registry.get_weather_status(site.site_id).value,
            "Demand datasets": len(site.demand_datasets),
            "Demand evidence": ", ".join(demand_classes) or "MISSING",
            "Planning": registry.get_planning_readiness(site.site_id).value,
        })
    return rows


def render_sites(registry: SiteRegistry) -> None:
    page_header(
        "Sites · Phase 16", "Village registry & onboarding",
        "Browse registered villages or add a local planning site without changing model code.",
        [("FILE-BACKED", "success"), ("PROVENANCE", "info"), ("NO BATCH OPTIMIZATION", "warning")],
    )
    browse, add = st.tabs(["Browse sites", "Add new site"])
    with browse:
        rows = _site_rows(registry)
        section_header("Registered sites", "Status text accompanies every classification; no numerical confidence score is used.")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if rows:
            frame = pd.DataFrame([
                {"lat": site.latitude, "lon": site.longitude, "name": site.name}
                for site in registry.list_sites()
            ])
            st.map(frame, latitude="lat", longitude="lon")
        site_ids = [site.site_id for site in registry.list_sites()]
        selected_id = st.selectbox("Inspect site", site_ids, format_func=lambda value: registry.get_site(value).name)
        selected = registry.get_site(selected_id)
        a, b, c, d = st.columns(4)
        with a: metric("Classification", selected.classification.value)
        with b: metric("Weather", registry.get_weather_status(selected_id).value)
        with c: metric("Demand datasets", str(len(selected.demand_datasets)))
        with d: metric("Planning readiness", registry.get_planning_readiness(selected_id).value)
        st.download_button(
            "Export site JSON", registry.export_site(selected_id),
            file_name=f"{selected_id}.site.json", mime="application/json",
        )
        history = registry.scenario_history(selected_id)
        if history:
            section_header("Local scenario history")
            st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
        if selected.origin is SiteOrigin.BUILT_IN:
            st.info("Built-in site definitions are read-only and cannot be deleted from the UI.")
        else:
            with st.expander("Edit or remove this user site"):
                new_latitude = st.number_input("Updated latitude", -90.0, 90.0, selected.latitude, format="%.6f")
                new_longitude = st.number_input("Updated longitude", -180.0, 180.0, selected.longitude, format="%.6f")
                if st.button("Save coordinate change"):
                    registry.update_site_metadata(selected_id, latitude=new_latitude, longitude=new_longitude)
                    st.warning("Coordinates updated. Existing weather references are now STALE and must be prepared again.")
                    st.rerun()
                if st.button("Remove user site", type="secondary"):
                    registry.remove_site(selected_id)
                    st.success("User site removed. Historical scenario outputs were not deleted.")
                    st.rerun()
        audit = registry.validate_registry()
        section_header("Registry validation")
        st.caption(
            f"{audit.registered_sites} registered · {audit.valid_sites} valid · "
            f"{audit.planning_ready_sites} planning-ready · {audit.blockers} blockers · {audit.warnings} warnings"
        )
        if audit.checks:
            st.dataframe(pd.DataFrame([item.model_dump() for item in audit.checks]), hide_index=True, width="stretch")

    with add:
        section_header("1 · Site details", "All fields are validated before the local definition is saved.")
        name = st.text_input("Site name", key="onboard_name")
        suggested = suggest_site_id(name) if name else "new_village"
        site_id = st.text_input("Site ID", value=suggested, key="onboard_site_id")
        region = st.text_input("Region", key="onboard_region")
        country = st.text_input("Country", value="Kazakhstan", key="onboard_country")
        latitude = st.number_input("Site latitude", -90.0, 90.0, 50.0, format="%.6f", key="onboard_lat")
        longitude = st.number_input("Site longitude", -180.0, 180.0, 67.0, format="%.6f", key="onboard_lon")
        timezone_name = st.text_input("IANA timezone", value="Asia/Almaty", key="onboard_timezone")
        source_name = st.text_input("Site metadata source", value="User-provided site metadata")
        source_url = st.text_input("Site source URL (optional)") or None

        section_header("2 · Weather", "ERA5 is fetched only after the explicit onboarding action if the exact cache is absent.")
        prepare_weather = st.checkbox("Prepare/cache 2025 ERA5 weather", value=False)
        section_header("3 · Demand", "A site may be registered without demand; each attached dataset needs a stable ID.")
        demand_mode = st.selectbox("Demand onboarding mode", ["Annual estimate", "Monthly totals", "Hourly CSV", "No demand yet"])
        attach_demand = demand_mode != "No demand yet"
        demand_id = st.text_input("Demand dataset ID", value="planning_estimate_v1", disabled=not attach_demand)
        demand_name = st.text_input("Demand dataset name", value="Planning estimate v1", disabled=not attach_demand)
        annual_kwh = None
        monthly_values = None
        hourly_upload = None
        if demand_mode == "Annual estimate":
            annual_kwh = st.number_input("Annual demand (kWh/year)", 10_000.0, 20_000_000.0, 100_000.0, step=10_000.0)
        elif demand_mode == "Monthly totals":
            st.caption("Enter 12 monthly energy totals in kWh.")
            values = []
            for index, month in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")):
                values.append(st.number_input(month, min_value=0.0, value=10_000.0, step=1_000.0, key=f"onboard_month_{index}"))
            monthly_values = tuple(values)
        elif demand_mode == "Hourly CSV":
            hourly_upload = st.file_uploader("Hourly demand CSV", type="csv", help="Exact columns: timestamp,demand_kwh")
        evidence_options = (
            [DemandSourceType.USER_PROVIDED, DemandSourceType.MEASURED, DemandSourceType.SOURCE_REPORTED, DemandSourceType.PROXY_DERIVED]
            if demand_mode == "Hourly CSV"
            else [DemandSourceType.SYNTHETIC_ESTIMATE, DemandSourceType.PROXY_DERIVED]
        )
        demand_classification = st.selectbox(
            "Demand evidence class", evidence_options, format_func=lambda value: readable(value.value),
            disabled=not attach_demand,
        )
        demand_method = st.text_area(
            "Demand derivation notes",
            value="User planning assumption distributed with the deterministic community-facility-like hourly shape.",
            disabled=not attach_demand,
        )
        section_header("4 · Validate", "Synthetic-demand provenance produces a warning, not a false validation claim.")
        if st.button("Validate and save site", type="primary", width="stretch"):
            try:
                site = registry.onboard_site(
                    site_id=site_id, name=name, region=region, country=country,
                    latitude=latitude, longitude=longitude, timezone_name=timezone_name,
                    classification=SiteClassification.PLANNING_SITE,
                    source_name=source_name, source_url=source_url,
                )
                if attach_demand and demand_mode == "Annual estimate":
                    registry.create_annual_demand_dataset(
                        site.site_id, demand_id=demand_id, name=demand_name,
                        annual_kwh=annual_kwh, method=demand_method,
                        classification=demand_classification,
                        confidence=(DemandConfidence.PROXY_ESTIMATE if demand_classification is DemandSourceType.PROXY_DERIVED else DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE),
                    )
                elif attach_demand and demand_mode == "Monthly totals":
                    registry.create_monthly_demand_dataset(
                        site.site_id, demand_id=demand_id, name=demand_name,
                        monthly_kwh=monthly_values, method=demand_method,
                        classification=demand_classification,
                        confidence=(DemandConfidence.PROXY_ESTIMATE if demand_classification is DemandSourceType.PROXY_DERIVED else DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE),
                    )
                elif attach_demand and demand_mode == "Hourly CSV":
                    if hourly_upload is None:
                        raise ValueError("hourly CSV is required")
                    confidence = (
                        DemandConfidence.MEASURED if demand_classification is DemandSourceType.MEASURED
                        else DemandConfidence.PROXY_ESTIMATE if demand_classification is DemandSourceType.PROXY_DERIVED
                        else DemandConfidence.USER_PROVIDED_UNVERIFIED
                    )
                    registry.create_hourly_demand_dataset(
                        site.site_id, demand_id=demand_id, name=demand_name,
                        csv_payload=hourly_upload.getvalue(), method=demand_method,
                        classification=demand_classification, confidence=confidence,
                        source_name=hourly_upload.name,
                    )
                if prepare_weather:
                    with st.status("Preparing ERA5 weather…", expanded=True):
                        registry.prepare_weather(site.site_id)
                readiness = registry.get_planning_readiness(site.site_id)
                section_header("5 · Ready")
                callout(
                    "SITE SAVED",
                    f"Metadata PASS · Weather {registry.get_weather_status(site.site_id).value} · "
                    f"Demand {'PASS' if registry.list_demand_datasets(site.site_id) else 'MISSING'} · "
                    f"Planning {readiness.value}",
                    "info",
                )
                st.rerun()
            except ValueError as error:
                st.error(str(error))
