"""Validate the site registry and demonstrate generic-site onboarding/planning."""

from __future__ import annotations

import json
import time
from pathlib import Path

from steppegrid.equipment.catalog import PLANNER_V2
from steppegrid.optimization.economics import EconomicsVersion
from steppegrid.planning.models import CatalogFilterMode, PlanningScenario, TechnologySelection
from steppegrid.planning.service import ScenarioPlanningService
from steppegrid.sites import SiteClassification, SiteRegistry, SiteRegistryError

OUTPUT = Path("outputs/phase16")
DEMO_SITE_ID = "phase16_example_village"
DEMO_DEMAND_ID = "synthetic_30mwh_v1"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    started = time.perf_counter()
    registry = SiteRegistry()
    timings = registry.performance_snapshot()
    audit = registry.validate_registry(write_output=True)
    if audit.blockers:
        raise RuntimeError(f"built-in registry has {audit.blockers} blocker(s)")

    demo_registry = SiteRegistry(
        OUTPUT / "demo_registry", cache_root="data/weather/cache",
        output_root=OUTPUT / "sites",
    )
    onboarding_started = time.perf_counter()
    try:
        site = demo_registry.get_site(DEMO_SITE_ID)
    except SiteRegistryError:
        site = demo_registry.onboard_site(
            site_id=DEMO_SITE_ID,
            name="Phase 16 Example Village",
            region="Synthetic Test Region",
            country="Kazakhstan",
            latitude=50.578333,
            longitude=57.544722,
            timezone_name="Asia/Aqtobe",
            classification=SiteClassification.PLANNING_SITE,
            source_name="Phase 16 architecture demonstration",
            notes="Synthetic/non-production registry fixture using an existing cached coordinate solely to demonstrate generic onboarding.",
        )
    if not site.demand_datasets:
        demo_registry.create_annual_demand_dataset(
            DEMO_SITE_ID, demand_id=DEMO_DEMAND_ID,
            name="Synthetic 30 MWh demonstration",
            annual_kwh=30_000,
            method="Synthetic Phase 16 software demonstration distributed with a deterministic community-facility-like profile.",
            source_name="Phase 16 architecture demonstration",
        )
    onboarding_seconds = time.perf_counter() - onboarding_started

    weather_started = time.perf_counter()
    if demo_registry.get_weather_status(DEMO_SITE_ID).value != "CACHED":
        demo_registry.prepare_weather(DEMO_SITE_ID)
    weather_seconds = time.perf_counter() - weather_started

    demand = demo_registry.get_demand_dataset(DEMO_SITE_ID, DEMO_DEMAND_ID)
    scenario = PlanningScenario(
        name="Phase 16 generic-site planning demonstration",
        site=demo_registry.planning_site(DEMO_SITE_ID),
        demand=demo_registry.demand_specification(DEMO_SITE_ID, DEMO_DEMAND_ID),
        demand_id=demand.demand_id,
        registered_demand_sha256=demand.demand_sha256,
        reliability_target=.95,
        equipment_catalog_version=PLANNER_V2.version,
        economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,
        technologies=TechnologySelection(
            wind_keys=("northern_power_nps_100c_21",),
            pv_keys=("trina_tsm_450_neg9r28__sma_sunny_tripower_x_25",),
            battery_keys=("sungrow_powerstack_st255_2h",),
            filter_mode=CatalogFilterMode.CUSTOM,
        ),
    )
    planning_started = time.perf_counter()
    service = ScenarioPlanningService(
        registry=demo_registry, cache_root="data/weather/cache",
        output_root=OUTPUT / "temporary_scenarios",
        site_output_root=OUTPUT / "sites",
    )
    run = service.run(scenario)
    planning_seconds = time.perf_counter() - planning_started
    if not run.result.feasible:
        raise RuntimeError("generic-site planning demonstration found no feasible design")

    demo_audit = demo_registry.validate_registry()
    summary = {
        "schema_version": "phase16.summary.v1",
        "built_in_registry_audit": audit.model_dump(mode="json"),
        "generic_site": demo_registry.get_site(DEMO_SITE_ID).model_dump(mode="json"),
        "generic_site_readiness": demo_registry.get_planning_readiness(DEMO_SITE_ID).value,
        "generic_site_audit": demo_audit.model_dump(mode="json"),
        "planning_result": run.result.model_dump(mode="json"),
        "output_path": str(run.artifacts.directory if run.artifacts else ""),
        "performance_seconds": {
            "registry_load": timings.registry_load_seconds,
            "registry_validation": timings.validation_seconds,
            "demand_dataset_indexing": timings.demand_index_seconds,
            "onboarding_excluding_weather": onboarding_seconds,
            "weather_prepare_cache_or_fetch": weather_seconds,
            "demonstration_planning": planning_seconds,
            "total": time.perf_counter() - started,
        },
        "interpretation": "Synthetic software architecture demonstration; not scientific evidence about a village.",
        "phase17_cross_site_analysis_performed": False,
    }
    _write_json(OUTPUT / "phase16_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
