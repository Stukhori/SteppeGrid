"""Cached Open-Meteo ERA5 historical reanalysis weather provider."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from steppegrid.simulation.models import (
    DataProvenance,
    Location,
    WeatherDataset,
    WeatherSeries,
)
from steppegrid.weather.csv_provider import WEATHER_COLUMNS, WeatherDataError

OPEN_METEO_ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_DOCUMENTATION = "https://open-meteo.com/en/docs/historical-weather-api"
PROVIDER_NAME = "Open-Meteo Historical Weather API"
MODEL_NAME = "ERA5"
MODEL_PARAMETER = "era5"
HOURLY_VARIABLES = ("temperature_2m", "wind_speed_10m", "shortwave_radiation")
GENERATION_VARIABLES = ("wind_speed_100m", "direct_normal_irradiance", "diffuse_radiation")
MINOR_NEGATIVE_RADIATION_FLOOR_W_M2 = -10.0
REQUESTED_VARIABLES = (*HOURLY_VARIABLES, *GENERATION_VARIABLES)
RADIATION_INTERVAL_CONVENTION = "preceding_hour_mean"
RADIATION_INTERVAL_DURATION_MINUTES = 60
TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}
EARTH_MEAN_RADIUS_KM = 6371.0088

HTTPTransport = Callable[[str, float], bytes]


class OpenMeteoError(WeatherDataError):
    """Raised for network, cache, or remote response failures."""


@dataclass(frozen=True)
class CachePaths:
    directory: Path
    raw: Path
    normalized: Path
    metadata: Path


def _great_circle_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    latitude_1, latitude_2 = math.radians(lat1), math.radians(lat2)
    delta_latitude = latitude_2 - latitude_1
    delta_longitude = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_1) * math.cos(latitude_2) * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * EARTH_MEAN_RADIUS_KM * math.asin(math.sqrt(a))


def _default_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "SteppeGrid/0.1 (research software)"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


class OpenMeteoHistoricalWeatherProvider:
    def __init__(
        self,
        *,
        cache_root: str | Path = "data/weather/cache",
        timeout_seconds: float = 30.0,
        maximum_attempts: int = 3,
        maximum_irradiance_w_m2: float = 2000.0,
        transport: HTTPTransport | None = None,
    ) -> None:
        if maximum_attempts < 1:
            raise ValueError("maximum_attempts must be at least one")
        self.cache_root = Path(cache_root)
        self.timeout_seconds = timeout_seconds
        self.maximum_attempts = maximum_attempts
        self.maximum_irradiance_w_m2 = maximum_irradiance_w_m2
        self.transport = transport or _default_transport

    def _request_parameters(
        self, location: Location, start: datetime, end: datetime
    ) -> dict[str, str | float]:
        inclusive_end = end - timedelta(hours=1)
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.date().isoformat(),
            "end_date": inclusive_end.date().isoformat(),
            "hourly": ",".join(REQUESTED_VARIABLES),
            "models": MODEL_PARAMETER,
            "wind_speed_unit": "ms",
            "temperature_unit": "celsius",
            "timezone": "UTC",
        }

    def _validate_period(self, start: datetime, end: datetime) -> None:
        if start.tzinfo is None or end.tzinfo is None:
            raise OpenMeteoError("Open-Meteo request datetimes must be timezone-aware UTC")
        if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
            raise OpenMeteoError("Open-Meteo request datetimes must use UTC")
        duration = end - start
        hours = int(duration.total_seconds() / 3600)
        if hours <= 0 or duration != timedelta(hours=hours):
            raise OpenMeteoError("Open-Meteo request period must contain positive whole hours")

    def cache_key(self, location: Location, start: datetime, end: datetime) -> str:
        definition = {
            "provider": "open_meteo",
            "model": MODEL_PARAMETER,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "requested_variables": list(REQUESTED_VARIABLES),
            "wind_speed_unit": "ms",
            "temperature_unit": "celsius",
            "timezone": "UTC",
        }
        encoded = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def cache_paths(self, location: Location, start: datetime, end: datetime) -> CachePaths:
        directory = self.cache_root / "open_meteo" / MODEL_PARAMETER / self.cache_key(
            location, start, end
        )
        return CachePaths(
            directory=directory,
            raw=directory / "raw.json",
            normalized=directory / "weather.csv",
            metadata=directory / "metadata.json",
        )

    def _download(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self.maximum_attempts + 1):
            try:
                return self.transport(url, self.timeout_seconds)
            except HTTPError as error:
                last_error = error
                if error.code not in TRANSIENT_HTTP_STATUS or attempt == self.maximum_attempts:
                    raise OpenMeteoError(
                        f"Open-Meteo request failed with HTTP {error.code}: {error.reason}"
                    ) from error
            except (URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt == self.maximum_attempts:
                    raise OpenMeteoError(
                        f"Open-Meteo request failed after {attempt} attempts: {error}"
                    ) from error
            time.sleep(0.25 * 2 ** (attempt - 1))
        raise OpenMeteoError(f"Open-Meteo request failed: {last_error}")

    def get_hourly_weather(
        self,
        location: Location,
        start: datetime,
        end: datetime,
        *,
        refresh: bool = False,
    ) -> WeatherDataset:
        self._validate_period(start, end)
        paths = self.cache_paths(location, start, end)
        cache_complete = paths.raw.is_file() and paths.normalized.is_file() and paths.metadata.is_file()
        if cache_complete and not refresh:
            raw_bytes = paths.raw.read_bytes()
            try:
                metadata = json.loads(paths.metadata.read_text(encoding="utf-8"))
                retrieved_at = datetime.fromisoformat(metadata["provenance"]["retrieved_at"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise OpenMeteoError(f"invalid cache metadata: {paths.metadata}") from error
            return self._normalize(
                raw_bytes, location, start, end, retrieved_at, paths, "HIT"
            )

        parameters = self._request_parameters(location, start, end)
        request_url = f"{OPEN_METEO_ARCHIVE_ENDPOINT}?{urlencode(parameters)}"
        raw_bytes = self._download(request_url)
        retrieved_at = datetime.now(timezone.utc)
        dataset = self._normalize(raw_bytes, location, start, end, retrieved_at, paths, "MISS")
        self._save_cache(paths, raw_bytes, dataset, parameters, request_url)
        return dataset

    def _normalize(
        self,
        raw_bytes: bytes,
        location: Location,
        start: datetime,
        end: datetime,
        retrieved_at: datetime,
        paths: CachePaths,
        cache_status: str,
    ) -> WeatherDataset:
        try:
            payload = json.loads(raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenMeteoError("Open-Meteo returned malformed JSON") from error
        if not isinstance(payload, dict):
            raise OpenMeteoError("Open-Meteo response root must be an object")
        hourly = payload.get("hourly")
        units = payload.get("hourly_units")
        if not isinstance(hourly, dict) or not isinstance(units, dict):
            raise OpenMeteoError("Open-Meteo response requires hourly and hourly_units objects")

        required_arrays = ("time", *HOURLY_VARIABLES)
        for variable in required_arrays:
            if variable not in hourly:
                raise OpenMeteoError(f"Open-Meteo response is missing hourly variable: {variable}")
            if not isinstance(hourly[variable], list):
                raise OpenMeteoError(f"Open-Meteo hourly variable must be an array: {variable}")
        lengths = {variable: len(hourly[variable]) for variable in required_arrays}
        if len(set(lengths.values())) != 1:
            raise OpenMeteoError(f"Open-Meteo hourly arrays have unequal lengths: {lengths}")
        expected_units = {
            "temperature_2m": "°C",
            "wind_speed_10m": "m/s",
            "shortwave_radiation": "W/m²",
        }
        for variable, expected_unit in expected_units.items():
            if units.get(variable) != expected_unit:
                raise OpenMeteoError(
                    f"unexpected unit for {variable}: {units.get(variable)!r}; expected {expected_unit!r}"
                )

        timestamps: list[datetime] = []
        for index, raw_timestamp in enumerate(hourly["time"]):
            if not isinstance(raw_timestamp, str):
                raise OpenMeteoError(f"invalid timestamp at hourly index {index}")
            try:
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError as error:
                raise OpenMeteoError(f"invalid timestamp: {raw_timestamp!r}") from error
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp.utcoffset() != timedelta(0):
                raise OpenMeteoError(f"non-UTC timestamp returned: {raw_timestamp}")
            timestamps.append(timestamp)
        if len(timestamps) != len(set(timestamps)):
            raise OpenMeteoError("Open-Meteo response contains duplicate timestamps")
        if timestamps != sorted(timestamps):
            raise OpenMeteoError("Open-Meteo timestamps are not chronological")

        has_generation_variables = all(variable in hourly for variable in GENERATION_VARIABLES)
        if any(variable in hourly for variable in GENERATION_VARIABLES) and not has_generation_variables:
            raise OpenMeteoError("Open-Meteo response contains only some Phase 8 generation variables")
        if has_generation_variables:
            for variable in GENERATION_VARIABLES:
                if not isinstance(hourly[variable], list) or len(hourly[variable]) != len(timestamps):
                    raise OpenMeteoError(f"invalid hourly generation variable: {variable}")
            if units.get("wind_speed_100m") != units.get("wind_speed_10m"):
                raise OpenMeteoError("unexpected unit for wind_speed_100m")
            for variable in ("direct_normal_irradiance", "diffuse_radiation"):
                if units.get(variable) != units.get("shortwave_radiation"):
                    raise OpenMeteoError(f"unexpected unit for {variable}")

        rows: dict[datetime, tuple[float, ...]] = {}
        radiation_floor_counts = {
            "direct_normal_irradiance": 0,
            "diffuse_radiation": 0,
        }
        for index, timestamp in enumerate(timestamps):
            values: list[float] = []
            for variable in HOURLY_VARIABLES:
                raw_value = hourly[variable][index]
                if raw_value is None:
                    raise OpenMeteoError(
                        f"missing value at {timestamp.isoformat()} for {variable}"
                    )
                if not isinstance(raw_value, (int, float)) or not math.isfinite(raw_value):
                    raise OpenMeteoError(
                        f"invalid value at {timestamp.isoformat()} for {variable}: {raw_value!r}"
                    )
                values.append(float(raw_value))
            temperature, wind, irradiance = values
            if wind < 0:
                raise OpenMeteoError(f"negative wind speed at {timestamp.isoformat()}")
            if irradiance < 0 or irradiance > self.maximum_irradiance_w_m2:
                raise OpenMeteoError(
                    f"irradiance outside 0-{self.maximum_irradiance_w_m2} W/m2 "
                    f"at {timestamp.isoformat()}"
                )
            rows[timestamp] = (wind, irradiance, temperature)
            if has_generation_variables:
                extra: list[float] = []
                for variable in GENERATION_VARIABLES:
                    raw_value = hourly[variable][index]
                    if not isinstance(raw_value, (int, float)) or not math.isfinite(raw_value):
                        raise OpenMeteoError(
                            f"invalid Phase 8 generation weather at {timestamp.isoformat()}"
                        )
                    value = float(raw_value)
                    if value < 0:
                        if (
                            variable in radiation_floor_counts
                            and value >= MINOR_NEGATIVE_RADIATION_FLOOR_W_M2
                        ):
                            radiation_floor_counts[variable] += 1
                            value = 0.0
                        else:
                            raise OpenMeteoError(
                                f"invalid Phase 8 generation weather at {timestamp.isoformat()}"
                            )
                    extra.append(value)
                rows[timestamp] += tuple(extra)

        expected_timestamps = [
            start + timedelta(hours=index)
            for index in range(int((end - start).total_seconds() / 3600))
        ]
        returned_in_period = [timestamp for timestamp in timestamps if start <= timestamp < end]
        if returned_in_period != expected_timestamps:
            if any(timestamp not in rows for timestamp in expected_timestamps):
                missing = next(
                    timestamp for timestamp in expected_timestamps if timestamp not in rows
                )
                raise OpenMeteoError(
                    f"Open-Meteo response is missing requested timestamp: {missing.isoformat()}"
                )
            unexpected = next(
                timestamp for timestamp in returned_in_period if timestamp not in expected_timestamps
            )
            raise OpenMeteoError(
                f"Open-Meteo response contains unexpected in-range timestamp: {unexpected.isoformat()}"
            )
        selected = [rows[timestamp] for timestamp in expected_timestamps]

        try:
            returned_latitude = float(payload["latitude"])
            returned_longitude = float(payload["longitude"])
        except (KeyError, TypeError, ValueError) as error:
            raise OpenMeteoError("Open-Meteo response is missing valid returned coordinates") from error
        if (
            not math.isfinite(returned_latitude)
            or not math.isfinite(returned_longitude)
            or not -90 <= returned_latitude <= 90
            or not -180 <= returned_longitude <= 180
        ):
            raise OpenMeteoError("Open-Meteo returned coordinates are invalid")
        timezone_name = payload.get("timezone")
        if timezone_name not in {"UTC", "GMT"} or payload.get("utc_offset_seconds") != 0:
            raise OpenMeteoError("Open-Meteo response did not preserve requested UTC timezone")

        series = WeatherSeries(
            timestamps=expected_timestamps,
            wind_speed_m_s=[row[0] for row in selected],
            solar_irradiance_w_m2=[row[1] for row in selected],
            temperature_c=[row[2] for row in selected],
            wind_speed_100m_m_s=[row[3] for row in selected] if has_generation_variables else None,
            direct_normal_irradiance_w_m2=[row[4] for row in selected] if has_generation_variables else None,
            diffuse_radiation_w_m2=[row[5] for row in selected] if has_generation_variables else None,
        )
        provenance = DataProvenance(
            source=PROVIDER_NAME,
            provider=PROVIDER_NAME,
            underlying_model=MODEL_NAME,
            retrieved_at=retrieved_at,
            latitude=location.latitude,
            longitude=location.longitude,
            requested_latitude=location.latitude,
            requested_longitude=location.longitude,
            returned_latitude=returned_latitude,
            returned_longitude=returned_longitude,
            requested_start_date=start.date(),
            requested_end_date=end.date(),
            start_time=start,
            end_time=end,
            timezone="UTC",
            temporal_resolution="hourly",
            spatial_resolution="0.25 degrees (approximately 25 km; ERA5 dataset level)",
            variables_requested=list(REQUESTED_VARIABLES if has_generation_variables else HOURLY_VARIABLES),
            original_units={
                variable: units[variable]
                for variable in (REQUESTED_VARIABLES if has_generation_variables else HOURLY_VARIABLES)
            },
            normalized_units={
                "wind_speed_m_s": "m/s",
                "solar_irradiance_w_m2": "W/m2",
                "temperature_c": "degC",
                "wind_speed_100m_m_s": "m/s",
                "direct_normal_irradiance_w_m2": "W/m2",
                "diffuse_radiation_w_m2": "W/m2",
            },
            processing_notes=[
                "Selected the requested half-open UTC interval from inclusive API date output.",
                "Renamed source variables; no unit conversion or interpolation.",
                "Shortwave radiation is the mean over the preceding hour.",
                "The record timestamp is the end of that radiation averaging interval; POA geometry should use its midpoint without changing record alignment.",
                "ERA5 100 m wind is used as the generation reference when present.",
                "Data are ERA5 reanalysis associated with a grid cell, not a local station measurement.",
            ] + [
                f"Floored {count} small negative {variable} ERA5 value(s) to 0 W/m2; "
                f"accepted floor is {MINOR_NEGATIVE_RADIATION_FLOOR_W_M2:g} W/m2."
                for variable, count in radiation_floor_counts.items() if count
            ],
            coordinate_distance_km=_great_circle_distance_km(
                location.latitude, location.longitude, returned_latitude, returned_longitude
            ),
            cache_key=self.cache_key(location, start, end),
            cache_status=cache_status,
            raw_response_path=paths.raw.as_posix(),
            normalized_data_path=paths.normalized.as_posix(),
            metadata_path=paths.metadata.as_posix(),
            source_documentation=OPEN_METEO_DOCUMENTATION,
        )
        return WeatherDataset(series=series, provenance=provenance)

    def _save_cache(
        self,
        paths: CachePaths,
        raw_bytes: bytes,
        dataset: WeatherDataset,
        parameters: dict[str, str | float],
        request_url: str,
    ) -> None:
        paths.directory.mkdir(parents=True, exist_ok=True)
        raw_temporary = paths.raw.with_suffix(".json.tmp")
        raw_temporary.write_bytes(raw_bytes)
        raw_temporary.replace(paths.raw)

        normalized_temporary = paths.normalized.with_suffix(".csv.tmp")
        with normalized_temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(WEATHER_COLUMNS)
            for index, timestamp in enumerate(dataset.series.timestamps):
                writer.writerow(
                    [
                        timestamp.isoformat(),
                        dataset.series.wind_speed_m_s[index],
                        dataset.series.solar_irradiance_w_m2[index],
                        dataset.series.temperature_c[index],
                    ]
                )
        normalized_temporary.replace(paths.normalized)

        metadata = {
            "provider": PROVIDER_NAME,
            "model": MODEL_NAME,
            "endpoint": OPEN_METEO_ARCHIVE_ENDPOINT,
            "request_url": request_url,
            "request_parameters": parameters,
            "provenance": dataset.provenance.model_dump(mode="json"),
        }
        metadata_temporary = paths.metadata.with_suffix(".json.tmp")
        metadata_temporary.write_text(
            json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        metadata_temporary.replace(paths.metadata)
