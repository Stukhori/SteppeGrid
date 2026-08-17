"""Strict public models for Phase 14 planning inputs and results."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from steppegrid.simulation.models import DomainModel


MINIMUM_ANNUAL_DEMAND_KWH = 10_000.0
MAXIMUM_ANNUAL_DEMAND_KWH = 20_000_000.0
SUPPORTED_TARGETS = (0.95, 0.99)


class SitePreset(str, Enum):
    RODINA = "rodina"
    SHAMSHI = "shamshi"
    CUSTOM = "custom"


class DemandMode(str, Enum):
    RODINA_BENCHMARK = "rodina_benchmark"
    ESTIMATED_ANNUAL = "estimated_annual"
    ESTIMATED_MONTHLY = "estimated_monthly"
    HOURLY_UPLOAD = "hourly_upload"


class DemandSourceType(str, Enum):
    MEASURED = "MEASURED"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    SOURCE_RECONSTRUCTED = "SOURCE_RECONSTRUCTED"
    PROXY_DERIVED = "PROXY_DERIVED"
    SYNTHETIC_ESTIMATE = "SYNTHETIC_ESTIMATE"
    USER_PROVIDED = "USER_PROVIDED"


class DemandConfidence(str, Enum):
    MEASURED = "Measured"
    STRONG_SOURCE_RECONSTRUCTION = "Strong source reconstruction"
    PROXY_ESTIMATE = "Proxy estimate"
    SYNTHETIC_PLANNING_ESTIMATE = "Synthetic planning estimate"
    USER_PROVIDED_UNVERIFIED = "User-provided, unverified"


class PlanningSite(DomainModel):
    preset: SitePreset
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    country: str = Field(default="Kazakhstan", min_length=1, max_length=120)
    timezone_offset: str = Field(default="+05:00", pattern=r"^[+-](?:0\d|1\d|2[0-3]):[0-5]\d$")


class DemandSpecification(DomainModel):
    mode: DemandMode
    source_type: DemandSourceType
    confidence: DemandConfidence
    profile_shape: Literal[
        "flat_within_month", "residential_like", "community_facility_like"
    ] = "community_facility_like"
    annual_kwh: float | None = Field(default=None, gt=0)
    monthly_kwh: tuple[float, ...] | None = None
    source_name: str | None = Field(default=None, max_length=240)
    source_url: str | None = Field(default=None, max_length=1000)
    source_year: int | None = Field(default=None, ge=1900, le=9998)
    method_notes: str = Field(min_length=1, max_length=2000)
    upload_filename: str | None = Field(default=None, max_length=260)
    upload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> DemandSpecification:
        if self.monthly_kwh is not None:
            if len(self.monthly_kwh) != 12:
                raise ValueError("monthly_kwh must contain exactly 12 monthly totals")
            if any(not math.isfinite(value) or value < 0 for value in self.monthly_kwh):
                raise ValueError("monthly_kwh values must be finite and non-negative")
            if math.fsum(self.monthly_kwh) <= 0:
                raise ValueError("monthly_kwh must have a positive annual total")
        if self.mode is DemandMode.ESTIMATED_ANNUAL and self.annual_kwh is None:
            raise ValueError("estimated annual demand requires annual_kwh")
        if self.mode is DemandMode.ESTIMATED_MONTHLY and self.monthly_kwh is None:
            raise ValueError("estimated monthly demand requires monthly_kwh")
        if self.mode is DemandMode.HOURLY_UPLOAD and (
            self.upload_filename is None or self.upload_sha256 is None
        ):
            raise ValueError("hourly upload requires a filename and SHA-256")
        if self.source_type is DemandSourceType.PROXY_DERIVED and not self.source_name:
            raise ValueError("proxy-derived demand requires a visible source name")
        if self.mode is DemandMode.RODINA_BENCHMARK and (
            self.source_type is not DemandSourceType.SOURCE_RECONSTRUCTED
        ):
            raise ValueError("Rodina benchmark demand must be source-reconstructed")
        return self


class TechnologySelection(DomainModel):
    wind_keys: tuple[str, ...] = ()
    pv_keys: tuple[str, ...] = ()
    battery_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_generation(self) -> TechnologySelection:
        if not self.wind_keys and not self.pv_keys:
            raise ValueError("select at least one wind or PV technology")
        for values in (self.wind_keys, self.pv_keys, self.battery_keys):
            if len(values) != len(set(values)):
                raise ValueError("technology selections must not contain duplicates")
        return self


class PlanningScenario(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    site: PlanningSite
    reference_year: int = Field(default=2025, ge=1940, le=9998)
    demand: DemandSpecification
    reliability_target: Literal[0.95, 0.99]
    technologies: TechnologySelection
    weather_provider: Literal["Open-Meteo Historical Weather API"] = (
        "Open-Meteo Historical Weather API"
    )
    weather_model: Literal["ERA5"] = "ERA5"

    @model_validator(mode="after")
    def validate_site_demand_pair(self) -> PlanningScenario:
        if (
            self.demand.mode is DemandMode.RODINA_BENCHMARK
            and self.site.preset is not SitePreset.RODINA
        ):
            raise ValueError("Rodina benchmark demand can only be used at the Rodina site")
        annual = self.demand.annual_kwh
        if self.demand.monthly_kwh is not None:
            annual = math.fsum(self.demand.monthly_kwh)
        if annual is not None and not MINIMUM_ANNUAL_DEMAND_KWH <= annual <= MAXIMUM_ANNUAL_DEMAND_KWH:
            raise ValueError(
                f"annual demand must be between {MINIMUM_ANNUAL_DEMAND_KWH:g} and "
                f"{MAXIMUM_ANNUAL_DEMAND_KWH:g} kWh"
            )
        return self

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @property
    def input_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def scenario_id(self) -> str:
        return f"scenario-{self.input_hash[:16]}"


class PlanningDemand(DomainModel):
    timestamps: tuple[datetime, ...]
    demand_kwh: tuple[float, ...]
    source_type: DemandSourceType
    confidence: DemandConfidence
    method: str
    source_name: str | None = None
    source_url: str | None = None
    source_year: int | None = None
    units: Literal["kWh per hourly interval"] = "kWh per hourly interval"

    @model_validator(mode="after")
    def validate_hourly_trace(self) -> PlanningDemand:
        if len(self.timestamps) not in (8760, 8784):
            raise ValueError("planning demand must contain exactly 8,760 or 8,784 hours")
        if len(self.timestamps) != len(self.demand_kwh):
            raise ValueError("timestamps and demand_kwh must have equal lengths")
        if any(timestamp.tzinfo is None for timestamp in self.timestamps):
            raise ValueError("all planning-demand timestamps must be timezone-aware")
        if len(set(self.timestamps)) != len(self.timestamps):
            raise ValueError("planning demand contains duplicate timestamps")
        for previous, current in zip(self.timestamps, self.timestamps[1:], strict=False):
            if current - previous != timedelta(hours=1):
                raise ValueError("planning demand must be a consecutive hourly series")
        if any(not math.isfinite(value) or value < 0 for value in self.demand_kwh):
            raise ValueError("demand_kwh must be finite and non-negative")
        if math.fsum(self.demand_kwh) <= 0:
            raise ValueError("planning demand must have positive annual energy")
        return self

    @property
    def annual_kwh(self) -> float:
        return math.fsum(self.demand_kwh)

    @property
    def sha256(self) -> str:
        payload = "\n".join(
            f"{timestamp.isoformat()},{value:.12g}"
            for timestamp, value in zip(self.timestamps, self.demand_kwh, strict=True)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PlanningDesign(DomainModel):
    wind_key: str | None
    wind_count: int = Field(ge=0)
    pv_key: str | None
    pv_count: int = Field(ge=0)
    battery_key: str | None
    battery_count: int = Field(ge=0)
    wind_capacity_kw: float = Field(ge=0)
    pv_dc_capacity_kw: float = Field(ge=0)
    pv_ac_capacity_kw: float = Field(ge=0)
    battery_usable_capacity_kwh: float = Field(ge=0)


class PlanningMetrics(DomainModel):
    annual_load_kwh: float = Field(gt=0)
    renewable_generation_kwh: float = Field(ge=0)
    served_energy_kwh: float = Field(ge=0)
    unmet_energy_kwh: float = Field(ge=0)
    served_fraction: float = Field(ge=0, le=1)
    lpsp: float = Field(ge=0, le=1)
    loss_of_load_hours: int = Field(ge=0)
    longest_deficit_hours: int = Field(ge=0)
    maximum_hourly_deficit_kwh: float = Field(ge=0)
    curtailment_kwh: float = Field(ge=0)
    curtailment_fraction: float = Field(ge=0)
    battery_throughput_kwh: float = Field(ge=0)


class PlanningEconomics(DomainModel):
    initial_capex_usd: float = Field(ge=0)
    net_present_cost_usd: float = Field(ge=0)
    equivalent_annual_cost_usd: float = Field(ge=0)
    cost_per_served_kwh_usd: float = Field(ge=0)
    economic_classes: dict[str, str]
    reference_capex_basis: dict[str, str]
    economic_sources: dict[str, str | None]


class PlanningResult(DomainModel):
    schema_version: Literal["phase14.v1"] = "phase14.v1"
    scenario_id: str
    scenario_name: str
    scenario_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    demand_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    weather_cache_key: str
    weather_cache_status: str
    weather_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    weather_source: str
    weather_model: str
    weather_start_utc: datetime
    weather_end_utc: datetime
    scenario_timezone: str
    annual_demand_kwh: float = Field(gt=0)
    demand_source_type: DemandSourceType
    demand_confidence: DemandConfidence
    demand_method: str
    reliability_target: Literal[0.95, 0.99]
    feasible: bool
    design: PlanningDesign | None
    metrics: PlanningMetrics | None
    economics: PlanningEconomics | None
    optimizer_method: Literal["phase10_staged_generalized", "exact_reduced_space"]
    evaluated_portfolios: int = Field(ge=0)
    dispatch_simulations: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    stage_timings_seconds: dict[str, float] = Field(default_factory=dict)
    assumptions: tuple[str, ...]
    software_version: str
