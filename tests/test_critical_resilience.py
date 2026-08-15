import pytest

from steppegrid.simulation.models import LoadProfile
from steppegrid.simulation.simulator import simulate


def _critical_outage(scenario_factory, available_energy_kwh: float):
    inputs = scenario_factory(
        hours=1,
        demand_kwh=2,
        solar_irradiance_w_m2=1000,
        solar_capacity_kw=available_energy_kwh,
        grid_available=False,
    )
    inputs = inputs.model_copy(
        update={
            "load": LoadProfile(
                timestamps=inputs.load.timestamps,
                demand_kwh=[2],
                critical_demand_kwh=[1],
            ),
            "outage_load_policy": "critical_first",
        }
    )
    return simulate(inputs)


@pytest.mark.parametrize(
    ("available", "served_fraction", "critical_unserved"),
    [(1.0, 1.0, 0.0), (0.4, 0.4, 0.6), (0.0, 0.0, 1.0)],
)
def test_critical_first_outage_service(available, served_fraction, critical_unserved, scenario_factory):
    result = _critical_outage(scenario_factory, available)
    assert result.metrics.critical_load_served_fraction == pytest.approx(served_fraction)
    assert result.metrics.outage_critical_unserved_kwh == pytest.approx(critical_unserved)
    assert result.metrics.outage_total_demand_kwh == pytest.approx(2)


def test_existing_policy_allocates_service_proportionally(scenario_factory):
    inputs = scenario_factory(
        hours=1,
        demand_kwh=2,
        solar_irradiance_w_m2=1000,
        solar_capacity_kw=1,
        grid_available=False,
    )
    inputs = inputs.model_copy(
        update={
            "load": LoadProfile(
                timestamps=inputs.load.timestamps,
                demand_kwh=[2],
                critical_demand_kwh=[1],
            )
        }
    )
    result = simulate(inputs)
    assert result.metrics.outage_total_served_kwh == pytest.approx(1)
    assert result.metrics.outage_critical_served_kwh == pytest.approx(0.5)


def test_zero_critical_demand_has_explicit_zero_fraction(scenario_factory):
    result = simulate(scenario_factory(hours=1))
    assert result.metrics.outage_critical_demand_kwh == 0
    assert result.metrics.critical_load_served_fraction == 0
