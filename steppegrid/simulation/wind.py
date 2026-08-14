"""Generic empirical wind-turbine power-curve calculation."""

from bisect import bisect_right

from steppegrid.simulation.models import WindTurbineConfig


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
