"""Synthetic data for demonstration and smoke testing only."""

from datetime import datetime, timedelta, timezone
from math import pi, sin

from steppegrid.simulation.grid import availability_with_outages
from steppegrid.simulation.models import (
    BatteryConfig,
    LoadProfile,
    OutageInterval,
    PowerCurvePoint,
    SimulationInput,
    SolarArrayConfig,
    WeatherSeries,
    WindTurbineConfig,
)


def synthetic_24_hour_scenario() -> SimulationInput:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = [start + timedelta(hours=hour) for hour in range(24)]
    irradiance = [max(0.0, 700.0 * sin(pi * (hour - 6) / 12)) for hour in range(24)]
    wind_speeds = [4.0 + (hour % 5) * 0.5 for hour in range(24)]
    return SimulationInput(
        load=LoadProfile(timestamps=timestamps, demand_kwh=[1.0] * 24),
        weather=WeatherSeries(
            timestamps=timestamps,
            wind_speed_m_s=wind_speeds,
            solar_irradiance_w_m2=irradiance,
        ),
        grid=availability_with_outages(
            timestamps,
            [OutageInterval(start=timestamps[18], end=timestamps[22])],
        ),
        wind_turbine=WindTurbineConfig(
            name="synthetic demonstration curve",
            power_curve=[
                PowerCurvePoint(wind_speed_m_s=0, electrical_output_kw=0),
                PowerCurvePoint(wind_speed_m_s=3, electrical_output_kw=0),
                PowerCurvePoint(wind_speed_m_s=6, electrical_output_kw=0.8),
                PowerCurvePoint(wind_speed_m_s=12, electrical_output_kw=2.0),
                PowerCurvePoint(wind_speed_m_s=25, electrical_output_kw=0),
            ],
        ),
        solar_array=SolarArrayConfig(dc_capacity_kw=2.0, performance_ratio=0.8),
        battery=BatteryConfig(
            capacity_kwh=4.0,
            initial_soc_kwh=1.0,
            maximum_charge_kw=2.0,
            maximum_discharge_kw=2.0,
            charging_efficiency=0.95,
            discharging_efficiency=0.95,
        ),
    )
