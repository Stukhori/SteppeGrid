"""Full-year quality checks and descriptive ERA5 resource statistics."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import correlation, fmean, median, pstdev

from pydantic import Field

from steppegrid.simulation.models import DomainModel, WeatherDataset
from steppegrid.weather.inspection import percentile


class SiteAnalysisError(ValueError):
    pass


class DataQualitySummary(DomainModel):
    expected_records: int
    received_records: int
    missing_timestamps: int
    duplicate_timestamps: int
    missing_required_values: int
    timezone: str


class WindResourceSummary(DomainModel):
    label: str = "ERA5 10 m wind speed"
    mean_m_s: float
    median_m_s: float
    standard_deviation_m_s: float
    percentile_5_m_s: float
    percentile_25_m_s: float
    percentile_75_m_s: float
    percentile_95_m_s: float
    maximum_m_s: float
    percent_below_2_m_s: float
    percent_2_to_3_m_s: float
    percent_3_to_5_m_s: float
    percent_5_to_8_m_s: float
    percent_above_8_m_s: float


class SolarResourceSummary(DomainModel):
    annual_mean_irradiance_w_m2: float
    annual_horizontal_irradiation_kwh_m2: float
    highest_irradiation_month: str
    lowest_irradiation_month: str


class TemperatureSummary(DomainModel):
    annual_mean_c: float
    minimum_c: float
    maximum_c: float


class MonthlyResourceSummary(DomainModel):
    month: int = Field(ge=1, le=12)
    month_name: str
    records: int
    mean_wind_speed_10m_m_s: float
    median_wind_speed_10m_m_s: float
    mean_shortwave_irradiance_w_m2: float
    horizontal_irradiation_kwh_m2: float
    mean_temperature_c: float
    normalized_mean_wind: float
    normalized_solar_irradiation: float


class PilotSiteAnalysis(DomainModel):
    data_quality: DataQualitySummary
    wind: WindResourceSummary
    solar: SolarResourceSummary
    temperature: TemperatureSummary
    monthly: list[MonthlyResourceSummary]
    monthly_wind_solar_correlation: float | None
    correlation_definition: str


def expected_full_year_timestamps(start: datetime, end: datetime) -> list[datetime]:
    if start.tzinfo is None or end.tzinfo is None or start.utcoffset() != timedelta(0):
        raise SiteAnalysisError("pilot year must use timezone-aware UTC datetimes")
    if end.utcoffset() != timedelta(0):
        raise SiteAnalysisError("pilot year must use timezone-aware UTC datetimes")
    if (start.month, start.day, start.hour, start.minute, start.second) != (1, 1, 0, 0, 0):
        raise SiteAnalysisError("pilot year must start at January 1 00:00 UTC")
    if end != start.replace(year=start.year + 1):
        raise SiteAnalysisError("pilot year must end at January 1 00:00 UTC of the next year")
    hours = int((end - start).total_seconds() / 3600)
    return [start + timedelta(hours=index) for index in range(hours)]


def validate_complete_year(dataset: WeatherDataset, start: datetime, end: datetime) -> DataQualitySummary:
    expected = expected_full_year_timestamps(start, end)
    timestamps = dataset.series.timestamps
    duplicate_count = len(timestamps) - len(set(timestamps))
    missing = [timestamp for timestamp in expected if timestamp not in set(timestamps)]
    if duplicate_count:
        raise SiteAnalysisError(f"pilot weather contains {duplicate_count} duplicate timestamps")
    if timestamps != expected:
        detail = missing[0].isoformat() if missing else "unexpected UTC chronology"
        raise SiteAnalysisError(
            f"incomplete pilot weather year: expected {len(expected)} hourly records, "
            f"received {len(timestamps)}; first issue: {detail}"
        )
    temperature = dataset.series.temperature_c
    if temperature is None:
        raise SiteAnalysisError("pilot weather is missing temperature_c")
    required_lengths = {
        len(dataset.series.wind_speed_m_s),
        len(dataset.series.solar_irradiance_w_m2),
        len(temperature),
    }
    if required_lengths != {len(expected)}:
        raise SiteAnalysisError("pilot weather required arrays do not match the full-year length")
    return DataQualitySummary(
        expected_records=len(expected),
        received_records=len(timestamps),
        missing_timestamps=0,
        duplicate_timestamps=0,
        missing_required_values=0,
        timezone="UTC",
    )


def _normalize(values: list[float]) -> list[float]:
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return [0.0] * len(values)
    return [(value - minimum) / (maximum - minimum) for value in values]


def analyze_full_year(dataset: WeatherDataset, start: datetime, end: datetime) -> PilotSiteAnalysis:
    quality = validate_complete_year(dataset, start, end)
    wind = dataset.series.wind_speed_m_s
    solar = dataset.series.solar_irradiance_w_m2
    temperature = dataset.series.temperature_c
    assert temperature is not None
    count = len(wind)

    grouped: dict[int, list[int]] = defaultdict(list)
    for index, timestamp in enumerate(dataset.series.timestamps):
        grouped[timestamp.month].append(index)

    monthly_base: list[dict[str, float | int | str]] = []
    for month in range(1, 13):
        indices = grouped[month]
        month_wind = [wind[index] for index in indices]
        month_solar = [solar[index] for index in indices]
        month_temperature = [temperature[index] for index in indices]
        monthly_base.append(
            {
                "month": month,
                "month_name": calendar.month_name[month],
                "records": len(indices),
                "mean_wind_speed_10m_m_s": fmean(month_wind),
                "median_wind_speed_10m_m_s": median(month_wind),
                "mean_shortwave_irradiance_w_m2": fmean(month_solar),
                "horizontal_irradiation_kwh_m2": sum(month_solar) / 1000.0,
                "mean_temperature_c": fmean(month_temperature),
            }
        )

    monthly_wind = [float(row["mean_wind_speed_10m_m_s"]) for row in monthly_base]
    monthly_solar = [float(row["horizontal_irradiation_kwh_m2"]) for row in monthly_base]
    normalized_wind = _normalize(monthly_wind)
    normalized_solar = _normalize(monthly_solar)
    monthly = [
        MonthlyResourceSummary(
            **row,
            normalized_mean_wind=normalized_wind[index],
            normalized_solar_irradiation=normalized_solar[index],
        )
        for index, row in enumerate(monthly_base)
    ]
    monthly_correlation = (
        correlation(monthly_wind, monthly_solar)
        if len(set(monthly_wind)) > 1 and len(set(monthly_solar)) > 1
        else None
    )

    def percentage(predicate) -> float:
        return 100.0 * sum(predicate(value) for value in wind) / count

    highest_solar = max(monthly, key=lambda row: row.horizontal_irradiation_kwh_m2)
    lowest_solar = min(monthly, key=lambda row: row.horizontal_irradiation_kwh_m2)
    return PilotSiteAnalysis(
        data_quality=quality,
        wind=WindResourceSummary(
            mean_m_s=fmean(wind),
            median_m_s=median(wind),
            standard_deviation_m_s=pstdev(wind),
            percentile_5_m_s=percentile(wind, 0.05),
            percentile_25_m_s=percentile(wind, 0.25),
            percentile_75_m_s=percentile(wind, 0.75),
            percentile_95_m_s=percentile(wind, 0.95),
            maximum_m_s=max(wind),
            percent_below_2_m_s=percentage(lambda value: value < 2),
            percent_2_to_3_m_s=percentage(lambda value: 2 <= value < 3),
            percent_3_to_5_m_s=percentage(lambda value: 3 <= value < 5),
            percent_5_to_8_m_s=percentage(lambda value: 5 <= value <= 8),
            percent_above_8_m_s=percentage(lambda value: value > 8),
        ),
        solar=SolarResourceSummary(
            annual_mean_irradiance_w_m2=fmean(solar),
            annual_horizontal_irradiation_kwh_m2=sum(solar) / 1000.0,
            highest_irradiation_month=highest_solar.month_name,
            lowest_irradiation_month=lowest_solar.month_name,
        ),
        temperature=TemperatureSummary(
            annual_mean_c=fmean(temperature),
            minimum_c=min(temperature),
            maximum_c=max(temperature),
        ),
        monthly=monthly,
        monthly_wind_solar_correlation=monthly_correlation,
        correlation_definition=(
            "Pearson correlation across 12 values: monthly mean ERA5 10 m wind speed "
            "and monthly horizontal irradiation. Correlation does not establish "
            "energy-system resilience."
        ),
    )
