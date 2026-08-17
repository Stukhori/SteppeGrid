import pytest

from steppegrid.app.services import PlanningService
from steppegrid.benchmarks.phase9 import benchmark_pv, load_phase9_loads, load_phase9_weather, run_phase9
from steppegrid.equipment.catalog import BATTERIES
from steppegrid.optimization.core import RenewablePortfolio, dispatch, scale_trace


def test_generalized_pv_coordinates_preserve_frozen_rodina_defaults():
    weather = load_phase9_weather()
    default_metadata, default_profiles = benchmark_pv(weather)
    explicit_metadata, explicit_profiles = benchmark_pv(
        weather, latitude=51.302445, longitude=70.541645,
        tilt_deg=51.302445, azimuth_deg=180.0, timezone_offset_hours=5,
    )
    assert default_metadata == explicit_metadata
    assert default_profiles.keys() == explicit_profiles.keys()
    for key in default_profiles:
        assert default_profiles[key] == pytest.approx(explicit_profiles[key], abs=0)


def test_generalized_dispatch_evaluates_frozen_rodina_selected_design_identically():
    weather = load_phase9_weather()
    phase9 = run_phase9(weather=weather, write_outputs=False)
    loads, _ = load_phase9_loads()
    selected = PlanningService().design(0.95)
    portfolio = RenewablePortfolio(
        selected["wind_key"], selected["wind_count"],
        selected["pv_key"], selected["pv_count"],
    )
    trace = scale_trace(portfolio, phase9.wind_profiles_kwh, phase9.pv_profiles_kwh)
    metrics = dispatch(
        loads[selected["binding_load_profile"]], trace,
        BATTERIES[selected["battery_key"]], selected["battery_count"],
    )
    assert metrics["served_fraction"] == pytest.approx(selected["worst_served_fraction"], abs=1e-12)
    assert metrics["unmet_energy_kwh"] == pytest.approx(selected["unmet_energy_kwh"], abs=1e-6)
    assert metrics["loss_of_load_hours"] == selected["loss_of_load_hours"]
