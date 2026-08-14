from datetime import datetime, timedelta, timezone

import pytest

from steppegrid.simulation.models import (
    BatteryConfig,
    GridAvailability,
    LoadProfile,
    PowerCurvePoint,
    SimulationInput,
    SolarArrayConfig,
    WeatherSeries,
    WindTurbineConfig,
)


@pytest.fixture
def scenario_factory():
    def make(
        *,
        hours: int,
        demand_kwh: float = 1.0,
        solar_irradiance_w_m2: float = 0.0,
        solar_capacity_kw: float = 0.0,
        grid_available: bool = False,
        battery_capacity_kwh: float = 0.0,
        initial_soc_kwh: float = 0.0,
        maximum_charge_kw: float = 0.0,
        maximum_discharge_kw: float = 0.0,
        charging_efficiency: float = 1.0,
        discharging_efficiency: float = 1.0,
    ) -> SimulationInput:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        timestamps = [start + timedelta(hours=index) for index in range(hours)]
        return SimulationInput(
            load=LoadProfile(timestamps=timestamps, demand_kwh=[demand_kwh] * hours),
            weather=WeatherSeries(
                timestamps=timestamps,
                wind_speed_m_s=[0.0] * hours,
                solar_irradiance_w_m2=[solar_irradiance_w_m2] * hours,
            ),
            grid=GridAvailability(timestamps=timestamps, available=[grid_available] * hours),
            wind_turbine=WindTurbineConfig(
                name="zero-output test curve",
                power_curve=[PowerCurvePoint(wind_speed_m_s=0, electrical_output_kw=0)],
            ),
            solar_array=SolarArrayConfig(
                dc_capacity_kw=solar_capacity_kw,
                performance_ratio=1.0,
            ),
            battery=BatteryConfig(
                capacity_kwh=battery_capacity_kwh,
                initial_soc_kwh=initial_soc_kwh,
                maximum_charge_kw=maximum_charge_kw,
                maximum_discharge_kw=maximum_discharge_kw,
                charging_efficiency=charging_efficiency,
                discharging_efficiency=discharging_efficiency,
            ),
        )

    return make
