from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from steppegrid.simulation.models import LoadProfile, PowerCurvePoint, WindTurbineConfig
from steppegrid.simulation.wind import electrical_output_kw


def test_wind_curve_interpolates_linearly():
    turbine = WindTurbineConfig(
        name="test",
        power_curve=[
            PowerCurvePoint(wind_speed_m_s=3, electrical_output_kw=0),
            PowerCurvePoint(wind_speed_m_s=7, electrical_output_kw=2),
        ],
        turbine_count=2,
    )
    assert electrical_output_kw(5, turbine) == pytest.approx(2)


def test_wind_curve_uses_supplied_endpoint_behavior():
    turbine = WindTurbineConfig(
        name="test",
        power_curve=[
            PowerCurvePoint(wind_speed_m_s=3, electrical_output_kw=0),
            PowerCurvePoint(wind_speed_m_s=25, electrical_output_kw=0),
        ],
    )
    assert electrical_output_kw(30, turbine) == 0


def test_missing_hour_is_rejected():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="consecutive hourly"):
        LoadProfile(
            timestamps=[start, start + timedelta(hours=2)],
            demand_kwh=[1, 1],
        )


def test_unsorted_power_curve_is_rejected():
    with pytest.raises(ValidationError, match="strictly increasing"):
        WindTurbineConfig(
            name="invalid",
            power_curve=[
                PowerCurvePoint(wind_speed_m_s=5, electrical_output_kw=1),
                PowerCurvePoint(wind_speed_m_s=3, electrical_output_kw=0),
            ],
        )
