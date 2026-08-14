from datetime import timedelta

import pytest

from steppegrid.simulation.grid import availability_with_outages
from steppegrid.simulation.models import OutageInterval
from steppegrid.simulation.simulator import simulate


def test_outage_metrics_cover_only_unavailable_intervals(scenario_factory):
    inputs = scenario_factory(hours=6, grid_available=True)
    timestamps = inputs.grid.timestamps
    grid = availability_with_outages(
        timestamps,
        [OutageInterval(start=timestamps[1], end=timestamps[4])],
    )
    inputs = inputs.model_copy(
        update={
            "grid": grid
        }
    )
    result = simulate(inputs)
    assert result.metrics.outage_demand_kwh == pytest.approx(3)
    assert result.metrics.outage_served_energy_kwh == pytest.approx(0)
    assert result.metrics.outage_unserved_energy_kwh == pytest.approx(3)
    assert result.hourly[1].timestamp + timedelta(hours=2) == result.hourly[3].timestamp


def test_outage_interval_is_start_inclusive_and_end_exclusive(scenario_factory):
    timestamps = scenario_factory(hours=4).grid.timestamps
    grid = availability_with_outages(
        timestamps,
        [OutageInterval(start=timestamps[1], end=timestamps[3])],
    )
    assert grid.available == [True, False, False, True]
