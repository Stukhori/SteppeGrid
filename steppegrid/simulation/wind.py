"""Generic empirical wind-turbine power-curve calculation."""

from bisect import bisect_right

from steppegrid.simulation.models import WindTurbineConfig
from steppegrid.equipment.models import CutOutBehavior, HighWindCurvePolicy, WindTurbineSpec

DEFAULT_WIND_SHEAR_EXPONENT = 1 / 7


def wind_speed_at_hub_height(wind_speed_reference_m_s: float, hub_height_m: float,
                             reference_height_m: float = 100.0,
                             shear_exponent: float = DEFAULT_WIND_SHEAR_EXPONENT) -> float:
    """Power-law height conversion; alpha=1/7 is a generic neutral/open-terrain assumption, not site-measured."""
    if wind_speed_reference_m_s < 0 or hub_height_m <= 0 or reference_height_m <= 0 or shear_exponent < 0:
        raise ValueError("wind speed and shear exponent must be non-negative and heights positive")
    return wind_speed_reference_m_s * (hub_height_m / reference_height_m) ** shear_exponent


def commercial_turbine_output_kw(wind_speed_100m_m_s: float, turbine: WindTurbineSpec,
                                 hub_height_m: float, shear_exponent: float = DEFAULT_WIND_SHEAR_EXPONENT) -> float:
    """Evaluate the verified curve at power-law-adjusted hub-height wind speed."""
    speed = wind_speed_at_hub_height(wind_speed_100m_m_s, hub_height_m, 100.0, shear_exponent)
    if speed < turbine.cut_in_wind_speed_m_s:
        return 0.0
    if (turbine.cut_out_behavior == CutOutBehavior.SPEED_THRESHOLD
            and speed > turbine.cut_out_wind_speed_m_s):
        return 0.0
    points = turbine.power_curve
    if speed <= points[0].wind_speed_m_s:
        return points[0].electrical_output_kw
    if speed == points[-1].wind_speed_m_s:
        return points[-1].electrical_output_kw
    if speed > points[-1].wind_speed_m_s:
        if turbine.high_wind_curve_policy != HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE:
            raise ValueError(f"unsupported high-wind policy: {turbine.high_wind_curve_policy}")
        # Explicit model assumption: do not extrapolate or call this held value certified.
        return min(points[-1].electrical_output_kw, turbine.maximum_curve_output_kw)
    speeds = [point.wind_speed_m_s for point in points]
    upper_index = bisect_right(speeds, speed)
    lower, upper = points[upper_index - 1], points[upper_index]
    fraction = (speed - lower.wind_speed_m_s) / (upper.wind_speed_m_s - lower.wind_speed_m_s)
    return min(lower.electrical_output_kw + fraction * (upper.electrical_output_kw - lower.electrical_output_kw), turbine.maximum_curve_output_kw)


def electrical_output_kw(wind_speed_m_s: float, turbine: WindTurbineConfig) -> float:
    """Linearly interpolate output; use endpoint outputs outside the supplied range."""
    points = turbine.power_curve
    if wind_speed_m_s <= points[0].wind_speed_m_s:
        return points[0].electrical_output_kw * turbine.turbine_count
    if wind_speed_m_s >= points[-1].wind_speed_m_s:
        return points[-1].electrical_output_kw * turbine.turbine_count

    speeds = [point.wind_speed_m_s for point in points]
    upper_index = bisect_right(speeds, wind_speed_m_s)
    lower = points[upper_index - 1]
    upper = points[upper_index]
    fraction = (wind_speed_m_s - lower.wind_speed_m_s) / (
        upper.wind_speed_m_s - lower.wind_speed_m_s
    )
    output_kw = lower.electrical_output_kw + fraction * (
        upper.electrical_output_kw - lower.electrical_output_kw
    )
    return output_kw * turbine.turbine_count
