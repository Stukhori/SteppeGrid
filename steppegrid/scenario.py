"""Serializable, reproducible simulation scenario definitions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from steppegrid.data.turbine_curves import load_turbine_curve_csv
from steppegrid.simulation.grid import availability_with_outages
from steppegrid.simulation.models import (
    BatteryConfig, DataProvenance, DomainModel, LoadProfile, Location,
    OutageInterval, SimulationInput, SolarArrayConfig,
)
from steppegrid.weather.csv_provider import CSVWeatherProvider
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider
from steppegrid.weather.synthetic import SyntheticWeatherProvider


class WeatherSourceConfig(DomainModel):
    provider: Literal["synthetic", "csv", "open-meteo"]
    path: str | None = None
    model: Literal["era5"] = "era5"
    cache_directory: str | None = None
    source: str | None = None
    retrieved_at: datetime | None = None
    maximum_irradiance_w_m2: float = Field(default=2000.0, gt=0)
    processing_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_csv_path(self) -> WeatherSourceConfig:
        if self.provider == "csv" and not self.path:
            raise ValueError("CSV weather provider requires path")
        return self


class TurbineSourceConfig(DomainModel):
    curve_csv: str
    name: str
    count: int = Field(default=1, ge=0)
    manufacturer: str | None = None
    rated_power_kw: float | None = Field(default=None, gt=0)
    source: str | None = None
    measurement_or_datasheet: str | None = None
    notes: str | None = None


class SimulationSettings(DomainModel):
    timestep_hours: float = 1.0

    @model_validator(mode="after")
    def require_hourly(self) -> SimulationSettings:
        if self.timestep_hours != 1.0:
            raise ValueError("only a 1-hour timestep is currently supported")
        return self


class SimulationScenario(DomainModel):
    location: Location
    start_time: datetime
    end_time: datetime
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    weather: WeatherSourceConfig
    load_profile_kwh: list[float]
    solar: SolarArrayConfig
    wind: TurbineSourceConfig
    battery: BatteryConfig
    grid_available_by_default: bool = True
    outage_schedule: list[OutageInterval] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_period_and_load(self) -> SimulationScenario:
        duration = self.end_time - self.start_time
        hours = int(duration.total_seconds() / 3600)
        if hours <= 0 or duration != timedelta(hours=hours):
            raise ValueError("scenario period must contain positive whole hours")
        if len(self.load_profile_kwh) != hours:
            raise ValueError("load_profile_kwh must contain one value per scenario hour")
        if any(value < 0 for value in self.load_profile_kwh):
            raise ValueError("load_profile_kwh values must be non-negative")
        for outage in self.outage_schedule:
            if outage.start < self.start_time or outage.end > self.end_time:
                raise ValueError("outage intervals must lie within the scenario period")
        return self


class ResolvedScenario(DomainModel):
    scenario: SimulationScenario
    simulation_input: SimulationInput
    weather_provenance: DataProvenance


def load_scenario(path: str | Path) -> SimulationScenario:
    scenario_path = Path(path)
    if not scenario_path.is_file():
        raise ValueError(f"scenario file does not exist: {scenario_path}")
    raw = scenario_path.read_text(encoding="utf-8")
    if scenario_path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(raw)
    elif scenario_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        raise ValueError("scenario file must use .yaml, .yml, or .json")
    if not isinstance(data, dict):
        raise ValueError("scenario file must contain a mapping/object")
    return SimulationScenario.model_validate(data)


def resolve_scenario(
    scenario: SimulationScenario,
    *,
    base_directory: str | Path = ".",
    refresh_weather: bool = False,
) -> ResolvedScenario:
    base = Path(base_directory)
    if scenario.weather.provider == "synthetic":
        provider = SyntheticWeatherProvider()
    elif scenario.weather.provider == "csv":
        provider = CSVWeatherProvider(
            base / str(scenario.weather.path), source=scenario.weather.source,
            retrieved_at=scenario.weather.retrieved_at,
            maximum_irradiance_w_m2=scenario.weather.maximum_irradiance_w_m2,
            processing_notes=scenario.weather.processing_notes,
        )
    else:
        cache_root = (
            base / scenario.weather.cache_directory
            if scenario.weather.cache_directory
            else Path("data/weather/cache")
        )
        provider = OpenMeteoHistoricalWeatherProvider(
            cache_root=cache_root,
            maximum_irradiance_w_m2=scenario.weather.maximum_irradiance_w_m2,
        )
    if isinstance(provider, OpenMeteoHistoricalWeatherProvider):
        weather = provider.get_hourly_weather(
            scenario.location,
            scenario.start_time,
            scenario.end_time,
            refresh=refresh_weather,
        )
    else:
        weather = provider.get_hourly_weather(
            scenario.location, scenario.start_time, scenario.end_time
        )
    timestamps = weather.series.timestamps
    grid = availability_with_outages(timestamps, scenario.outage_schedule)
    if not scenario.grid_available_by_default:
        grid = availability_with_outages(
            timestamps, [OutageInterval(start=scenario.start_time, end=scenario.end_time)]
        )
    wind = load_turbine_curve_csv(
        base / scenario.wind.curve_csv, name=scenario.wind.name,
        turbine_count=scenario.wind.count, manufacturer=scenario.wind.manufacturer,
        rated_power_kw=scenario.wind.rated_power_kw, source=scenario.wind.source,
        measurement_or_datasheet=scenario.wind.measurement_or_datasheet,
        notes=scenario.wind.notes,
    )
    simulation_input = SimulationInput(
        load=LoadProfile(timestamps=timestamps, demand_kwh=scenario.load_profile_kwh),
        weather=weather.series, grid=grid, wind_turbine=wind,
        solar_array=scenario.solar, battery=scenario.battery,
    )
    return ResolvedScenario(
        scenario=scenario, simulation_input=simulation_input,
        weather_provenance=weather.provenance,
    )


def load_and_resolve_scenario(
    path: str | Path, *, refresh_weather: bool = False
) -> ResolvedScenario:
    scenario_path = Path(path)
    return resolve_scenario(
        load_scenario(scenario_path),
        base_directory=scenario_path.parent,
        refresh_weather=refresh_weather,
    )
