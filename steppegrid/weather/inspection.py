"""Descriptive statistics for normalized hourly weather datasets."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, median

from steppegrid.simulation.models import WeatherDataset


@dataclass(frozen=True)
class WeatherSummary:
    records: int
    mean_wind_speed_m_s: float
    median_wind_speed_m_s: float
    percentile_95_wind_speed_m_s: float
    maximum_wind_speed_m_s: float
    mean_solar_irradiance_w_m2: float
    horizontal_irradiation_kwh_m2: float
    mean_temperature_c: float
    minimum_temperature_c: float
    maximum_temperature_c: float
    missing_records: int


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight


def summarize_weather(dataset: WeatherDataset) -> WeatherSummary:
    wind = dataset.series.wind_speed_m_s
    solar = dataset.series.solar_irradiance_w_m2
    temperature = dataset.series.temperature_c
    if temperature is None:
        raise ValueError("weather inspection requires temperature_c")
    return WeatherSummary(
        records=len(dataset.series.timestamps),
        mean_wind_speed_m_s=fmean(wind),
        median_wind_speed_m_s=median(wind),
        percentile_95_wind_speed_m_s=_percentile(wind, 0.95),
        maximum_wind_speed_m_s=max(wind),
        mean_solar_irradiance_w_m2=fmean(solar),
        # Hourly mean irradiance multiplied by one hour gives Wh/m2 per record.
        horizontal_irradiation_kwh_m2=sum(solar) / 1000.0,
        mean_temperature_c=fmean(temperature),
        minimum_temperature_c=min(temperature),
        maximum_temperature_c=max(temperature),
        missing_records=0,
    )
