"""Strict CSV weather provider with explicit provenance."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from steppegrid.simulation.models import (
    DataProvenance,
    Location,
    WeatherDataset,
    WeatherSeries,
)

WEATHER_COLUMNS = (
    "timestamp",
    "wind_speed_m_s",
    "solar_irradiance_w_m2",
    "temperature_c",
)


class WeatherDataError(ValueError):
    """Raised when weather source data is missing, malformed, or non-hourly."""


def _parse_timestamp(raw: str, row_number: int) -> datetime:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise WeatherDataError(f"row {row_number}: invalid ISO 8601 timestamp {raw!r}") from error


class CSVWeatherProvider:
    def __init__(
        self,
        path: str | Path,
        *,
        source: str | None = None,
        retrieved_at: datetime | None = None,
        maximum_irradiance_w_m2: float = 2000.0,
        processing_notes: list[str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.source = source or f"CSV file: {self.path.name}"
        self.retrieved_at = retrieved_at
        self.maximum_irradiance_w_m2 = maximum_irradiance_w_m2
        self.processing_notes = processing_notes or []

    def get_hourly_weather(
        self, location: Location, start: datetime, end: datetime
    ) -> WeatherDataset:
        if end <= start:
            raise WeatherDataError("weather end must be later than start")
        if not self.path.is_file():
            raise WeatherDataError(f"weather CSV does not exist: {self.path}")

        records: list[tuple[datetime, float, float, float]] = []
        with self.path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(WEATHER_COLUMNS):
                raise WeatherDataError(
                    "weather CSV columns must be exactly: " + ",".join(WEATHER_COLUMNS)
                )
            for row_number, row in enumerate(reader, start=2):
                if any(row[column] is None or not row[column].strip() for column in WEATHER_COLUMNS):
                    raise WeatherDataError(f"row {row_number}: missing weather value")
                timestamp = _parse_timestamp(row["timestamp"], row_number)
                try:
                    wind = float(row["wind_speed_m_s"])
                    irradiance = float(row["solar_irradiance_w_m2"])
                    temperature = float(row["temperature_c"])
                except ValueError as error:
                    raise WeatherDataError(f"row {row_number}: invalid numeric value") from error
                if wind < 0:
                    raise WeatherDataError(f"row {row_number}: wind speed cannot be negative")
                if not 0 <= irradiance <= self.maximum_irradiance_w_m2:
                    raise WeatherDataError(
                        f"row {row_number}: irradiance must be between 0 and "
                        f"{self.maximum_irradiance_w_m2} W/m2"
                    )
                records.append((timestamp, wind, irradiance, temperature))

        timestamps = [record[0] for record in records]
        if len(timestamps) != len(set(timestamps)):
            raise WeatherDataError("weather CSV contains duplicate timestamps")
        if timestamps != sorted(timestamps):
            raise WeatherDataError("weather CSV timestamps must be chronological")
        for previous, current in zip(timestamps, timestamps[1:], strict=False):
            if current - previous != timedelta(hours=1):
                raise WeatherDataError(
                    f"weather CSV has a missing or non-hourly interval after {previous.isoformat()}"
                )

        selected = [record for record in records if start <= record[0] < end]
        expected_hours = int((end - start).total_seconds() / 3600)
        if end - start != timedelta(hours=expected_hours):
            raise WeatherDataError("requested weather period must contain whole hours")
        expected_timestamps = [start + timedelta(hours=index) for index in range(expected_hours)]
        if [record[0] for record in selected] != expected_timestamps:
            raise WeatherDataError("CSV does not contain every requested hourly timestamp")

        series = WeatherSeries(
            timestamps=[record[0] for record in selected],
            wind_speed_m_s=[record[1] for record in selected],
            solar_irradiance_w_m2=[record[2] for record in selected],
            temperature_c=[record[3] for record in selected],
        )
        provenance = DataProvenance(
            source=self.source,
            retrieved_at=self.retrieved_at,
            latitude=location.latitude,
            longitude=location.longitude,
            start_time=start,
            end_time=end,
            original_units={
                "wind_speed": "m/s",
                "solar_irradiance": "W/m2",
                "temperature": "degC",
            },
            normalized_units={
                "wind_speed_m_s": "m/s",
                "solar_irradiance_w_m2": "W/m2",
                "temperature_c": "degC",
            },
            processing_notes=["No interpolation or unit conversion performed.", *self.processing_notes],
        )
        return WeatherDataset(series=series, provenance=provenance)
