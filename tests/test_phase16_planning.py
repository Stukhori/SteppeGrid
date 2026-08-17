import json

import pytest

from steppegrid.equipment.catalog import EquipmentCatalogVersion
from steppegrid.optimization.economics import EconomicsVersion
from steppegrid.planning.models import CatalogFilterMode, PlanningScenario, TechnologySelection
from steppegrid.planning.service import ScenarioPlanningService
from steppegrid.sites import SiteRegistry


def _selection():
    return TechnologySelection(
        wind_keys=("northern_power_nps_100c_21",),
        pv_keys=("trina_tsm_450_neg9r28__sma_sunny_tripower_x_25",),
        battery_keys=("sungrow_powerstack_st255_2h",),
        filter_mode=CatalogFilterMode.CUSTOM,
    )


def test_generic_registered_site_plans_and_preserves_snapshot_and_output_isolation(tmp_path):
    registry = SiteRegistry(
        tmp_path / "registry", cache_root="data/weather/cache",
        output_root=tmp_path / "site_outputs",
    )
    site = registry.onboard_site(
        site_id="generic_village", name="Generic Village", region="Synthetic Region",
        country="Kazakhstan", latitude=50.578333, longitude=57.544722,
        timezone_name="Asia/Aqtobe", source_name="Test fixture",
    )
    registry.prepare_weather(site.site_id)
    demand = registry.create_annual_demand_dataset(
        site.site_id, demand_id="estimate_v1", name="Synthetic estimate v1", annual_kwh=30_000,
    )
    snapshot = registry.planning_site(site.site_id)
    scenario = PlanningScenario(
        name="Generic multi-site test", site=snapshot,
        demand=registry.demand_specification(site.site_id, demand.demand_id),
        demand_id=demand.demand_id, registered_demand_sha256=demand.demand_sha256,
        reliability_target=.95, technologies=_selection(),
        equipment_catalog_version=EquipmentCatalogVersion.PLANNER_V2,
        economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,
    )
    run = ScenarioPlanningService(
        registry=registry, cache_root="data/weather/cache",
        output_root=tmp_path / "legacy", site_output_root=tmp_path / "site_outputs",
    ).run(scenario)
    assert run.result.feasible
    assert run.result.site_id == site.site_id
    assert run.result.demand_id == demand.demand_id
    assert run.result.demand_sha256 == demand.demand_sha256
    assert run.result.site_metadata_hash == snapshot.site_metadata_hash
    assert run.result.site_snapshot == snapshot
    assert run.artifacts.directory.parent == tmp_path / "site_outputs" / site.site_id / "scenarios"
    provenance = json.loads(run.artifacts.provenance_json.read_text(encoding="utf-8"))
    assert provenance["site_snapshot"]["site_id"] == site.site_id
    assert provenance["demand_id"] == demand.demand_id

    old_hash = scenario.input_hash
    registry.create_annual_demand_dataset(
        site.site_id, demand_id="estimate_v2", name="Synthetic estimate v2", annual_kwh=40_000,
    )
    assert scenario.input_hash == old_hash
    assert scenario.site == snapshot
    history = registry.scenario_history(site.site_id)
    assert history[0]["scenario_id"] == scenario.scenario_id


def test_registered_shamshi_demand_is_explicitly_synthetic_not_field_validated():
    registry = SiteRegistry()
    dataset = registry.get_demand_dataset("shamshi_kaldayakova", "shamshi_demo_500mwh_community")
    scenario = PlanningScenario(
        name="Shamshi registered dataset metadata",
        site=registry.planning_site("shamshi_kaldayakova"),
        demand=registry.demand_specification("shamshi_kaldayakova", dataset.demand_id),
        demand_id=dataset.demand_id, registered_demand_sha256=dataset.demand_sha256,
        reliability_target=.95, technologies=_selection(),
    )
    assert scenario.site.site_classification == "FIELD_CASE"
    assert scenario.demand.source_type.value == "SYNTHETIC_ESTIMATE"
    assert "field" not in scenario.demand.method_notes.lower() or "not" in scenario.demand.method_notes.lower()


def test_registered_site_cannot_plan_before_weather_is_validated(tmp_path):
    registry = SiteRegistry(tmp_path / "registry", output_root=tmp_path / "outputs")
    site = registry.onboard_site(
        site_id="weather_missing_village", name="Weather Missing Village",
        region="Synthetic Region", country="Kazakhstan", latitude=50, longitude=60,
        timezone_name="Asia/Almaty", source_name="Test fixture",
    )
    demand = registry.create_annual_demand_dataset(
        site.site_id, demand_id="estimate_v1", name="Estimate", annual_kwh=30_000,
    )
    scenario = PlanningScenario(
        name="Must reject missing weather", site=registry.planning_site(site.site_id),
        demand=registry.demand_specification(site.site_id, demand.demand_id),
        demand_id=demand.demand_id, registered_demand_sha256=demand.demand_sha256,
        reliability_target=.95, technologies=_selection(),
    )
    service = ScenarioPlanningService(registry=registry, site_output_root=tmp_path / "outputs")
    with pytest.raises(ValueError, match="weather is not validated as CACHED"):
        service.review(scenario)
