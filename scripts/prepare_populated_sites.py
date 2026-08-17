"""Prepare 2025 ERA5 data and audits for built-in KZ_RURAL_PROXY_V1 sites."""

from __future__ import annotations

import argparse
import math

from steppegrid.sites import PlanningReadiness, SiteRegistry, WeatherStatus

METHODOLOGY_ID = "kz_rural_proxy_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-weather", action="store_true")
    parser.add_argument("--site-id", action="append", default=[])
    args = parser.parse_args()

    registry = SiteRegistry()
    method = registry.get_demand_methodology(METHODOLOGY_ID)
    candidates = [
        site for site in registry.list_sites()
        if any(
            demand.proxy_calculation is not None
            and demand.proxy_calculation.methodology_id == METHODOLOGY_ID
            for demand in site.demand_datasets
        )
    ]
    if args.site_id:
        selected = set(args.site_id)
        candidates = [site for site in candidates if site.site_id in selected]
        missing = selected - {site.site_id for site in candidates}
        if missing:
            raise ValueError(f"unknown populated site IDs: {sorted(missing)}")

    for site in candidates:
        demand = registry.get_demand_dataset(site.site_id, "proxy_rural_community_v1")
        trace = registry.build_demand(site.site_id, demand.demand_id)
        if len(trace.timestamps) != 8_760 or any(value < 0 for value in trace.demand_kwh):
            raise ValueError(f"invalid hourly demand trace for {site.site_id}")
        if not math.isclose(
            trace.annual_kwh,
            site.population * method.planning_kwh_per_capita,
            rel_tol=0,
            abs_tol=1e-6,
        ):
            raise ValueError(f"proxy energy mismatch for {site.site_id}")
        if (
            registry.get_weather_status(site.site_id) is not WeatherStatus.CACHED
            or args.refresh_weather
        ):
            registry.prepare_weather(
                site.site_id,
                year=2025,
                refresh=args.refresh_weather,
                allow_built_in_update=True,
            )
        readiness = registry.get_planning_readiness(site.site_id)
        if readiness is not PlanningReadiness.READY_FOR_PLANNING:
            raise ValueError(f"site is not planning-ready: {site.site_id} ({readiness.value})")
        print(
            f"{site.site_id}: {trace.annual_kwh:.3f} kWh, "
            f"weather={registry.get_weather_status(site.site_id).value}, "
            f"readiness={readiness.value}"
        )

    registry_audit = registry.validate_registry(write_output=True)
    populated_audit = registry.populated_sites_audit(write_output=True)
    if registry_audit.blockers or populated_audit.blockers:
        raise ValueError(
            f"audit blockers: registry={registry_audit.blockers}, "
            f"populated={populated_audit.blockers}"
        )
    print(
        f"registry: {registry_audit.registered_sites} sites, "
        f"{registry_audit.planning_ready_sites} ready, "
        f"{registry_audit.blockers} blockers"
    )


if __name__ == "__main__":
    main()
