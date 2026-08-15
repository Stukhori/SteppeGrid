"""Timezone-correct pairing of Rodina reconstructed demand with ERA5 weather."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from statistics import correlation, fmean
from typing import Literal

import yaml
from pydantic import Field, model_validator

from steppegrid.benchmarks.models import ReconstructionResult
from steppegrid.benchmarks.reconstruction import (
    BenchmarkVariant,
    VALID_SHAPES,
    parse_fixed_utc_offset,
    reconstruct_hourly_load,
)
from steppegrid.benchmarks.source import (
    load_monthly_benchmark,
    validate_source_integrity,
)
from steppegrid.simulation.models import (
    DataProvenance,
    DomainModel,
    LoadProvenance,
    Location,
    WeatherDataset,
)
from steppegrid.site.analysis import PilotSiteAnalysis, analyze_full_year
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider

RODINA_SITE_CONFIG = Path("data/benchmarks/rodina/site.yaml")
RODINA_TIMEZONE_OFFSET = "+05:00"
PRIMARY_VARIANT: BenchmarkVariant = "published_monthly_rows"
ENERGY_TOLERANCE_KWH = 1e-6


class RodinaPairingError(ValueError):
    pass


class RodinaLocation(Location):
    district: str
    region: str


class CoordinateAnchorProvenance(DomainModel):
    classification: Literal["VERIFIED_SAMPLING_ANCHOR"]
    source: str
    description: str
    precision_note: str


class RodinaWeatherConfig(DomainModel):
    provider: Literal["open-meteo"] = "open-meteo"
    model: Literal["era5"] = "era5"
    cache_directory: str = "../../weather/cache"


class RodinaBenchmarkSiteConfig(DomainModel):
    site: RodinaLocation
    coordinate_anchor: CoordinateAnchorProvenance
    local_timezone_offset: Literal["+05:00"] = RODINA_TIMEZONE_OFFSET
    reference_year: int = Field(default=2025, ge=1900, le=9998)
    reference_year_is_source_period: Literal[False] = False
    source_directory: str = "."
    weather: RodinaWeatherConfig = Field(default_factory=RodinaWeatherConfig)
    output_directory: str = "../../../outputs/benchmarks/rodina/paired_analysis"

    @model_validator(mode="after")
    def require_verified_rodina_site(self) -> RodinaBenchmarkSiteConfig:
        expected = {
            "name": "Rodina",
            "district": "Tselinograd District",
            "region": "Akmola Region",
            "country": "Kazakhstan",
        }
        actual = {
            "name": self.site.name,
            "district": self.site.district,
            "region": self.site.region,
            "country": self.site.country,
        }
        if actual != expected:
            raise ValueError(f"Rodina site identity must be {expected}")
        return self


class LocalYearInterval(DomainModel):
    reference_year: int
    timezone_offset: str
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime
    hours: int


class PairingProvenance(DomainModel):
    weather: DataProvenance
    load: LoadProvenance
    site: RodinaLocation
    coordinate_anchor: CoordinateAnchorProvenance
    reference_year: int
    reference_year_is_source_period: bool
    local_timezone_offset: str
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime
    alignment_method: str
    critical_load_available: bool = False
    grid_outage_schedule_used: bool = False


class AlignedHourlyDataset(DomainModel):
    timestamp_utc: list[datetime]
    timestamp_local: list[datetime]
    total_load_kwh: list[float]
    temperature_c: list[float]
    wind_speed_m_s: list[float]
    solar_irradiance_w_m2: list[float]
    provenance: PairingProvenance

    @model_validator(mode="after")
    def validate_alignment(self) -> AlignedHourlyDataset:
        lengths = {
            len(self.timestamp_utc),
            len(self.timestamp_local),
            len(self.total_load_kwh),
            len(self.temperature_c),
            len(self.wind_speed_m_s),
            len(self.solar_irradiance_w_m2),
        }
        if len(lengths) != 1 or not self.timestamp_utc:
            raise ValueError("all paired hourly arrays must have one non-zero length")
        if len(set(self.timestamp_utc)) != len(self.timestamp_utc):
            raise ValueError("paired weather contains duplicate UTC timestamps")
        if len(set(self.timestamp_local)) != len(self.timestamp_local):
            raise ValueError("paired load contains duplicate local timestamps")
        for utc_timestamp, local_timestamp in zip(
            self.timestamp_utc, self.timestamp_local, strict=True
        ):
            if utc_timestamp.utcoffset() != timedelta(0):
                raise ValueError("paired weather timestamps must use UTC")
            if local_timestamp.astimezone(timezone.utc) != utc_timestamp:
                raise ValueError("local and UTC timestamps do not identify the same hour")
        for timestamps in (self.timestamp_utc, self.timestamp_local):
            for previous, current in zip(timestamps, timestamps[1:], strict=False):
                if current - previous != timedelta(hours=1):
                    raise ValueError("paired timestamps must be consecutive hourly intervals")
        required_values = (
            self.total_load_kwh,
            self.temperature_c,
            self.wind_speed_m_s,
            self.solar_irradiance_w_m2,
        )
        if any(not math.isfinite(value) for values in required_values for value in values):
            raise ValueError("paired required values must be finite")
        return self


class MonthlyPairedDiagnostic(DomainModel):
    month: int = Field(ge=1, le=12)
    monthly_load_kwh: float
    mean_wind_speed_10m_m_s: float
    horizontal_irradiation_kwh_m2: float
    mean_temperature_c: float
    normalized_load: float
    normalized_mean_wind: float
    normalized_solar_irradiation: float


class PairingValidationSummary(DomainModel):
    records: int
    weather_complete: bool
    load_complete: bool
    duplicate_utc_timestamps: int
    duplicate_local_timestamps: int
    missing_required_values: int
    local_to_utc_correct: bool
    chronological_order_valid: bool
    annual_energy_conserved: bool
    local_monthly_energy_conserved: bool


class PairedDemandResourceSummary(DomainModel):
    variant: str
    shape: str
    reference_year: int
    annual_load_kwh: float
    mean_hourly_load_kwh: float
    peak_hourly_load_kwh: float
    load_factor: float
    peak_local_timestamp: str
    peak_local_hour: int = Field(ge=0, le=23)
    hourly_load_solar_resource_correlation: float | None
    hourly_load_wind_speed_correlation: float | None
    monthly_load_solar_irradiation_correlation: float | None
    monthly_load_mean_wind_speed_correlation: float | None
    correlation_definition: str


class PairedAnalysisResult(DomainModel):
    aligned: AlignedHourlyDataset
    validation: PairingValidationSummary
    monthly: list[MonthlyPairedDiagnostic]
    summary: PairedDemandResourceSummary


@dataclass(frozen=True)
class RodinaPairedRun:
    config: RodinaBenchmarkSiteConfig
    interval: LocalYearInterval
    weather: WeatherDataset
    weather_analysis: PilotSiteAnalysis
    paired_results: tuple[PairedAnalysisResult, ...]
    output_directory: Path


def load_rodina_site_config(
    path: str | Path = RODINA_SITE_CONFIG,
) -> RodinaBenchmarkSiteConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise RodinaPairingError(f"Rodina site config does not exist: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RodinaPairingError("Rodina site config must contain a mapping")
    try:
        return RodinaBenchmarkSiteConfig.model_validate(raw)
    except ValueError as error:
        raise RodinaPairingError(f"invalid Rodina site config: {error}") from error


def local_year_interval(reference_year: int, timezone_offset: str) -> LocalYearInterval:
    local_timezone = parse_fixed_utc_offset(timezone_offset)
    local_start = datetime(reference_year, 1, 1, tzinfo=local_timezone)
    local_end = datetime(reference_year + 1, 1, 1, tzinfo=local_timezone)
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    hours = int((utc_end - utc_start).total_seconds() / 3600)
    return LocalYearInterval(
        reference_year=reference_year,
        timezone_offset=timezone_offset,
        local_start=local_start,
        local_end=local_end,
        utc_start=utc_start,
        utc_end=utc_end,
        hours=hours,
    )


def _normalize(values: list[float]) -> list[float]:
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return [0.0] * len(values)
    return [(value - minimum) / (maximum - minimum) for value in values]


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    return correlation(left, right)


def _with_pairing_load_provenance(
    result: ReconstructionResult,
    config: RodinaBenchmarkSiteConfig,
) -> ReconstructionResult:
    provenance = result.dataset.provenance
    updated_provenance = provenance.model_copy(
        update={
            "location": config.site,
            "location_description": (
                f"Rodina, Tselinograd District, Akmola Region, Kazakhstan; "
                f"weather sampling anchor {config.site.latitude}, {config.site.longitude}"
            ),
            "processing_steps": [
                *provenance.processing_steps,
                "Assigned local civil timestamps at fixed UTC+05:00 for weather pairing.",
                "Converted local timestamps to UTC only for row alignment; energy values were unchanged.",
            ],
            "timezone_assumption": (
                "UTC+05:00 is Rodina local civil time for the 2025 pairing carrier, with no "
                "daylight-saving transition. The publication does not establish that its "
                "monthly table represents measured calendar-year 2025 demand."
            ),
        }
    )
    dataset = result.dataset.model_copy(update={"provenance": updated_provenance})
    return result.model_copy(update={"dataset": dataset})


def pair_reconstructed_load_with_weather(
    load_result: ReconstructionResult,
    weather: WeatherDataset,
    config: RodinaBenchmarkSiteConfig,
) -> PairedAnalysisResult:
    interval = local_year_interval(
        load_result.summary.reference_year, config.local_timezone_offset
    )
    local_timezone = parse_fixed_utc_offset(config.local_timezone_offset)
    expected_local = [
        interval.local_start + timedelta(hours=index) for index in range(interval.hours)
    ]
    expected_utc = [timestamp.astimezone(timezone.utc) for timestamp in expected_local]
    load = load_result.dataset
    temperature = weather.series.temperature_c

    if load.critical_load_kwh is not None:
        raise RodinaPairingError("Rodina pairing must not contain invented critical load")
    if interval.hours != 8760:
        raise RodinaPairingError(
            f"Rodina reference year must contain 8760 hours, received {interval.hours}"
        )
    if any(timestamp.utcoffset() != local_timezone.utcoffset(None) for timestamp in load.timestamps):
        raise RodinaPairingError("Rodina load timestamps must use fixed UTC+05:00")
    if load.timestamps != expected_local:
        raise RodinaPairingError("Rodina load does not cover the complete local calendar year")
    if weather.series.timestamps != expected_utc:
        raise RodinaPairingError(
            "ERA5 weather does not cover the UTC interval matching the Rodina local year"
        )
    if temperature is None:
        raise RodinaPairingError("Rodina ERA5 weather is missing temperature_c")
    if [timestamp.astimezone(timezone.utc) for timestamp in load.timestamps] != expected_utc:
        raise RodinaPairingError("Rodina local-to-UTC timestamp conversion is incorrect")

    target_annual = math.fsum(load.total_load_kwh)
    local_month_totals = [
        math.fsum(
            value
            for timestamp, value in zip(
                load.timestamps, load.total_load_kwh, strict=True
            )
            if timestamp.month == month
        )
        for month in range(1, 13)
    ]
    monthly_targets = [row.source_target_kwh for row in load_result.validation]
    if any(
        abs(actual - target) > ENERGY_TOLERANCE_KWH
        for actual, target in zip(local_month_totals, monthly_targets, strict=True)
    ):
        raise RodinaPairingError("timezone pairing changed a local monthly load total")

    paired_provenance = PairingProvenance(
        weather=weather.provenance,
        load=load.provenance,
        site=config.site,
        coordinate_anchor=config.coordinate_anchor,
        reference_year=interval.reference_year,
        reference_year_is_source_period=config.reference_year_is_source_period,
        local_timezone_offset=config.local_timezone_offset,
        local_start=interval.local_start,
        local_end=interval.local_end,
        utc_start=interval.utc_start,
        utc_end=interval.utc_end,
        alignment_method=(
            "Load timestamps retain fixed-offset Rodina local civil time; each row is paired "
            "with the ERA5 UTC timestamp identifying the same hourly interval."
        ),
    )
    aligned = AlignedHourlyDataset(
        timestamp_utc=expected_utc,
        timestamp_local=load.timestamps,
        total_load_kwh=load.total_load_kwh,
        temperature_c=temperature,
        wind_speed_m_s=weather.series.wind_speed_m_s,
        solar_irradiance_w_m2=weather.series.solar_irradiance_w_m2,
        provenance=paired_provenance,
    )
    if abs(math.fsum(aligned.total_load_kwh) - target_annual) > ENERGY_TOLERANCE_KWH:
        raise RodinaPairingError("timezone pairing changed annual load energy")

    monthly_base: list[tuple[float, float, float, float]] = []
    for month in range(1, 13):
        indices = [
            index
            for index, timestamp in enumerate(aligned.timestamp_local)
            if timestamp.month == month
        ]
        monthly_base.append(
            (
                math.fsum(aligned.total_load_kwh[index] for index in indices),
                fmean(aligned.wind_speed_m_s[index] for index in indices),
                math.fsum(aligned.solar_irradiance_w_m2[index] for index in indices)
                / 1000.0,
                fmean(aligned.temperature_c[index] for index in indices),
            )
        )
    monthly_load = [row[0] for row in monthly_base]
    monthly_wind = [row[1] for row in monthly_base]
    monthly_solar = [row[2] for row in monthly_base]
    normalized_load = _normalize(monthly_load)
    normalized_wind = _normalize(monthly_wind)
    normalized_solar = _normalize(monthly_solar)
    monthly = [
        MonthlyPairedDiagnostic(
            month=month,
            monthly_load_kwh=values[0],
            mean_wind_speed_10m_m_s=values[1],
            horizontal_irradiation_kwh_m2=values[2],
            mean_temperature_c=values[3],
            normalized_load=normalized_load[month - 1],
            normalized_mean_wind=normalized_wind[month - 1],
            normalized_solar_irradiation=normalized_solar[month - 1],
        )
        for month, values in enumerate(monthly_base, start=1)
    ]

    annual = math.fsum(aligned.total_load_kwh)
    peak_index = max(range(len(aligned.total_load_kwh)), key=aligned.total_load_kwh.__getitem__)
    peak = aligned.total_load_kwh[peak_index]
    mean = annual / len(aligned.total_load_kwh)
    summary = PairedDemandResourceSummary(
        variant=load_result.summary.variant,
        shape=load_result.summary.shape,
        reference_year=load_result.summary.reference_year,
        annual_load_kwh=annual,
        mean_hourly_load_kwh=mean,
        peak_hourly_load_kwh=peak,
        load_factor=mean / peak if peak else 0.0,
        peak_local_timestamp=aligned.timestamp_local[peak_index].isoformat(),
        peak_local_hour=aligned.timestamp_local[peak_index].hour,
        hourly_load_solar_resource_correlation=_pearson(
            aligned.total_load_kwh, aligned.solar_irradiance_w_m2
        ),
        hourly_load_wind_speed_correlation=_pearson(
            aligned.total_load_kwh, aligned.wind_speed_m_s
        ),
        monthly_load_solar_irradiation_correlation=_pearson(
            monthly_load, monthly_solar
        ),
        monthly_load_mean_wind_speed_correlation=_pearson(
            monthly_load, monthly_wind
        ),
        correlation_definition=(
            "Pearson correlations compare reconstructed hourly load (kWh per hourly interval) "
            "with coincident raw ERA5 shortwave radiation (W/m2) or 10 m wind speed (m/s). "
            "Monthly correlations compare local-calendar monthly load energy with monthly "
            "horizontal irradiation or monthly mean 10 m wind speed. They describe timing, "
            "not generation, renewable coverage, or system performance."
        ),
    )
    validation = PairingValidationSummary(
        records=len(aligned.timestamp_utc),
        weather_complete=weather.series.timestamps == expected_utc,
        load_complete=load.timestamps == expected_local,
        duplicate_utc_timestamps=len(aligned.timestamp_utc)
        - len(set(aligned.timestamp_utc)),
        duplicate_local_timestamps=len(aligned.timestamp_local)
        - len(set(aligned.timestamp_local)),
        missing_required_values=0,
        local_to_utc_correct=True,
        chronological_order_valid=True,
        annual_energy_conserved=True,
        local_monthly_energy_conserved=True,
    )
    return PairedAnalysisResult(
        aligned=aligned,
        validation=validation,
        monthly=monthly,
        summary=summary,
    )


def analyze_rodina_paired(
    config_path: str | Path = RODINA_SITE_CONFIG,
    *,
    reference_year: int | None = None,
    variant: BenchmarkVariant = PRIMARY_VARIANT,
    refresh: bool = False,
    source_directory: str | Path | None = None,
    cache_directory: str | Path | None = None,
    output_directory: str | Path | None = None,
    provider: OpenMeteoHistoricalWeatherProvider | None = None,
    create_plots: bool = True,
) -> RodinaPairedRun:
    config_path = Path(config_path)
    config = load_rodina_site_config(config_path)
    if reference_year is not None:
        config = config.model_copy(update={"reference_year": reference_year})
    interval = local_year_interval(config.reference_year, config.local_timezone_offset)
    base = config_path.parent
    source_root = (
        Path(source_directory) if source_directory is not None else base / config.source_directory
    )
    cache_root = (
        Path(cache_directory)
        if cache_directory is not None
        else base / config.weather.cache_directory
    )
    output_root = (
        Path(output_directory)
        if output_directory is not None
        else base / config.output_directory
    )
    weather_provider = provider or OpenMeteoHistoricalWeatherProvider(cache_root=cache_root)
    weather = weather_provider.get_hourly_weather(
        config.site, interval.utc_start, interval.utc_end, refresh=refresh
    )
    local_timezone: tzinfo = parse_fixed_utc_offset(config.local_timezone_offset)
    weather_analysis = analyze_full_year(
        weather,
        interval.utc_start,
        interval.utc_end,
        calendar_timezone=local_timezone,
    )
    source = load_monthly_benchmark(source_root)
    integrity = validate_source_integrity(source)
    results: list[PairedAnalysisResult] = []
    for shape in VALID_SHAPES:
        reconstructed = reconstruct_hourly_load(
            source,
            variant=variant,
            shape=shape,
            reference_year=config.reference_year,
            timezone_offset=config.local_timezone_offset,
        )
        contextualized = _with_pairing_load_provenance(reconstructed, config)
        results.append(
            pair_reconstructed_load_with_weather(contextualized, weather, config)
        )

    from steppegrid.benchmarks.paired_outputs import write_paired_analysis

    write_paired_analysis(
        config=config,
        interval=interval,
        weather=weather,
        weather_analysis=weather_analysis,
        results=results,
        integrity=integrity,
        output_directory=output_root,
    )
    if create_plots:
        from steppegrid.benchmarks.paired_plots import create_paired_plots

        create_paired_plots(results, output_root / "plots")
    return RodinaPairedRun(
        config=config,
        interval=interval,
        weather=weather,
        weather_analysis=weather_analysis,
        paired_results=tuple(results),
        output_directory=output_root,
    )
