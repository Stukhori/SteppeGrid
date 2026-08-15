from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import correlation

import pytest

from steppegrid.benchmarks.paired import (
    RODINA_TIMEZONE_OFFSET,
    RodinaPairingError,
    analyze_rodina_paired,
    load_rodina_site_config,
    local_year_interval,
    pair_reconstructed_load_with_weather,
)
from steppegrid.benchmarks.paired_outputs import write_paired_analysis
from steppegrid.benchmarks.paired_plots import create_paired_plots
from steppegrid.benchmarks.reconstruction import VALID_SHAPES, reconstruct_hourly_load
from steppegrid.benchmarks.source import (
    load_monthly_benchmark,
    validate_source_integrity,
)
from steppegrid.simulation.models import (
    DataProvenance,
    LoadSourceType,
    WeatherDataset,
    WeatherSeries,
)
from steppegrid.site.analysis import analyze_full_year
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider


def _weather_dataset(start: datetime, end: datetime) -> WeatherDataset:
    hours = int((end - start).total_seconds() / 3600)
    timestamps = [start + timedelta(hours=index) for index in range(hours)]
    local = [timestamp.astimezone(timezone(timedelta(hours=5))) for timestamp in timestamps]
    wind = [
        4.2
        + 0.8 * math.sin(2 * math.pi * timestamp.timetuple().tm_yday / 365)
        + 0.3 * math.cos(2 * math.pi * timestamp.hour / 24)
        for timestamp in local
    ]
    solar = [
        max(0.0, math.sin(math.pi * (timestamp.hour - 6) / 12))
        * (500 + 250 * math.sin(2 * math.pi * (timestamp.timetuple().tm_yday - 80) / 365))
        for timestamp in local
    ]
    temperature = [
        5
        + 20 * math.sin(2 * math.pi * (timestamp.timetuple().tm_yday - 105) / 365)
        + 3 * math.sin(2 * math.pi * (timestamp.hour - 8) / 24)
        for timestamp in local
    ]
    return WeatherDataset(
        series=WeatherSeries(
            timestamps=timestamps,
            wind_speed_m_s=wind,
            solar_irradiance_w_m2=solar,
            temperature_c=temperature,
        ),
        provenance=DataProvenance(
            source="deterministic offline ERA5 fixture",
            provider="Open-Meteo Historical Weather API",
            underlying_model="ERA5",
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            latitude=51.25,
            longitude=70.5,
            requested_latitude=51.302445,
            requested_longitude=70.541645,
            returned_latitude=51.25,
            returned_longitude=70.5,
            coordinate_distance_km=6.5,
            start_time=start,
            end_time=end,
            original_units={
                "temperature_2m": "degC",
                "wind_speed_10m": "m/s",
                "shortwave_radiation": "W/m2",
            },
            normalized_units={
                "temperature_c": "degC",
                "wind_speed_m_s": "m/s",
                "solar_irradiance_w_m2": "W/m2",
            },
            timezone="UTC",
            temporal_resolution="hourly",
            variables_requested=[
                "temperature_2m",
                "wind_speed_10m",
                "shortwave_radiation",
            ],
            cache_key="offline-rodina-2025",
            cache_status="HIT",
        ),
    )


@pytest.fixture(scope="module")
def paired_fixture():
    config = load_rodina_site_config()
    interval = local_year_interval(2025, RODINA_TIMEZONE_OFFSET)
    weather = _weather_dataset(interval.utc_start, interval.utc_end)
    source = load_monthly_benchmark()
    results = []
    for shape in VALID_SHAPES:
        reconstruction = reconstruct_hourly_load(
            source,
            variant="published_monthly_rows",
            shape=shape,
            reference_year=2025,
            timezone_offset=RODINA_TIMEZONE_OFFSET,
        )
        results.append(
            pair_reconstructed_load_with_weather(reconstruction, weather, config)
        )
    return config, interval, weather, source, results


def test_rodina_site_and_local_year_boundaries_are_explicit(paired_fixture):
    config, interval, _, _, _ = paired_fixture
    assert config.site.name == "Rodina"
    assert config.site.district == "Tselinograd District"
    assert config.site.region == "Akmola Region"
    assert config.coordinate_anchor.classification == "VERIFIED_SAMPLING_ANCHOR"
    assert interval.local_start == datetime(
        2025, 1, 1, tzinfo=timezone(timedelta(hours=5))
    )
    assert interval.utc_start == datetime(2024, 12, 31, 19, tzinfo=timezone.utc)
    assert interval.local_end == datetime(
        2026, 1, 1, tzinfo=timezone(timedelta(hours=5))
    )
    assert interval.utc_end == datetime(2025, 12, 31, 19, tzinfo=timezone.utc)
    assert interval.hours == 8760


@pytest.mark.parametrize("shape", VALID_SHAPES)
def test_all_shapes_align_8760_hours_without_duplicates(paired_fixture, shape):
    _, interval, _, _, results = paired_fixture
    result = next(item for item in results if item.summary.shape == shape)
    assert result.validation.records == 8760
    assert result.validation.duplicate_utc_timestamps == 0
    assert result.validation.duplicate_local_timestamps == 0
    assert result.aligned.timestamp_local[0] == interval.local_start
    assert result.aligned.timestamp_utc[0] == interval.utc_start
    assert result.aligned.timestamp_local[-1] == interval.local_end - timedelta(hours=1)
    assert result.aligned.timestamp_utc[-1] == interval.utc_end - timedelta(hours=1)
    assert all(
        local.astimezone(timezone.utc) == utc
        for local, utc in zip(
            result.aligned.timestamp_local,
            result.aligned.timestamp_utc,
            strict=True,
        )
    )


def test_timezone_pairing_preserves_annual_and_local_monthly_energy(paired_fixture):
    _, _, _, source, results = paired_fixture
    published_months = [row.load_kwh for row in source.rows]
    for result in results:
        assert math.fsum(result.aligned.total_load_kwh) == pytest.approx(
            sum(published_months), abs=1e-6
        )
        for month, target in enumerate(published_months, start=1):
            total = math.fsum(
                value
                for timestamp, value in zip(
                    result.aligned.timestamp_local,
                    result.aligned.total_load_kwh,
                    strict=True,
                )
                if timestamp.month == month
            )
            assert total == pytest.approx(target, abs=1e-6)
        assert result.validation.annual_energy_conserved
        assert result.validation.local_monthly_energy_conserved


def test_naive_utc_calendar_year_is_rejected(paired_fixture):
    config, _, _, source, _ = paired_fixture
    reconstruction = reconstruct_hourly_load(
        source,
        variant="published_monthly_rows",
        shape="flat_within_month",
        reference_year=2025,
        timezone_offset=RODINA_TIMEZONE_OFFSET,
    )
    naive_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    naive_weather = _weather_dataset(naive_start, naive_start.replace(year=2026))
    with pytest.raises(RodinaPairingError, match="matching the Rodina local year"):
        pair_reconstructed_load_with_weather(reconstruction, naive_weather, config)


def test_pairing_preserves_separate_weather_and_load_provenance(paired_fixture):
    config, interval, _, _, results = paired_fixture
    provenance = results[1].aligned.provenance
    assert provenance.weather.underlying_model == "ERA5"
    assert provenance.weather.cache_key == "offline-rodina-2025"
    assert provenance.load.source_type is LoadSourceType.LITERATURE_DERIVED
    assert provenance.load.hourly_values_measured is False
    assert provenance.load.hourly_values_reconstructed is True
    assert provenance.load.reference_year == 2025
    assert provenance.load.reference_year_is_source_period is False
    assert provenance.critical_load_available is False
    assert provenance.grid_outage_schedule_used is False
    assert provenance.coordinate_anchor == config.coordinate_anchor
    assert provenance.utc_start == interval.utc_start


def test_correlations_match_deterministic_fixture_calculation(paired_fixture):
    _, _, _, _, results = paired_fixture
    result = results[1]
    summary = result.summary
    assert summary.hourly_load_solar_resource_correlation == pytest.approx(
        correlation(
            result.aligned.total_load_kwh,
            result.aligned.solar_irradiance_w_m2,
        )
    )
    assert summary.hourly_load_wind_speed_correlation == pytest.approx(
        correlation(result.aligned.total_load_kwh, result.aligned.wind_speed_m_s)
    )
    assert summary.monthly_load_solar_irradiation_correlation == pytest.approx(
        correlation(
            [row.monthly_load_kwh for row in result.monthly],
            [row.horizontal_irradiation_kwh_m2 for row in result.monthly],
        )
    )
    assert "not generation" in summary.correlation_definition


def test_pairing_is_reproducible(paired_fixture):
    config, _, weather, source, results = paired_fixture
    reconstruction = reconstruct_hourly_load(
        source,
        variant="published_monthly_rows",
        shape="residential_like",
        reference_year=2025,
        timezone_offset=RODINA_TIMEZONE_OFFSET,
    )
    repeated = pair_reconstructed_load_with_weather(reconstruction, weather, config)
    assert repeated == results[1]


def test_outputs_include_aligned_rows_dual_provenance_and_plots(
    paired_fixture, tmp_path
):
    config, interval, weather, source, results = paired_fixture
    analysis = analyze_full_year(
        weather,
        interval.utc_start,
        interval.utc_end,
        calendar_timezone=timezone(timedelta(hours=5)),
    )
    output = write_paired_analysis(
        config=config,
        interval=interval,
        weather=weather,
        weather_analysis=analysis,
        results=results,
        integrity=validate_source_integrity(source),
        output_directory=tmp_path,
    )
    plot_paths = create_paired_plots(results, output / "plots")
    with (output / "flat_within_month" / "aligned_hourly.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    provenance = json.loads(
        (output / "residential_like" / "provenance.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(rows) == 8760
    assert rows[0]["timestamp_utc"].startswith("2024-12-31T19:00:00")
    assert rows[0]["timestamp_local"].startswith("2025-01-01T00:00:00")
    assert set(provenance) == {"weather", "load", "pairing"}
    assert (output / "weather" / "weather_summary.json").is_file()
    assert (output / "comparison.md").is_file()
    assert len(plot_paths) == 4
    assert all(path.stat().st_size > 0 for path in plot_paths)


class FrozenTransport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(self, url: str, timeout_seconds: float) -> bytes:
        self.calls += 1
        return self.payload


def _full_api_payload() -> bytes:
    start = datetime(2024, 12, 31, tzinfo=timezone.utc)
    hours = 8784
    timestamps = [start + timedelta(hours=index) for index in range(hours)]
    payload = {
        "latitude": 51.25,
        "longitude": 70.5,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "\u00b0C",
            "wind_speed_10m": "m/s",
            "shortwave_radiation": "W/m\u00b2",
        },
        "hourly": {
            "time": [timestamp.strftime("%Y-%m-%dT%H:%M") for timestamp in timestamps],
            "temperature_2m": [float((index % 30) - 15) for index in range(hours)],
            "wind_speed_10m": [3.0 + (index % 24) / 24 for index in range(hours)],
            "shortwave_radiation": [
                max(0.0, 600 * math.sin(math.pi * ((index % 24) - 6) / 12))
                for index in range(hours)
            ],
        },
    }
    return json.dumps(payload).encode()


def test_cached_full_rodina_workflow_is_offline_and_reproducible(tmp_path):
    transport = FrozenTransport(_full_api_payload())
    provider = OpenMeteoHistoricalWeatherProvider(
        cache_root=tmp_path / "cache", transport=transport
    )
    interval = local_year_interval(2025, RODINA_TIMEZONE_OFFSET)
    config = load_rodina_site_config()
    first = provider.get_hourly_weather(
        config.site, interval.utc_start, interval.utc_end
    )
    second = provider.get_hourly_weather(
        config.site, interval.utc_start, interval.utc_end
    )
    assert first.provenance.cache_status == "MISS"
    assert second.provenance.cache_status == "HIT"
    assert transport.calls == 1

    source_directory = Path("data/benchmarks/rodina").resolve()
    first_run = analyze_rodina_paired(
        provider=provider,
        source_directory=source_directory,
        output_directory=tmp_path / "output",
        create_plots=False,
    )
    first_summary = (
        tmp_path / "output" / "residential_like" / "summary.json"
    ).read_bytes()
    second_run = analyze_rodina_paired(
        provider=provider,
        source_directory=source_directory,
        output_directory=tmp_path / "output",
        create_plots=False,
    )
    second_summary = (
        tmp_path / "output" / "residential_like" / "summary.json"
    ).read_bytes()
    assert transport.calls == 1
    assert first_run.weather.provenance.cache_status == "HIT"
    assert second_run.weather.provenance.cache_status == "HIT"
    assert first_run.paired_results == second_run.paired_results
    assert first_summary == second_summary
