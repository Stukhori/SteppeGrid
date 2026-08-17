"""Typed, serializable models for the Phase 16 village registry."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
)
from steppegrid.simulation.models import DomainModel

SITE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
DATASET_ID_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class SiteClassification(str, Enum):
    BENCHMARK = "BENCHMARK"
    FIELD_CASE = "FIELD_CASE"
    PLANNING_SITE = "PLANNING_SITE"
    CUSTOM_SITE = "CUSTOM_SITE"


class SiteOrigin(str, Enum):
    BUILT_IN = "BUILT_IN"
    USER_REGISTERED = "USER_REGISTERED"


class WeatherStatus(str, Enum):
    CACHED = "CACHED"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"


class PlanningReadiness(str, Enum):
    WEATHER_MISSING = "WEATHER_MISSING"
    DEMAND_MISSING = "DEMAND_MISSING"
    READY_FOR_PLANNING = "READY_FOR_PLANNING"
    BENCHMARK_READY = "BENCHMARK_READY"
    INVALID = "INVALID"


class ProvenanceSourceType(str, Enum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    PROJECT_RECORD = "PROJECT_RECORD"
    USER_PROVIDED = "USER_PROVIDED"
    DERIVED = "DERIVED"


class SourceReference(DomainModel):
    field: str = Field(min_length=1, max_length=120)
    source_name: str = Field(min_length=1, max_length=300)
    source_type: ProvenanceSourceType
    source_url: str | None = Field(default=None, max_length=1500)
    source_year: int | None = Field(default=None, ge=1900, le=9999)
    retrieved_date: date | None = None
    notes: str | None = Field(default=None, max_length=3000)


class DemandProxyMethod(DomainModel):
    schema_version: str = "phase16.demand-proxy-method.v1"
    methodology_id: str = Field(pattern=DATASET_ID_PATTERN)
    name: str = Field(min_length=1, max_length=300)
    base_year: int = Field(ge=1940, le=9998)
    rural_household_electricity_gwh: float = Field(gt=0)
    rural_population: int = Field(gt=0)
    household_kwh_per_capita: float = Field(gt=0)
    community_service_multiplier: float = Field(gt=0)
    planning_kwh_per_capita: float = Field(gt=0)
    classification: DemandSourceType = DemandSourceType.PROXY_DERIVED
    profile_shape: str = "community_facility_like"
    interpretation: str = Field(min_length=1, max_length=3000)
    provenance: tuple[SourceReference, ...]

    @model_validator(mode="after")
    def validate_calculation(self) -> DemandProxyMethod:
        expected_household = self.rural_household_electricity_gwh * 1_000_000 / self.rural_population
        expected_planning = expected_household * self.community_service_multiplier
        if abs(self.household_kwh_per_capita - expected_household) > 1e-4:
            raise ValueError("household per-capita value does not match the national inputs")
        if abs(self.planning_kwh_per_capita - expected_planning) > 1e-4:
            raise ValueError("planning per-capita value does not match the uplift calculation")
        if self.classification is not DemandSourceType.PROXY_DERIVED:
            raise ValueError("proxy methodology classification must be PROXY_DERIVED")
        return self


class ProxyDemandCalculation(DomainModel):
    methodology_id: str = Field(pattern=DATASET_ID_PATTERN)
    population_basis: int = Field(gt=0)
    planning_kwh_per_capita: float = Field(gt=0)
    annual_energy_unrounded_kwh: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_annual_energy(self) -> ProxyDemandCalculation:
        expected = self.population_basis * self.planning_kwh_per_capita
        if abs(self.annual_energy_unrounded_kwh - expected) > 1e-6:
            raise ValueError("proxy annual energy does not match population times per-capita demand")
        return self


class WeatherDatasetRef(DomainModel):
    weather_id: str = Field(pattern=DATASET_ID_PATTERN)
    source: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year: int = Field(ge=1940, le=9998)
    status: WeatherStatus
    variables: tuple[str, ...]
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    timezone: str = "UTC"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    cache_key: str | None = Field(default=None, pattern=SHA256_PATTERN)
    path: str | None = None
    metadata_path: str | None = None
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    provenance: tuple[SourceReference, ...] = ()

    @model_validator(mode="after")
    def cached_reference_is_complete(self) -> WeatherDatasetRef:
        if self.status is WeatherStatus.CACHED and not all(
            (self.start_utc, self.end_utc, self.cache_key, self.path, self.metadata_path, self.sha256)
        ):
            raise ValueError("cached weather requires period, paths, cache key, and SHA-256")
        return self


class DemandDatasetRef(DomainModel):
    demand_id: str = Field(pattern=DATASET_ID_PATTERN)
    site_id: str = Field(pattern=SITE_ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    mode: DemandMode
    classification: DemandSourceType
    confidence: DemandConfidence
    reference_year: int = Field(default=2025, ge=1940, le=9998)
    annual_energy_kwh: float = Field(gt=0)
    temporal_resolution: str = "hourly"
    profile_method: str = Field(min_length=1, max_length=2000)
    profile_shape: str = "community_facility_like"
    monthly_kwh: tuple[float, ...] | None = None
    path: str | None = None
    source_file_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    demand_sha256: str = Field(pattern=SHA256_PATTERN)
    proxy_calculation: ProxyDemandCalculation | None = None
    provenance: tuple[SourceReference, ...]
    created_at_utc: datetime | None = None

    @model_validator(mode="after")
    def validate_monthly_dataset(self) -> DemandDatasetRef:
        if self.mode is DemandMode.ESTIMATED_MONTHLY and (
            self.monthly_kwh is None or len(self.monthly_kwh) != 12
        ):
            raise ValueError("monthly demand datasets require 12 totals")
        if self.mode is DemandMode.HOURLY_UPLOAD and not self.path:
            raise ValueError("hourly demand datasets require a path")
        if self.proxy_calculation is not None:
            if self.classification is not DemandSourceType.PROXY_DERIVED:
                raise ValueError("proxy calculation requires PROXY_DERIVED classification")
            if abs(self.annual_energy_kwh - self.proxy_calculation.annual_energy_unrounded_kwh) > 1e-6:
                raise ValueError("dataset annual energy does not match its proxy calculation")
        return self


class VillageSite(DomainModel):
    schema_version: str = "phase16.site.v1"
    site_id: str = Field(pattern=SITE_ID_PATTERN)
    name: str = Field(min_length=1, max_length=160)
    native_name: str | None = Field(default=None, max_length=160)
    settlement_type: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=160)
    district: str | None = Field(default=None, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=80)
    timezone_offset: str = Field(pattern=r"^[+-](?:0\d|1\d|2[0-3]):[0-5]\d$")
    classification: SiteClassification
    origin: SiteOrigin
    population: int | None = Field(default=None, gt=0)
    population_year: int | None = Field(default=None, ge=1900, le=9999)
    population_is_approximate: bool = False
    household_count: int | None = Field(default=None, gt=0)
    household_count_year: int | None = Field(default=None, ge=1900, le=9999)
    elevation_m: float | None = None
    weather_datasets: tuple[WeatherDatasetRef, ...] = ()
    demand_datasets: tuple[DemandDatasetRef, ...] = ()
    provenance: tuple[SourceReference, ...]
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_site(self) -> VillageSite:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {self.timezone}") from error
        if len({item.weather_id for item in self.weather_datasets}) != len(self.weather_datasets):
            raise ValueError("weather IDs must be unique within a site")
        if len({item.demand_id for item in self.demand_datasets}) != len(self.demand_datasets):
            raise ValueError("demand IDs must be unique within a site")
        if any(item.site_id != self.site_id for item in self.demand_datasets):
            raise ValueError("demand dataset site_id does not match its site")
        required_fields = {"coordinates", "name", "region", "timezone"}
        present = {source.field for source in self.provenance}
        if not required_fields <= present:
            raise ValueError(f"site provenance missing fields: {sorted(required_fields - present)}")
        if self.population is not None and "population" not in present:
            raise ValueError("population requires provenance")
        if self.household_count is not None and "household_count" not in present:
            raise ValueError("household count requires provenance")
        return self

    @property
    def metadata_hash(self) -> str:
        payload = self.model_dump(
            mode="json", exclude={"weather_datasets", "demand_datasets"}
        )
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class SiteAuditCheck(DomainModel):
    site_id: str | None
    category: str
    status: str
    message: str


class SiteRegistryAudit(DomainModel):
    schema_version: str = "phase16.site-audit.v1"
    registered_sites: int
    valid_sites: int
    planning_ready_sites: int
    weather_missing: int
    demand_missing: int
    blockers: int
    warnings: int
    checks: tuple[SiteAuditCheck, ...]


class PopulatedSiteAuditEntry(DomainModel):
    site_id: str
    name: str
    region: str
    latitude: float
    longitude: float
    population: int
    population_year: int | None
    population_is_approximate: bool
    population_source: SourceReference
    demand_id: str
    demand_methodology_id: str
    annual_demand_kwh: float
    demand_classification: DemandSourceType
    weather_status: WeatherStatus
    planning_readiness: PlanningReadiness
    source_metadata: tuple[SourceReference, ...]
    site_metadata_hash: str
    demand_sha256: str
    weather_sha256: str | None


class PopulatedSitesAudit(DomainModel):
    schema_version: str = "phase16.populated-sites-audit.v1"
    demand_methodology: DemandProxyMethod
    sites: tuple[PopulatedSiteAuditEntry, ...]
    blockers: int


def suggest_site_id(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not value or not value[0].isalpha():
        value = f"site_{value}" if value else "site"
    return value


def resolve_registry_path(_registry_root: Path, relative_path: str | None) -> Path | None:
    if relative_path is None:
        return None
    path = Path(relative_path)
    return path
