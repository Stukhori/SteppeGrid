"""Typed contracts for literature-derived monthly energy benchmarks."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from steppegrid.simulation.models import DomainModel
from steppegrid.simulation.models import LoadDataset


class PublishedRange(DomainModel):
    minimum_kw: float = Field(ge=0)
    maximum_kw: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> PublishedRange:
        if self.maximum_kw < self.minimum_kw:
            raise ValueError("published range maximum cannot be below minimum")
        return self


class BenchmarkSourceMetadata(DomainModel):
    benchmark_name: str
    location_name: str
    region: str
    country: str
    publication_title: str
    authors: list[str]
    year: int
    journal: str
    issue: str
    doi: str
    source_url: str
    source_type: Literal["LITERATURE_DERIVED"]
    source_period: str
    source_table: str
    transcription_notes: list[str]
    published_annual_load_kwh: int = Field(ge=0)
    published_annual_pv_kwh: int = Field(ge=0)
    published_annual_wind_kwh: int = Field(ge=0)
    published_annual_generation_kwh: int = Field(ge=0)
    contextual_statements: dict[str, float | int]
    average_load_categories_kw: dict[str, PublishedRange]


class PublishedMonthlyEnergyRow(DomainModel):
    month: int = Field(ge=1, le=12)
    month_name: str
    load_kwh: int = Field(ge=0)
    pv_generation_kwh: int = Field(ge=0)
    wind_generation_kwh: int = Field(ge=0)
    published_total_generation_kwh: int = Field(ge=0)
    li_ion_soc_average: float = Field(ge=0, le=1)
    supercapacitor_soc_average: float = Field(ge=0, le=1)
    published_unserved_kwh: int = Field(ge=0)


class MonthlyLoadDataset(DomainModel):
    rows: list[PublishedMonthlyEnergyRow]
    provenance: BenchmarkSourceMetadata

    @model_validator(mode="after")
    def validate_calendar(self) -> MonthlyLoadDataset:
        if [row.month for row in self.rows] != list(range(1, 13)):
            raise ValueError("benchmark must contain January through December in order")
        return self


class IntegrityComparison(DomainModel):
    published_annual_kwh: int
    calculated_monthly_sum_kwh: int
    difference_kwh: int
    relative_difference: float
    matches: bool


class SourceIntegrityReport(DomainModel):
    benchmark_name: str
    load: IntegrityComparison
    pv: IntegrityComparison
    wind: IntegrityComparison
    generation: IntegrityComparison
    known_source_inconsistency: bool


class MonthlyReconstructionValidation(DomainModel):
    month: int
    month_name: str
    published_monthly_row_kwh: float
    source_target_kwh: float
    reconstructed_kwh: float
    absolute_error_kwh: float
    relative_error: float


class ReconstructedLoadSummary(DomainModel):
    variant: str
    shape: str
    reference_year: int
    timezone_offset: str
    records: int
    annual_energy_kwh: float
    published_annual_total_kwh: float
    difference_from_published_annual_kwh: float
    peak_hourly_load_kwh: float
    peak_timestamp: str
    mean_hourly_load_kwh: float
    load_factor: float
    critical_load_available: bool = False


class ReconstructionResult(DomainModel):
    dataset: LoadDataset
    validation: list[MonthlyReconstructionValidation]
    summary: ReconstructedLoadSummary
