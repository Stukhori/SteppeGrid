"""End-to-end cached pilot-site weather analysis and artifact generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from steppegrid.site.analysis import PilotSiteAnalysis, analyze_full_year
from steppegrid.site.config import PilotSiteConfig, load_pilot_site_config
from steppegrid.site.plots import create_site_plots
from steppegrid.site.report import render_site_report
from steppegrid.simulation.models import WeatherDataset
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider


def _write_summary_csv(analysis: PilotSiteAnalysis, path: Path) -> None:
    rows = [
        ("expected_records", analysis.data_quality.expected_records, "hourly records"),
        ("received_records", analysis.data_quality.received_records, "hourly records"),
        ("mean_wind_speed_10m", analysis.wind.mean_m_s, "m/s"),
        ("median_wind_speed_10m", analysis.wind.median_m_s, "m/s"),
        ("wind_standard_deviation", analysis.wind.standard_deviation_m_s, "m/s"),
        ("wind_percentile_5", analysis.wind.percentile_5_m_s, "m/s"),
        ("wind_percentile_25", analysis.wind.percentile_25_m_s, "m/s"),
        ("wind_percentile_75", analysis.wind.percentile_75_m_s, "m/s"),
        ("wind_percentile_95", analysis.wind.percentile_95_m_s, "m/s"),
        ("maximum_wind_speed_10m", analysis.wind.maximum_m_s, "m/s"),
        ("hours_wind_below_2_m_s", analysis.wind.percent_below_2_m_s, "%"),
        ("hours_wind_2_to_3_m_s", analysis.wind.percent_2_to_3_m_s, "%"),
        ("hours_wind_3_to_5_m_s", analysis.wind.percent_3_to_5_m_s, "%"),
        ("hours_wind_5_to_8_m_s", analysis.wind.percent_5_to_8_m_s, "%"),
        ("hours_wind_above_8_m_s", analysis.wind.percent_above_8_m_s, "%"),
        ("annual_mean_shortwave_irradiance", analysis.solar.annual_mean_irradiance_w_m2, "W/m2"),
        ("annual_horizontal_irradiation", analysis.solar.annual_horizontal_irradiation_kwh_m2, "kWh/m2"),
        ("annual_mean_temperature", analysis.temperature.annual_mean_c, "degC"),
        ("minimum_temperature", analysis.temperature.minimum_c, "degC"),
        ("maximum_temperature", analysis.temperature.maximum_c, "degC"),
        ("monthly_wind_solar_correlation", analysis.monthly_wind_solar_correlation, "Pearson r"),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("metric", "value", "unit"))
        writer.writerows(rows)


def _write_monthly_csv(analysis: PilotSiteAnalysis, path: Path) -> None:
    fieldnames = list(analysis.monthly[0].model_dump())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in analysis.monthly:
            writer.writerow(row.model_dump())


def _write_simulation_reference(
    config: PilotSiteConfig, dataset: WeatherDataset, cache_root: Path, path: Path
) -> None:
    reference = {
        "location": config.site.model_dump(mode="json"),
        "start_time": config.start_datetime.isoformat(),
        "end_time": config.end_datetime.isoformat(),
        "weather": {
            "provider": "open-meteo",
            "model": "era5",
            "cache_directory": str(cache_root.resolve()),
        },
    }
    path.write_text(
        yaml.safe_dump(reference, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def analyze_pilot_site(
    config_path: str | Path,
    *,
    refresh: bool = False,
    output_directory: str | Path | None = None,
    provider: OpenMeteoHistoricalWeatherProvider | None = None,
    create_plots: bool = True,
) -> Path:
    path = Path(config_path)
    config = load_pilot_site_config(path)
    base = path.parent
    cache_root = base / config.weather.cache_directory
    output = Path(output_directory) if output_directory else base / config.output_directory
    weather_provider = provider or OpenMeteoHistoricalWeatherProvider(cache_root=cache_root)
    dataset = weather_provider.get_hourly_weather(
        config.site, config.start_datetime, config.end_datetime, refresh=refresh
    )
    analysis = analyze_full_year(dataset, config.start_datetime, config.end_datetime)

    output.mkdir(parents=True, exist_ok=True)
    (output / "weather_summary.json").write_text(
        analysis.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    _write_summary_csv(analysis, output / "weather_summary.csv")
    _write_monthly_csv(analysis, output / "monthly_summary.csv")
    provenance_payload = {
        "provenance": dataset.provenance.model_dump(mode="json"),
        "record_count": len(dataset.series.timestamps),
        "software_assumptions": [
            "Hourly UTC timestep.",
            "ERA5 10 m wind is not adjusted to turbine hub height.",
            "Shortwave radiation is a preceding-hour mean integrated over one hour.",
            "No missing data interpolation or imputation.",
        ],
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        render_site_report(config, analysis, dataset.provenance), encoding="utf-8"
    )
    _write_simulation_reference(
        config, dataset, cache_root, output / "simulation_weather_reference.yaml"
    )
    if create_plots:
        create_site_plots(dataset, analysis, output)
    return output
