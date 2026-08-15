"""Auditable artifacts for Rodina weather-demand pairing."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from steppegrid.benchmarks.models import SourceIntegrityReport
from steppegrid.benchmarks.paired import (
    LocalYearInterval,
    PairedAnalysisResult,
    RodinaBenchmarkSiteConfig,
)
from steppegrid.simulation.models import WeatherDataset
from steppegrid.site.analysis import PilotSiteAnalysis


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_weather_outputs(
    config: RodinaBenchmarkSiteConfig,
    interval: LocalYearInterval,
    weather: WeatherDataset,
    analysis: PilotSiteAnalysis,
    output: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "weather_summary.json", analysis.model_dump(mode="json"))
    with (output / "monthly_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = list(analysis.monthly[0].model_dump())
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in analysis.monthly:
            writer.writerow(row.model_dump())
    _write_json(
        output / "provenance.json",
        {
            "weather": weather.provenance.model_dump(mode="json"),
            "site": config.site.model_dump(mode="json"),
            "coordinate_anchor": config.coordinate_anchor.model_dump(mode="json"),
            "local_year_interval": interval.model_dump(mode="json"),
            "analysis_calendar_timezone": config.local_timezone_offset,
            "scientific_boundaries": [
                "ERA5 is gridded reanalysis, not a Rodina weather-station measurement.",
                "ERA5 10 m wind speed is not turbine output or hub-height wind speed.",
                "Shortwave radiation is a raw horizontal resource variable, not PV generation.",
            ],
        },
    )


def _write_aligned_result(result: PairedAnalysisResult, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    aligned = result.aligned
    with (output / "aligned_hourly.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            (
                "timestamp_utc",
                "timestamp_local",
                "month_local",
                "hour_of_day_local",
                "total_load_kwh",
                "temperature_c",
                "wind_speed_m_s",
                "solar_irradiance_w_m2",
            )
        )
        for index, local_timestamp in enumerate(aligned.timestamp_local):
            writer.writerow(
                (
                    aligned.timestamp_utc[index].isoformat(),
                    local_timestamp.isoformat(),
                    local_timestamp.month,
                    local_timestamp.hour,
                    aligned.total_load_kwh[index],
                    aligned.temperature_c[index],
                    aligned.wind_speed_m_s[index],
                    aligned.solar_irradiance_w_m2[index],
                )
            )
    _write_json(
        output / "summary.json",
        {
            "summary": result.summary.model_dump(mode="json"),
            "validation": result.validation.model_dump(mode="json"),
            "monthly": [row.model_dump(mode="json") for row in result.monthly],
        },
    )
    _write_json(
        output / "provenance.json",
        {
            "weather": aligned.provenance.weather.model_dump(mode="json"),
            "load": aligned.provenance.load.model_dump(mode="json"),
            "pairing": {
                key: value
                for key, value in aligned.provenance.model_dump(mode="json").items()
                if key not in {"weather", "load"}
            },
        },
    )


def _format_correlation(value: float | None) -> str:
    return "undefined (one input is constant)" if value is None else f"{value:.6f}"


def _comparison_report(
    config: RodinaBenchmarkSiteConfig,
    interval: LocalYearInterval,
    results: list[PairedAnalysisResult],
    integrity: SourceIntegrityReport,
) -> str:
    summaries = [result.summary for result in results]
    rows = "\n".join(
        "| {shape} | {energy:,.3f} | {peak:,.3f} | {factor:.4f} | {solar} | {wind} |".format(
            shape=summary.shape,
            energy=summary.annual_load_kwh,
            peak=summary.peak_hourly_load_kwh,
            factor=summary.load_factor,
            solar=_format_correlation(summary.hourly_load_solar_resource_correlation),
            wind=_format_correlation(summary.hourly_load_wind_speed_correlation),
        )
        for summary in summaries
    )
    peaks = [summary.peak_hourly_load_kwh for summary in summaries]
    load_factors = [summary.load_factor for summary in summaries]
    solar_correlations = [
        summary.hourly_load_solar_resource_correlation for summary in summaries
    ]
    wind_correlations = [
        summary.hourly_load_wind_speed_correlation for summary in summaries
    ]
    solar_defined = [value for value in solar_correlations if value is not None]
    wind_defined = [value for value in wind_correlations if value is not None]
    solar_range = (
        f"{min(solar_defined):.6f} to {max(solar_defined):.6f}"
        if solar_defined
        else "undefined"
    )
    wind_range = (
        f"{min(wind_defined):.6f} to {max(wind_defined):.6f}"
        if wind_defined
        else "undefined"
    )
    return f"""# Rodina paired weather-demand analysis

## Scope

- Site: {config.site.name}, {config.site.district}, {config.site.region}, {config.site.country}
- ERA5 sampling anchor: {config.site.latitude}, {config.site.longitude}
- Coordinate classification: {config.coordinate_anchor.classification}
- Local timezone: {config.local_timezone_offset}, fixed with no daylight-saving transition
- Local interval: {interval.local_start.isoformat()} to {interval.local_end.isoformat()} (end exclusive)
- Matching UTC interval: {interval.utc_start.isoformat()} to {interval.utc_end.isoformat()} (end exclusive)
- Aligned hours: {interval.hours}
- Load variant: {summaries[0].variant}
- Critical load: unknown and absent
- Outage schedule: absent

The coordinate is a verified sampling anchor within or associated with Rodina. It is not asserted to be the exact village centroid. The 2025 load timestamps are a non-leap calendar carrier for pairing reconstructed monthly constraints with real 2025 ERA5 weather; the publication does not establish measured 2025 hourly demand.

## Shape comparison

| Hourly assumption | Annual load (kWh) | Peak hourly load (kWh) | Load factor | Hourly load vs shortwave radiation Pearson r | Hourly load vs ERA5 10 m wind speed Pearson r |
|---|---:|---:|---:|---:|---:|
{rows}

Peak loads span {min(peaks):,.3f} to {max(peaks):,.3f} kWh per hourly interval. Load factors span {min(load_factors):.4f} to {max(load_factors):.4f}. Hourly solar-resource correlations span {solar_range}; hourly wind-resource correlations span {wind_range}.

## Robust findings

- All three assumptions conserve the same 8.02 GWh annual total and the same twelve published monthly-row constraints in Rodina local time.
- All three use the identical ERA5 resource record and the identical UTC+05:00 to UTC mapping.
- The monthly load-resource relationship is identical across shapes because intraday reconstruction does not alter monthly energy.
- The source arithmetic inconsistency remains visible: printed annual load is {integrity.load.published_annual_kwh:,} kWh while the monthly rows sum to {integrity.load.calculated_monthly_sum_kwh:,} kWh.

## Shape-sensitive findings

- Peak hourly load and load factor depend materially on assumed intraday behavior.
- Hourly solar-resource and wind-speed correlations change with the assumed hour-of-day profile even though monthly energy is fixed.
- No hourly shape is identified as the true Rodina demand profile; the publication supplies monthly totals, not 8,760 measured hourly observations.

## Interpretation boundary

These are resource-demand temporal-alignment diagnostics. Shortwave radiation is not PV generation, 10 m wind speed is not wind-turbine generation, and correlations are not renewable coverage, performance, sizing, or recommendations.
"""


def write_paired_analysis(
    *,
    config: RodinaBenchmarkSiteConfig,
    interval: LocalYearInterval,
    weather: WeatherDataset,
    weather_analysis: PilotSiteAnalysis,
    results: list[PairedAnalysisResult],
    integrity: SourceIntegrityReport,
    output_directory: str | Path,
) -> Path:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_weather_outputs(
        config, interval, weather, weather_analysis, output / "weather"
    )
    for result in results:
        _write_aligned_result(result, output / result.summary.shape)
    (output / "comparison.md").write_text(
        _comparison_report(config, interval, results, integrity), encoding="utf-8"
    )
    return output
