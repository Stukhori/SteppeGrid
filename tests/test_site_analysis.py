from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from steppegrid.simulation.models import DataProvenance, Location, WeatherDataset, WeatherSeries
from steppegrid.site.analysis import analyze_full_year, validate_complete_year
from steppegrid.site.config import (
    PilotSiteConfig,
    PilotSiteConfigError,
    PilotWeatherConfig,
    load_pilot_site_config,
)
from steppegrid.site.report import render_site_report
from steppegrid.site.workflow import analyze_pilot_site
from steppegrid.weather.inspection import percentile


def _year_dataset(year: int, *, wind_value=None, solar_value=None) -> WeatherDataset:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    hours = int((end - start).total_seconds() / 3600)
    timestamps = [start + timedelta(hours=index) for index in range(hours)]
    wind = [float(wind_value(timestamp) if wind_value else timestamp.month) for timestamp in timestamps]
    solar = [float(solar_value(timestamp) if solar_value else timestamp.month * 100) for timestamp in timestamps]
    temperature = [float(timestamp.month - 6) for timestamp in timestamps]
    return WeatherDataset(
        series=WeatherSeries(
            timestamps=timestamps,
            wind_speed_m_s=wind,
            solar_irradiance_w_m2=solar,
            temperature_c=temperature,
        ),
        provenance=DataProvenance(
            source="offline annual test fixture",
            provider="Open-Meteo Historical Weather API",
            underlying_model="ERA5",
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            latitude=50,
            longitude=70,
            requested_latitude=50,
            requested_longitude=70,
            returned_latitude=50,
            returned_longitude=70,
            start_time=start,
            end_time=end,
            timezone="UTC",
            cache_key="fixture-cache-key",
            original_units={
                "wind_speed_10m": "m/s",
                "shortwave_radiation": "W/m²",
                "temperature_2m": "°C",
            },
            normalized_units={
                "wind_speed_m_s": "m/s",
                "solar_irradiance_w_m2": "W/m2",
                "temperature_c": "degC",
            },
        ),
    )


def _pilot_config(year: int = 2025) -> PilotSiteConfig:
    return PilotSiteConfig(
        site=Location(name="Offline test site", latitude=50, longitude=70),
        weather=PilotWeatherConfig(
            start_date=f"{year}-01-01", end_date=f"{year + 1}-01-01"
        ),
    )


def test_normal_year_requires_8760_records():
    dataset = _year_dataset(2025)
    quality = validate_complete_year(
        dataset,
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert quality.expected_records == 8760
    assert quality.received_records == 8760


def test_leap_year_requires_8784_records():
    dataset = _year_dataset(2024)
    quality = validate_complete_year(
        dataset,
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert quality.expected_records == 8784
    assert quality.received_records == 8784


def test_monthly_aggregation_uses_calendar_hours():
    analysis = analyze_full_year(
        _year_dataset(2025),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    january = analysis.monthly[0]
    february = analysis.monthly[1]
    assert january.records == 31 * 24
    assert february.records == 28 * 24
    assert january.mean_wind_speed_10m_m_s == pytest.approx(1)
    assert february.median_wind_speed_10m_m_s == pytest.approx(2)


def test_percentile_uses_linear_interpolation():
    assert percentile([0.0, 10.0], 0.05) == pytest.approx(0.5)
    assert percentile([0.0, 10.0], 0.25) == pytest.approx(2.5)
    assert percentile([0.0, 10.0], 0.95) == pytest.approx(9.5)


def test_solar_irradiation_converts_hourly_mean_w_m2_to_kwh_m2():
    analysis = analyze_full_year(
        _year_dataset(2025, solar_value=lambda timestamp: 100),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert analysis.solar.annual_mean_irradiance_w_m2 == pytest.approx(100)
    assert analysis.solar.annual_horizontal_irradiation_kwh_m2 == pytest.approx(876)
    assert analysis.monthly[0].horizontal_irradiation_kwh_m2 == pytest.approx(74.4)


def test_report_generation_is_conservative_and_complete():
    config = _pilot_config()
    dataset = _year_dataset(2025)
    analysis = analyze_full_year(dataset, config.start_datetime, config.end_datetime)
    report = render_site_report(config, analysis, dataset.provenance)
    assert "ERA5 10 m wind speed" in report
    assert "not a measured village weather-station record" in report
    assert "makes no equipment or installation recommendation" in report
    assert "Annual horizontal irradiation" in report


def test_workflow_is_reproducible_from_same_cached_dataset(tmp_path):
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        """site:
  name: Offline test site
  latitude: 50
  longitude: 70
  country: Kazakhstan
weather:
  provider: open-meteo
  model: era5
  start_date: 2025-01-01
  end_date: 2026-01-01
  cache_directory: cache
output_directory: output
""",
        encoding="utf-8",
    )
    dataset = _year_dataset(2025)

    class FixedProvider:
        def get_hourly_weather(self, location, start, end, *, refresh=False):
            return dataset

    output = tmp_path / "result"
    first = analyze_pilot_site(
        config_path, output_directory=output, provider=FixedProvider(), create_plots=False
    )
    first_json = (first / "weather_summary.json").read_bytes()
    first_report = (first / "report.md").read_bytes()
    second = analyze_pilot_site(
        config_path, output_directory=output, provider=FixedProvider(), create_plots=False
    )
    assert (second / "weather_summary.json").read_bytes() == first_json
    assert (second / "report.md").read_bytes() == first_report
    assert (second / "monthly_summary.csv").is_file()
    assert (second / "provenance.json").is_file()
    assert (second / "simulation_weather_reference.yaml").is_file()


def test_placeholder_pilot_config_fails_with_fields_to_replace(tmp_path):
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(
        """site:
  name: REPLACE_ME
  latitude: REPLACE_ME
  longitude: REPLACE_ME
  country: Kazakhstan
weather:
  provider: open-meteo
  model: era5
  start_date: 2025-01-01
  end_date: 2026-01-01
""",
        encoding="utf-8",
    )
    with pytest.raises(PilotSiteConfigError, match="site.name, site.latitude, site.longitude"):
        load_pilot_site_config(config_path)
