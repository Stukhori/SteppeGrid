"""Read-only product views over the registered sites and saved planning results."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from steppegrid.sites import SiteRegistry

FEATURED_SITE_ID = "shamshi_kaldayakova"
FEATURED_SITE_LABEL = "MY VILLAGE"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def saved_results() -> tuple[dict, ...]:
    """Load saved results only; normal page views never run optimization."""
    root = project_root()
    results: list[dict] = []
    for result_path in sorted((root / "outputs").glob("**/result.json")):
        if "demo_registry" in result_path.parts or "phase16_example_village" in result_path.parts:
            continue
        try:
            row = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        site_id = row.get("site_id")
        if not site_id and "Shamshi" in str(row.get("scenario_name", "")):
            site_id = FEATURED_SITE_ID
        if site_id:
            row["site_id"] = site_id
            row["_path"] = str(result_path.relative_to(root)).replace("\\", "/")
            row["_phase17_standardized"] = "outputs/phase17/standardized_runs/" in row["_path"]
            results.append(row)
    return tuple(results)


def latest_result(site_id: str, target: float) -> dict | None:
    matches = [r for r in saved_results() if r.get("site_id") == site_id and float(r.get("reliability_target", 0)) == target]
    if not matches:
        return None
    # Prefer the current registered-demand result, then the newest saved artifact.
    site = SiteRegistry().get_site(site_id)
    demand = site.demand_datasets[0].annual_energy_kwh if site.demand_datasets else None
    matches.sort(key=lambda r: (not r.get("_phase17_standardized", False), abs(float(r.get("annual_demand_kwh", 0)) - demand) if demand else 0, r["_path"]))
    return matches[0]


def site_rows(registry: SiteRegistry) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for site in registry.list_sites():
        demand = site.demand_datasets[0].annual_energy_kwh if site.demand_datasets else None
        rows.append({
            "site_id": site.site_id,
            "Site": site.name,
            "Region": site.region,
            "Population": site.population,
            "Annual demand (GWh/year)": round(demand / 1_000_000, 2) if demand else None,
            "Weather": "Ready" if site.weather_datasets else "Unavailable",
            "95% result": "Available" if latest_result(site.site_id, .95) or site.site_id == "rodina" else "Not available",
            "99% result": "Available" if latest_result(site.site_id, .99) or site.site_id == "rodina" else "Not available",
            "lat": site.latitude,
            "lon": site.longitude,
            "featured_site": site.site_id == FEATURED_SITE_ID,
        })
    return rows


def weather_summary(site) -> dict[str, float | int]:
    resources = pd.read_csv(project_root() / "outputs/phase17/site_resource_metrics.csv")
    matches = resources.loc[resources["site_id"] == site.site_id]
    if matches.empty:
        return {}
    row = matches.iloc[0]
    return {
        "hours": int(row["weather_hours"]),
        "wind_capacity_factor": float(row["wind_capacity_factor"]),
        "pv_specific_yield_kwh_per_kwp": float(row["pv_specific_yield_kwh_per_kwp"]),
    }


@lru_cache(maxsize=1)
def phase17_findings() -> dict[str, str]:
    resources = pd.read_csv(project_root() / "outputs/phase17/site_resource_metrics.csv")
    normalized = pd.read_csv(project_root() / "outputs/phase17/normalized_metrics.csv")
    escalation = pd.read_csv(project_root() / "outputs/phase17/reliability_escalation.csv")
    proxy_resources = resources.loc[resources["cohort"] == "primary_proxy"]
    proxy_95 = normalized.loc[(normalized["cohort"] == "primary_proxy") & (normalized["target"] == .95)]
    proxy_ids = set(proxy_95["site_id"])
    proxy_escalation = escalation.loc[escalation["site_id"].isin(proxy_ids)]
    return {
        "highest_solar": proxy_resources.loc[proxy_resources["pv_specific_yield_kwh_per_kwp"].idxmax(), "site"],
        "highest_wind": proxy_resources.loc[proxy_resources["wind_capacity_factor"].idxmax(), "site"],
        "lowest_normalized_npc": proxy_95.loc[proxy_95["NPC_per_annual_kWh_demand"].idxmin(), "site"],
        "largest_escalation": proxy_escalation.loc[proxy_escalation["delta_NPC_percent"].idxmax(), "site"],
    }
