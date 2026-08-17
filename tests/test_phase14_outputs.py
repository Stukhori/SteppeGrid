import hashlib
import json
from datetime import datetime, timezone

from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningDesign,
    PlanningResult,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.outputs import write_scenario_outputs


def _scenario(name, annual):
    return PlanningScenario(
        name=name,
        site=PlanningSite(preset=SitePreset.SHAMSHI, name="Shamshi", latitude=50.578333, longitude=57.544722),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            annual_kwh=annual, method_notes="Explicit user estimate",
        ),
        reliability_target=0.95,
        technologies=TechnologySelection(wind_keys=("sd6",)),
    )


def _result(scenario):
    return PlanningResult(
        scenario_id=scenario.scenario_id, scenario_name=scenario.name,
        scenario_input_hash=scenario.input_hash, demand_sha256="a" * 64,
        weather_cache_key="weather-key", weather_cache_status="HIT",
        weather_sha256="b" * 64,
        weather_source="Open-Meteo Historical Weather API", weather_model="ERA5",
        weather_start_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        weather_end_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scenario_timezone="+05:00", annual_demand_kwh=500_000,
        demand_source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
        demand_confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        demand_method="Explicit user estimate", reliability_target=0.95,
        feasible=True,
        design=PlanningDesign(
            wind_key="sd6", wind_count=2, pv_key=None, pv_count=0,
            battery_key=None, battery_count=0, wind_capacity_kw=10.4,
            pv_dc_capacity_kw=0, pv_ac_capacity_kw=0, battery_usable_capacity_kwh=0,
        ),
        metrics={"annual_load_kwh": 500_000.0, "renewable_generation_kwh": 600_000.0, "served_fraction": 0.96, "lpsp": 0.04, "served_energy_kwh": 480_000.0, "unmet_energy_kwh": 20_000.0, "loss_of_load_hours": 50, "longest_deficit_hours": 5, "maximum_hourly_deficit_kwh": 10, "curtailment_kwh": 100_000, "curtailment_fraction": 1/6, "battery_throughput_kwh": 0},
        economics={"initial_capex_usd": 100, "net_present_cost_usd": 123.0, "equivalent_annual_cost_usd": 8, "cost_per_served_kwh_usd": 8/480_000, "economic_classes": {"wind": "test"}, "reference_capex_basis": {"wind": "test"}, "economic_sources": {"wind": None}}, optimizer_method="exact_reduced_space",
        evaluated_portfolios=3, dispatch_simulations=3, elapsed_seconds=0.1,
        assumptions=("Planning result",), software_version="test",
    )


def test_scenario_exports_are_isolated_and_hash_verified(tmp_path):
    first = _scenario("First", 500_000)
    second = _scenario("Second", 600_000)
    first_files = write_scenario_outputs(first, _result(first), [{"timestamp": "2025-01-01T00:00:00+00:00"}], output_root=tmp_path)
    second_files = write_scenario_outputs(second, _result(second), [{"timestamp": "2025-01-01T00:00:00+00:00"}], output_root=tmp_path)
    assert first_files.directory != second_files.directory
    assert first_files.directory.parent == tmp_path
    assert second_files.directory.parent == tmp_path
    provenance = json.loads(first_files.provenance_json.read_text(encoding="utf-8"))
    for filename, expected in provenance["file_sha256"].items():
        actual = hashlib.sha256((first_files.directory / filename).read_bytes()).hexdigest()
        assert actual == expected
    assert provenance["benchmark_outputs_modified"] is False
    assert provenance["scenario_input_hash"] == first.input_hash
