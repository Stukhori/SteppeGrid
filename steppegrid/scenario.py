"""Serializable, reproducible simulation scenario definitions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from steppegrid.data.turbine_curves import load_turbine_curve_csv
from steppegrid.load.csv_provider import CSVLoadProvider
from steppegrid.load.synthetic import SyntheticLoadProvider
from steppegrid.simulation.grid import availability_with_outages
from steppegrid.simulation.models import (
    BatteryConfig, DataProvenance, DomainModel, LoadDataQuality, LoadDataset,
    LoadProvenance, LoadSourceType, Location, OutageInterval, SimulationInput,
    SolarArrayConfig,
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


class LoadSourceConfig(DomainModel):
    provider: Literal["synthetic", "csv"]
    path: str | None = None
    profile: Literal[
        "constant", "residential_like", "community_facility_like"
    ] = "constant"
    source: str | None = None
    source_type: LoadSourceType | None = None
    data_quality: LoadDataQuality | None = None
    retrieved_or_created_at: datetime | None = None
    processing_steps: list[str] = Field(default_factory=list)
    scale_factor: float | None = Field(default=None, gt=0)
    target_annual_kwh: float | None = Field(default=None, gt=0)
    critical_fraction: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_source(self) -> LoadSourceConfig:
        if self.provider == "csv" and not self.path:
            raise ValueError("CSV load provider requires path")
        if self.scale_factor is not None and self.target_annual_kwh is not None:
            raise ValueError("choose either target_annual_kwh or scale_factor, not both")
        if self.provider == "synthetic" and self.data_quality not in {
            None,
            LoadDataQuality.SYNTHETIC,
        }:
            raise ValueError("synthetic load must use SYNTHETIC data quality")
        if self.provider == "synthetic" and self.source_type not in {
            None,
            LoadSourceType.SYNTHETIC_MODEL,
        }:
            raise ValueError("synthetic load must use SYNTHETIC_MODEL source type")
        if self.provider == "synthetic" and self.path is not None:
            raise ValueError("synthetic load does not accept a path")
        return self


class SimulationSettings(DomainModel):
    timestep_hours: float = 1.0

    @model_validator(mode="after")
    def require_hourly(self) -> SimulationSettings:
        if self.timestep_hours != 1.0:
            raise ValueError("only a 1-hour timestep is currently supported")
        return self


class DispatchSettings(DomainModel):
    outage_load_policy: Literal[
        "proportional_or_existing", "critical_first"
    ] = "proportional_or_existing"


class SimulationScenario(DomainModel):
    location: Location
    start_time: datetime
    end_time: datetime
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    dispatch: DispatchSettings = Field(default_factory=DispatchSettings)
    weather: WeatherSourceConfig
    load: LoadSourceConfig | None = None
    load_profile_kwh: list[float] | None = None
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
        if (self.load is None) == (self.load_profile_kwh is None):
            raise ValueError("provide exactly one of load or legacy load_profile_kwh")
        if self.load_profile_kwh is not None:
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
    load_provenance: LoadProvenance


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
    if scenario.load is None:
        load = LoadDataset(
            timestamps=timestamps,
            total_load_kwh=scenario.load_profile_kwh or [],
            provenance=LoadProvenance(
                source="Legacy inline scenario load_profile_kwh",
                source_type=LoadSourceType.INLINE_SCENARIO,
                data_quality=LoadDataQuality.UNSPECIFIED,
                start_time=scenario.start_time,
                end_time=scenario.end_time,
                location=scenario.location,
                processing_steps=["Read hourly values directly from the scenario file."],
                notes="No independent source or quality classification was supplied.",
            ),
        )
    elif scenario.load.provider == "synthetic":
        load = SyntheticLoadProvider(
            profile=scenario.load.profile,
            scale_factor=scenario.load.scale_factor,
            target_annual_kwh=scenario.load.target_annual_kwh,
            critical_fraction=scenario.load.critical_fraction,
            location=scenario.location,
            created_at=scenario.load.retrieved_or_created_at,
            source=scenario.load.source,
            processing_steps=scenario.load.processing_steps,
        ).get_hourly_load(scenario.start_time, scenario.end_time)
    else:
        load = CSVLoadProvider(
            base / str(scenario.load.path),
            source=scenario.load.source,
            source_type=(
                scenario.load.source_type or LoadSourceType.USER_SUPPLIED_CSV
            ),
            data_quality=scenario.load.data_quality or LoadDataQuality.UNSPECIFIED,
            retrieved_at=scenario.load.retrieved_or_created_at,
            location=scenario.location,
            processing_steps=scenario.load.processing_steps,
            scale_factor=scenario.load.scale_factor,
            target_annual_kwh=scenario.load.target_annual_kwh,
            critical_fraction=scenario.load.critical_fraction,
        ).get_hourly_load(scenario.start_time, scenario.end_time)
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
        load=load,
        weather=weather.series, grid=grid, wind_turbine=wind,
        solar_array=scenario.solar, battery=scenario.battery,
        outage_load_policy=scenario.dispatch.outage_load_policy,
    )
    return ResolvedScenario(
        scenario=scenario, simulation_input=simulation_input,
        weather_provenance=weather.provenance,
        load_provenance=load.provenance,
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
