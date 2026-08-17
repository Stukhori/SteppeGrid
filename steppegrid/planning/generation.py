"""Site-aware weather loading and Phase 9 generation-stack reuse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path

from steppegrid.benchmarks.phase9 import benchmark_pv, benchmark_wind
from steppegrid.benchmarks.reconstruction import parse_fixed_utc_offset
from steppegrid.benchmarks.wind_shear import estimate_two_height_shear
from steppegrid.planning.models import PlanningDemand, PlanningSite
from steppegrid.simulation.models import Location, WeatherDataset
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider


@dataclass(frozen=True)
class PlanningGeneration:
    weather: WeatherDataset
    wind_profiles_kwh: dict[str, list[float]]
    pv_profiles_kwh: dict[str, list[float]]
    wind_metadata: dict[str, dict]
    pv_metadata: dict[str, dict]
    shear_exponent: float
    shear_terminology: str


def weather_cache_status(
    site: PlanningSite,
    demand: PlanningDemand,
    *,
    cache_root: str | Path = "data/weather/cache",
) -> dict[str, object]:
    provider = OpenMeteoHistoricalWeatherProvider(cache_root=cache_root)
    start = demand.timestamps[0].astimezone(timezone.utc)
    end = demand.timestamps[-1].astimezone(timezone.utc) + (demand.timestamps[-1] - demand.timestamps[-2])
    paths = provider.cache_paths(
        Location(name=site.name, latitude=site.latitude, longitude=site.longitude, country=site.country),
        start,
        end,
    )
    complete = paths.raw.is_file() and paths.normalized.is_file() and paths.metadata.is_file()
    return {
        "cache_key": paths.directory.name,
        "cache_available": complete,
        "period_start_utc": start.isoformat(),
        "period_end_utc": end.isoformat(),
        "provider": "Open-Meteo Historical Weather API",
        "model": "ERA5",
    }


def prepare_generation(
    site: PlanningSite,
    demand: PlanningDemand,
    *,
    cache_root: str | Path = "data/weather/cache",
) -> PlanningGeneration:
    """Load/fetch weather once for an explicit run and build catalog unit traces."""
    start = demand.timestamps[0].astimezone(timezone.utc)
    end = demand.timestamps[-1].astimezone(timezone.utc) + (demand.timestamps[-1] - demand.timestamps[-2])
    location = Location(
        name=site.name, latitude=site.latitude, longitude=site.longitude, country=site.country
    )
    weather = OpenMeteoHistoricalWeatherProvider(cache_root=cache_root).get_hourly_weather(
        location, start, end
    )
    if len(weather.series.timestamps) != len(demand.timestamps):
        raise ValueError("weather and demand periods have different hourly record counts")
    if weather.series.wind_speed_100m_m_s is None:
        raise ValueError("planning weather requires ERA5 wind_speed_100m")
    shear = estimate_two_height_shear(
        weather.series.wind_speed_m_s,
        weather.series.wind_speed_100m_m_s,
        timestamps=weather.series.timestamps,
    )
    wind_metadata, wind = benchmark_wind(weather, shear_exponent=shear.exponent)
    offset = parse_fixed_utc_offset(site.timezone_offset).utcoffset(None)
    offset_hours = offset.total_seconds() / 3600 if offset is not None else 0.0
    pv_metadata, pv = benchmark_pv(
        weather,
        latitude=site.latitude,
        longitude=site.longitude,
        tilt_deg=abs(site.latitude),
        azimuth_deg=180.0 if site.latitude >= 0 else 0.0,
        timezone_offset_hours=offset_hours,
    )
    return PlanningGeneration(
        weather=weather,
        wind_profiles_kwh=wind,
        pv_profiles_kwh=pv,
        wind_metadata=wind_metadata,
        pv_metadata=pv_metadata,
        shear_exponent=shear.exponent,
        shear_terminology=(
            "ERA5-derived two-height shear exponent for this planning weather period; "
            "not a site-measured shear exponent"
        ),
    )
