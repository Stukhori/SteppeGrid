from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError

import pytest
from pydantic import ValidationError

from steppegrid.simulation.models import Location
from steppegrid.scenario import (
    SimulationScenario,
    TurbineSourceConfig,
    WeatherSourceConfig,
    resolve_scenario,
)
from steppegrid.simulation.models import BatteryConfig, SolarArrayConfig
from steppegrid.simulation.simulator import simulate
from steppegrid.weather.inspection import summarize_weather
from steppegrid.weather.open_meteo import (
    HOURLY_VARIABLES,
    OpenMeteoError,
    OpenMeteoHistoricalWeatherProvider,
)

FIXTURE_PATH = Path("tests/fixtures/open_meteo_era5_response.json")
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2025, 1, 1, 3, tzinfo=timezone.utc)
LOCATION = Location(latitude=50.0, longitude=51.0)


class FrozenTransport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0
        self.urls: list[str] = []

    def __call__(self, url: str, timeout_seconds: float) -> bytes:
        self.calls += 1
        self.urls.append(url)
        assert timeout_seconds > 0
        return self.payload


def _payload_for(start: datetime, hours: int) -> dict:
    timestamps = [
        (start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M")
        for index in range(hours)
    ]
    return {
        "latitude": 50.0,
        "longitude": 51.0,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "wind_speed_10m": "m/s",
            "shortwave_radiation": "W/m²",
        },
        "hourly": {
            "time": timestamps,
            "temperature_2m": [-5.0] * hours,
            "wind_speed_10m": [4.0] * hours,
            "shortwave_radiation": [0.0] * hours,
        },
    }


def _provider(tmp_path, payload: dict | bytes):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    transport = FrozenTransport(raw)
    provider = OpenMeteoHistoricalWeatherProvider(
        cache_root=tmp_path / "cache", transport=transport
    )
    return provider, transport


def test_happy_path_normalizes_and_caches_exact_raw_response(tmp_path):
    raw = FIXTURE_PATH.read_bytes()
    provider, transport = _provider(tmp_path, raw)
    dataset = provider.get_hourly_weather(LOCATION, START, END)
    paths = provider.cache_paths(LOCATION, START, END)

    assert transport.calls == 1
    assert dataset.series.wind_speed_m_s == [5.0, 5.2, 5.4]
    assert dataset.series.temperature_c == [-10.0, -10.5, -11.0]
    assert paths.raw.read_bytes() == raw
    assert paths.normalized.is_file()
    assert paths.metadata.is_file()
    assert "models=era5" in transport.urls[0]
    assert "wind_speed_unit=ms" in transport.urls[0]


def test_second_identical_request_is_cache_hit_without_network(tmp_path):
    provider, transport = _provider(tmp_path, FIXTURE_PATH.read_bytes())
    first = provider.get_hourly_weather(LOCATION, START, END)
    second = provider.get_hourly_weather(LOCATION, START, END)
    assert transport.calls == 1
    assert first.series == second.series
    assert second.provenance.cache_status == "HIT"


def test_refresh_performs_new_request(tmp_path):
    provider, transport = _provider(tmp_path, FIXTURE_PATH.read_bytes())
    provider.get_hourly_weather(LOCATION, START, END)
    provider.get_hourly_weather(LOCATION, START, END, refresh=True)
    assert transport.calls == 2


def test_offline_cache_remains_usable(tmp_path):
    provider, _ = _provider(tmp_path, FIXTURE_PATH.read_bytes())
    provider.get_hourly_weather(LOCATION, START, END)

    def offline(url: str, timeout_seconds: float) -> bytes:
        raise URLError("offline")

    offline_provider = OpenMeteoHistoricalWeatherProvider(
        cache_root=tmp_path / "cache", transport=offline
    )
    dataset = offline_provider.get_hourly_weather(LOCATION, START, END)
    assert dataset.provenance.cache_status == "HIT"
    assert len(dataset.series.timestamps) == 3


def test_missing_variable_fails_clearly(tmp_path):
    payload = _payload_for(START, 3)
    del payload["hourly"]["wind_speed_10m"]
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match="missing hourly variable: wind_speed_10m"):
        provider.get_hourly_weather(LOCATION, START, END)


@pytest.mark.parametrize("variable", HOURLY_VARIABLES)
def test_null_value_names_timestamp_and_variable(tmp_path, variable):
    payload = _payload_for(START, 3)
    payload["hourly"][variable][1] = None
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match=rf"2025-01-01T01:00:00\+00:00 for {variable}"):
        provider.get_hourly_weather(LOCATION, START, END)


def test_duplicate_timestamp_fails(tmp_path):
    payload = _payload_for(START, 3)
    payload["hourly"]["time"][2] = payload["hourly"]["time"][1]
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match="duplicate timestamps"):
        provider.get_hourly_weather(LOCATION, START, END)


def test_unequal_array_lengths_fail(tmp_path):
    payload = _payload_for(START, 3)
    payload["hourly"]["temperature_2m"].pop()
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match="unequal lengths"):
        provider.get_hourly_weather(LOCATION, START, END)


@pytest.mark.parametrize(
    "variable,value,message",
    [
        ("wind_speed_10m", -1.0, "negative wind speed"),
        ("shortwave_radiation", -1.0, "irradiance outside"),
        ("temperature_2m", float("nan"), "invalid value"),
    ],
)
def test_invalid_remote_values_fail(tmp_path, variable, value, message):
    payload = _payload_for(START, 3)
    payload["hourly"][variable][0] = value
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match=message):
        provider.get_hourly_weather(LOCATION, START, END)


def test_unexpected_in_range_timestamp_fails(tmp_path):
    payload = _payload_for(START, 3)
    for variable in ("time", *HOURLY_VARIABLES):
        if variable == "time":
            payload["hourly"][variable].append("2025-01-01T01:30")
        else:
            payload["hourly"][variable].append(payload["hourly"][variable][-1])
    order = [0, 1, 3, 2]
    for variable in ("time", *HOURLY_VARIABLES):
        payload["hourly"][variable] = [payload["hourly"][variable][index] for index in order]
    provider, _ = _provider(tmp_path, payload)
    with pytest.raises(OpenMeteoError, match="unexpected in-range timestamp"):
        provider.get_hourly_weather(LOCATION, START, END)


def test_location_validation_rejects_invalid_coordinates():
    with pytest.raises(ValidationError):
        Location(latitude=91, longitude=51)


def test_leap_day_is_processed_as_24_hourly_records(tmp_path):
    leap_start = datetime(2024, 2, 29, tzinfo=timezone.utc)
    leap_end = datetime(2024, 3, 1, tzinfo=timezone.utc)
    provider, _ = _provider(tmp_path, _payload_for(leap_start, 24))
    dataset = provider.get_hourly_weather(LOCATION, leap_start, leap_end)
    assert len(dataset.series.timestamps) == 24
    assert all(timestamp.date().isoformat() == "2024-02-29" for timestamp in dataset.series.timestamps)


def test_provenance_survives_normalization_and_metadata(tmp_path):
    provider, _ = _provider(tmp_path, FIXTURE_PATH.read_bytes())
    dataset = provider.get_hourly_weather(LOCATION, START, END)
    provenance = dataset.provenance
    assert provenance.provider == "Open-Meteo Historical Weather API"
    assert provenance.underlying_model == "ERA5"
    assert provenance.requested_latitude == 50.0
    assert provenance.returned_longitude == 51.0
    assert provenance.requested_end_date.isoformat() == "2025-01-01"
    assert provenance.timezone == "UTC"
    assert provenance.temporal_resolution == "hourly"
    assert provenance.variables_requested == list(HOURLY_VARIABLES)
    assert provenance.original_units["shortwave_radiation"] == "W/m²"
    metadata = json.loads(Path(provenance.metadata_path).read_text(encoding="utf-8"))
    assert metadata["request_parameters"]["models"] == "era5"
    assert metadata["endpoint"].endswith("/v1/archive")


def test_weather_inspection_uses_hourly_irradiance_as_energy(tmp_path):
    payload = _payload_for(START, 3)
    payload["hourly"]["shortwave_radiation"] = [0.0, 500.0, 1000.0]
    provider, _ = _provider(tmp_path, payload)
    summary = summarize_weather(provider.get_hourly_weather(LOCATION, START, END))
    assert summary.mean_solar_irradiance_w_m2 == pytest.approx(500)
    assert summary.horizontal_irradiation_kwh_m2 == pytest.approx(1.5)
    assert summary.missing_records == 0


def test_open_meteo_scenario_uses_cached_weather_without_network(tmp_path):
    cache_root = tmp_path / "cache"
    provider, _ = _provider(tmp_path, FIXTURE_PATH.read_bytes())
    provider.get_hourly_weather(LOCATION, START, END)

    scenario = SimulationScenario(
        location=LOCATION,
        start_time=START,
        end_time=END,
        weather=WeatherSourceConfig(
            provider="open-meteo", cache_directory=str(cache_root)
        ),
        load_profile_kwh=[1.0, 1.0, 1.0],
        solar=SolarArrayConfig(dc_capacity_kw=0),
        wind=TurbineSourceConfig(
            curve_csv="data/turbine_curves/synthetic_example.csv",
            name="synthetic test curve",
        ),
        battery=BatteryConfig(
            capacity_kwh=0,
            initial_soc_kwh=0,
            maximum_charge_kw=0,
            maximum_discharge_kw=0,
            charging_efficiency=1,
            discharging_efficiency=1,
        ),
    )
    resolved = resolve_scenario(scenario)
    result = simulate(resolved.simulation_input)
    assert resolved.weather_provenance.cache_status == "HIT"
    assert result.metrics.total_demand_kwh == pytest.approx(3)
