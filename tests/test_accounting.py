from datetime import datetime, timedelta, timezone

import pytest

from steppegrid.simulation.models import (
    BatteryConfig, GridAvailability, LoadProfile, PowerCurvePoint,
    SimulationInput, SolarArrayConfig, WeatherSeries, WindTurbineConfig,
)
from steppegrid.simulation.simulator import simulate


def test_mixed_dispatch_conserves_energy_and_exercises_all_flows():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = [start + timedelta(hours=index) for index in range(5)]
    inputs = SimulationInput(
        load=LoadProfile(timestamps=timestamps, demand_kwh=[1, 1, 1, 1, 1]),
        weather=WeatherSeries(
            timestamps=timestamps,
            wind_speed_m_s=[0] * 5,
            solar_irradiance_w_m2=[1000, 0, 0, 0, 1000],
            temperature_c=[0] * 5,
        ),
        grid=GridAvailability(timestamps=timestamps, available=[True, True, True, False, True]),
        wind_turbine=WindTurbineConfig(
            name="zero", power_curve=[PowerCurvePoint(wind_speed_m_s=0, electrical_output_kw=0)]
        ),
        solar_array=SolarArrayConfig(dc_capacity_kw=3, performance_ratio=1),
        battery=BatteryConfig(
            capacity_kwh=1, initial_soc_kwh=0, maximum_charge_kw=1,
            maximum_discharge_kw=1, charging_efficiency=0.8,
            discharging_efficiency=0.8,
        ),
    )
    result = simulate(inputs)
    assert result.metrics.battery_charge_kwh > 0
    assert result.metrics.battery_discharge_kwh > 0
    assert result.metrics.battery_loss_kwh > 0
    assert result.metrics.grid_import_kwh > 0
    assert result.metrics.curtailed_energy_kwh > 0
    assert result.metrics.unserved_energy_kwh > 0
    for row in result.hourly:
        supplied = row.renewable_generation_kwh + row.grid_import_kwh + row.battery_soc_start_kwh
        accounted = (
            row.demand_kwh - row.unserved_energy_kwh + row.curtailed_energy_kwh
            + row.battery_soc_end_kwh + row.battery_loss_kwh
        )
        assert supplied == pytest.approx(accounted, abs=1e-9)


def test_documented_metric_definitions(scenario_factory):
    inputs = scenario_factory(
        hours=2, battery_capacity_kwh=1, initial_soc_kwh=1,
        maximum_discharge_kw=1, discharging_efficiency=0.5,
    )
    result = simulate(inputs)
    assert result.metrics.battery_discharge_kwh == pytest.approx(0.5)
    assert result.metrics.battery_loss_kwh == pytest.approx(0.5)
    # Phase 8: discharge from gifted initial inventory is not renewable generation.
    assert result.metrics.renewable_fraction == pytest.approx(0.0)
    assert result.metrics.renewable_generation_kwh == 0
    assert result.metrics.battery_discharge_from_initial_inventory_kwh == pytest.approx(0.5)
    assert result.metrics.battery_discharge_from_simulation_charge_kwh == 0
    assert result.metrics.initial_stored_energy_kwh == 1
    assert result.metrics.ending_stored_energy_kwh == 0
    assert result.metrics.outage_served_energy_kwh == pytest.approx(0.5)
    assert result.metrics.outage_unserved_energy_kwh == pytest.approx(1.5)
