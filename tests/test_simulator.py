import pytest

from steppegrid.simulation.simulator import simulate


def test_no_generation_means_all_load_is_unserved(scenario_factory):
    result = simulate(scenario_factory(hours=24))
    assert result.metrics.total_demand_kwh == pytest.approx(24)
    assert result.metrics.unserved_energy_kwh == pytest.approx(24)


def test_sufficient_renewable_generation_serves_load(scenario_factory):
    inputs = scenario_factory(
        hours=24, solar_irradiance_w_m2=1000, solar_capacity_kw=1
    )
    result = simulate(inputs)
    assert result.metrics.unserved_energy_kwh == pytest.approx(0)
    assert result.metrics.renewable_fraction == pytest.approx(1)


def test_ideal_battery_supports_exactly_ten_hours(scenario_factory):
    inputs = scenario_factory(
        hours=24,
        battery_capacity_kwh=10,
        initial_soc_kwh=10,
        maximum_discharge_kw=100,
    )
    result = simulate(inputs)
    assert [row.unserved_energy_kwh for row in result.hourly[:10]] == pytest.approx([0] * 10)
    assert result.hourly[10].unserved_energy_kwh == pytest.approx(1)
    assert result.metrics.battery_discharge_kwh == pytest.approx(10)
    assert result.metrics.unserved_energy_kwh == pytest.approx(14)


def test_full_battery_curtails_surplus(scenario_factory):
    inputs = scenario_factory(
        hours=1,
        solar_irradiance_w_m2=1000,
        solar_capacity_kw=3,
        battery_capacity_kwh=10,
        initial_soc_kwh=10,
        maximum_charge_kw=10,
    )
    result = simulate(inputs)
    assert result.metrics.curtailed_energy_kwh == pytest.approx(2)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"solar_irradiance_w_m2": 1000, "solar_capacity_kw": 2},
        {
            "solar_irradiance_w_m2": 1000,
            "solar_capacity_kw": 2,
            "battery_capacity_kwh": 3,
            "maximum_charge_kw": 1,
            "maximum_discharge_kw": 1,
            "charging_efficiency": 0.9,
            "discharging_efficiency": 0.8,
        },
        {"grid_available": True},
    ],
)
def test_hourly_energy_conservation(scenario_factory, kwargs):
    result = simulate(scenario_factory(hours=24, **kwargs))
    for row in result.hourly:
        supplied = (
            row.renewable_generation_kwh
            + row.grid_import_kwh
            + row.battery_soc_start_kwh
        )
        accounted = (
            row.demand_kwh
            - row.unserved_energy_kwh
            + row.curtailed_energy_kwh
            + row.battery_soc_end_kwh
            + row.battery_loss_kwh
        )
        assert supplied == pytest.approx(accounted, abs=1e-9)
