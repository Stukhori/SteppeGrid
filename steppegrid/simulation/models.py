"""Typed domain models and validation for hourly simulations."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Location(DomainModel):
    name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    country: str = "Kazakhstan"


class DataProvenance(DomainModel):
    source: str
    retrieved_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_time: datetime
    end_time: datetime
    original_units: dict[str, str]
    normalized_units: dict[str, str]
    processing_notes: list[str] = Field(default_factory=list)


def _validate_hourly(timestamps: list[datetime], values: list[object], name: str) -> None:
    if not timestamps:
        raise ValueError("timestamps must not be empty")
    if len(timestamps) != len(values):
        raise ValueError(f"timestamps and {name} must have equal lengths")
    for previous, current in zip(timestamps, timestamps[1:], strict=False):
        if current - previous != timedelta(hours=1):
            raise ValueError("timestamps must be strictly consecutive hourly intervals")


class LoadProfile(DomainModel):
    timestamps: list[datetime]
    demand_kwh: list[float]

    @model_validator(mode="after")
    def validate_series(self) -> LoadProfile:
        _validate_hourly(self.timestamps, self.demand_kwh, "demand_kwh")
        if any(value < 0 for value in self.demand_kwh):
            raise ValueError("demand_kwh values must be non-negative")
        return self


class WeatherSeries(DomainModel):
    timestamps: list[datetime]
    wind_speed_m_s: list[float]
    solar_irradiance_w_m2: list[float]
    temperature_c: list[float] | None = None

    @model_validator(mode="after")
    def validate_series(self) -> WeatherSeries:
        _validate_hourly(self.timestamps, self.wind_speed_m_s, "wind_speed_m_s")
        if len(self.solar_irradiance_w_m2) != len(self.timestamps):
            raise ValueError("solar irradiance and timestamps must have equal lengths")
        if self.temperature_c is not None and len(self.temperature_c) != len(self.timestamps):
            raise ValueError("temperature and timestamps must have equal lengths")
        if any(value < 0 for value in self.wind_speed_m_s):
            raise ValueError("wind speeds must be non-negative")
        if any(value < 0 for value in self.solar_irradiance_w_m2):
            raise ValueError("solar irradiance must be non-negative")
        return self


class WeatherDataset(DomainModel):
    series: WeatherSeries
    provenance: DataProvenance

    @model_validator(mode="after")
    def validate_provenance_period(self) -> WeatherDataset:
        timestamps = self.series.timestamps
        if self.provenance.start_time != timestamps[0]:
            raise ValueError("provenance start_time must match the first weather timestamp")
        if self.provenance.end_time != timestamps[-1] + timedelta(hours=1):
            raise ValueError("provenance end_time must be one hour after the final timestamp")
        return self


class GridAvailability(DomainModel):
    timestamps: list[datetime]
    available: list[bool]

    @model_validator(mode="after")
    def validate_series(self) -> GridAvailability:
        _validate_hourly(self.timestamps, self.available, "available")
        return self


class OutageInterval(DomainModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_bounds(self) -> OutageInterval:
        if self.end <= self.start:
            raise ValueError("outage end must be later than outage start")
        return self


class PowerCurvePoint(DomainModel):
    wind_speed_m_s: float = Field(ge=0)
    electrical_output_kw: float = Field(ge=0)


class WindTurbineConfig(DomainModel):
    name: str
    power_curve: list[PowerCurvePoint]
    turbine_count: int = Field(default=1, ge=0)
    manufacturer: str | None = None
    rated_power_kw: float | None = Field(default=None, gt=0)
    source: str | None = None
    measurement_or_datasheet: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_curve(self) -> WindTurbineConfig:
        if not self.power_curve:
            raise ValueError("power_curve must contain at least one point")
        speeds = [point.wind_speed_m_s for point in self.power_curve]
        if speeds != sorted(speeds) or len(speeds) != len(set(speeds)):
            raise ValueError("power-curve wind speeds must be unique and strictly increasing")
        return self


class SolarArrayConfig(DomainModel):
    dc_capacity_kw: float = Field(ge=0)
    performance_ratio: float = Field(default=0.8, gt=0, le=1)


class BatteryConfig(DomainModel):
    capacity_kwh: float = Field(ge=0)
    initial_soc_kwh: float = Field(ge=0)
    minimum_soc_kwh: float = Field(default=0, ge=0)
    maximum_charge_kw: float = Field(ge=0)
    maximum_discharge_kw: float = Field(ge=0)
    charging_efficiency: float = Field(gt=0, le=1)
    discharging_efficiency: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_soc_bounds(self) -> BatteryConfig:
        if self.minimum_soc_kwh > self.capacity_kwh:
            raise ValueError("minimum_soc_kwh cannot exceed capacity_kwh")
        if not self.minimum_soc_kwh <= self.initial_soc_kwh <= self.capacity_kwh:
            raise ValueError("initial_soc_kwh must lie between minimum SOC and capacity")
        return self


class SimulationInput(DomainModel):
    load: LoadProfile
    weather: WeatherSeries
    grid: GridAvailability
    wind_turbine: WindTurbineConfig
    solar_array: SolarArrayConfig
    battery: BatteryConfig

    @model_validator(mode="after")
    def validate_alignment(self) -> SimulationInput:
        if not (self.load.timestamps == self.weather.timestamps == self.grid.timestamps):
            raise ValueError("load, weather, and grid timestamps must match exactly")
        return self


class HourlyResult(DomainModel):
    timestamp: datetime
    demand_kwh: float
    solar_generation_kwh: float
    wind_generation_kwh: float
    renewable_generation_kwh: float
    renewable_direct_to_load_kwh: float
    battery_charge_kwh: float
    battery_discharge_kwh: float
    battery_soc_start_kwh: float
    battery_soc_end_kwh: float
    battery_loss_kwh: float
    grid_available: bool
    grid_import_kwh: float
    curtailed_energy_kwh: float
    unserved_energy_kwh: float


class AggregateMetrics(DomainModel):
    total_demand_kwh: float
    solar_generation_kwh: float
    wind_generation_kwh: float
    renewable_generation_kwh: float
    grid_import_kwh: float
    battery_charge_kwh: float
    battery_discharge_kwh: float
    battery_loss_kwh: float
    curtailed_energy_kwh: float
    unserved_energy_kwh: float
    renewable_fraction: float
    hours_with_unserved_load: int
    outage_demand_kwh: float
    outage_served_energy_kwh: float
    outage_unserved_energy_kwh: float


class SimulationResult(DomainModel):
    hourly: list[HourlyResult]
    metrics: AggregateMetrics
