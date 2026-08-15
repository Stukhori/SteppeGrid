from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from steppegrid.simulation.models import Location
from steppegrid.weather.csv_provider import CSVWeatherProvider, WeatherDataError


def _write_weather(path, rows):
    path.write_text(
        "timestamp,wind_speed_m_s,solar_irradiance_w_m2,temperature_c\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "field,value",
    [("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1)],
)
def test_invalid_location_coordinates_are_rejected(field, value):
    values = {"latitude": 50, "longitude": 70, field: value}
    with pytest.raises(ValidationError):
        Location(**values)


def test_csv_weather_rejects_duplicate_timestamp(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, [
        "2026-01-01T00:00:00+00:00,5,0,-10",
        "2026-01-01T00:00:00+00:00,6,0,-11",
    ])
    provider = CSVWeatherProvider(path)
    with pytest.raises(WeatherDataError, match="duplicate"):
        provider.get_hourly_weather(
            Location(latitude=50, longitude=70),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        )


def test_csv_weather_rejects_missing_hour(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, [
        "2026-01-01T00:00:00+00:00,5,0,-10",
        "2026-01-01T02:00:00+00:00,6,0,-11",
    ])
    with pytest.raises(WeatherDataError, match="missing or non-hourly"):
        CSVWeatherProvider(path).get_hourly_weather(
            Location(latitude=50, longitude=70),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
        )


def test_csv_weather_rejects_missing_value(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, ["2026-01-01T00:00:00+00:00,,0,-10"])
    with pytest.raises(WeatherDataError, match="missing weather value"):
        CSVWeatherProvider(path).get_hourly_weather(
            Location(latitude=50, longitude=70),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        )


def test_csv_weather_rejects_negative_wind(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, ["2026-01-01T00:00:00+00:00,-1,0,-10"])
    with pytest.raises(WeatherDataError, match="cannot be negative"):
        CSVWeatherProvider(path).get_hourly_weather(
            Location(latitude=50, longitude=70),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        )


def test_csv_weather_rejects_out_of_bounds_irradiance(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, ["2026-01-01T00:00:00+00:00,1,2001,-10"])
    with pytest.raises(WeatherDataError, match="irradiance"):
        CSVWeatherProvider(path).get_hourly_weather(
            Location(latitude=50, longitude=70),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        )


def test_csv_weather_records_provenance(tmp_path):
    path = tmp_path / "weather.csv"
    _write_weather(path, ["2026-01-01T00:00:00+00:00,5,0,-10"])
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dataset = CSVWeatherProvider(path, source="laboratory fixture").get_hourly_weather(
        Location(latitude=50, longitude=70), start, start + timedelta(hours=1)
    )
    assert dataset.provenance.source == "laboratory fixture"
    assert dataset.provenance.latitude == 50
    assert dataset.provenance.processing_notes[0].startswith("No interpolation")
