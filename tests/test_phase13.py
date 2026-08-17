import math
from pathlib import Path

import pytest

from steppegrid.app.data import AppDataError, FrozenDataRepository
from steppegrid.app.formatting import RECONSTRUCTION_NOTICE, SCENARIO_NOTICE, energy, percent
from steppegrid.app.services import PlanningService
from steppegrid.app.state import PAGES, SHAMSHI_STATUS


def test_app_exposes_all_required_pages():
    assert len(PAGES) == 8
    assert PAGES[0] == "Overview"
    assert PAGES[-1] == "Methodology & Provenance"


def test_frozen_designs_are_exact_phase12_selections():
    service = PlanningService()
    design95 = service.design(0.95)
    design99 = service.design(0.99)
    assert (design95["wind_count"], design95["pv_count"], design95["battery_count"]) == (131, 83, 4)
    assert (design99["wind_count"], design99["pv_count"], design99["battery_count"]) == (319, 202, 6)
    assert design95["worst_served_fraction"] == pytest.approx(0.9503758670754928)
    assert design99["worst_served_fraction"] == pytest.approx(0.9900266228605829)
    with pytest.raises(ValueError, match="frozen 95% or 99%"):
        service.design(0.97)


def test_app_terminology_preserves_research_limits():
    assert "not measured hourly demand" in RECONSTRUCTION_NOTICE
    assert "not uptime" in RECONSTRUCTION_NOTICE
    assert "not confidence intervals" in SCENARIO_NOTICE
    assert "not global re-optimization" in SCENARIO_NOTICE
    assert "No default electricity demand is assumed" in SHAMSHI_STATUS
    assert "not field optima" in SHAMSHI_STATUS


def test_adaptation_metadata_is_unambiguous():
    metadata = PlanningService().adaptation_metadata()
    assert metadata["adaptation_method"] == "saved_phase10_candidate_reselection"
    assert metadata["full_reoptimization_performed"] is False
    assert metadata["single_profile_comparison_provenance"] == {
        "label": "saved Phase 10 single-profile candidate-set comparison",
        "source": "outputs/benchmarks/rodina/phase10/scale_aware_energy_optima.json",
        "single_profile_modes": ["flat_within_month", "residential_like", "community_facility_like"],
        "robust_mode": "robust_all_profiles",
        "comparison_metric": "net_present_cost_usd",
    }


def test_combined_sensitivity_direction_and_headroom_are_visible():
    service = PlanningService()
    for target in (0.95, 0.99):
        rows = {row["scenario"]: row for row in service.sensitivity_rows(target)}
        assert rows["resource_stress"]["wind_shear_alpha"] > rows["nominal"]["wind_shear_alpha"]
        assert rows["resource_favorable"]["wind_shear_alpha"] < rows["nominal"]["wind_shear_alpha"]
        assert rows["resource_stress"]["served_fraction"] < rows["nominal"]["served_fraction"]
    margins = {row["target"]: row for row in service.margin_rows()}
    assert 100 * (margins[0.95]["maximum_demand_multiplier_for_target"] - 1) == pytest.approx(0.3221584)
    assert 100 * (margins[0.99]["maximum_demand_multiplier_for_target"] - 1) == pytest.approx(0.1477049)


def test_fixed_sensitivity_includes_physical_and_economic_one_factor_cases():
    rows = {row["scenario"]: row for row in PlanningService().fixed_sensitivity_rows(0.95)}
    expected = {"demand_low", "demand_high", "wind_shear_low", "wind_shear_high", "pv_low", "pv_high", "wind_capex_low", "wind_capex_high", "pv_capex_low", "pv_capex_high", "battery_capex_low", "battery_capex_high", "resource_stress", "resource_favorable"}
    assert expected <= rows.keys()
    assert rows["wind_capex_low"]["served_fraction"] == pytest.approx(rows["nominal"]["served_fraction"])
    assert rows["wind_capex_low"]["net_present_cost_usd"] < rows["nominal"]["net_present_cost_usd"]


def test_hourly_replay_matches_frozen_design_aggregate():
    service = PlanningService()
    frame = service.dispatch_frame(0.95, "residential_like")
    design = service.design(0.95)
    assert len(frame) == 8760
    assert frame["timestamp"].is_monotonic_increasing
    assert math.fsum(frame["unmet_energy_kwh"]) == pytest.approx(design["unmet_energy_kwh"], abs=1e-6)
    columns = ["load_kwh", "wind_generation_kwh", "pv_generation_kwh", "battery_soc_kwh", "unmet_energy_kwh", "curtailment_kwh"]
    assert (frame[columns] >= 0).all().all()


def test_missing_outputs_fail_with_reproduction_guidance(tmp_path: Path):
    with pytest.raises(AppDataError, match="run_phase12.py --mode verify"):
        FrozenDataRepository(tmp_path).validate()


def test_formatters_keep_units_explicit():
    assert energy(8_020_000) == "8.02 GWh"
    assert percent(0.950375867, 3) == "95.038%"
