"""Strict CSV provider for user-supplied hourly electricity demand."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta
from pathlib import Path

from steppegrid.load.scaling import scale_load_dataset
from steppegrid.simulation.models import (
    LoadDataQuality,
    LoadDataset,
    LoadProvenance,
    LoadSourceType,
    Location,
)

REQUIRED_COLUMNS = ("timestamp", "total_load_kwh")
CRITICAL_COLUMN = "critical_load_kwh"


class LoadDataError(ValueError):
    """Raised when load data is missing, malformed, or not strictly hourly."""


def _parse_timestamp(raw: str, row_number: int) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise LoadDataError(
            f"row {row_number}: invalid ISO 8601 timestamp {raw!r}"
        ) from error
    if value.tzinfo is None or value.utcoffset() is None:
        raise LoadDataError(f"row {row_number}: timestamp must include a UTC offset")
    return value


def _parse_energy(raw: str, column: str, row_number: int) -> float:
    try:
        value = float(raw)
    except ValueError as error:
        raise LoadDataError(f"row {row_number}: invalid {column} value") from error
    if not math.isfinite(value) or value < 0:
        raise LoadDataError(f"row {row_number}: {column} must be finite and non-negative")
    return value


class CSVLoadProvider:
    def __init__(
        self,
        path: str | Path,
        *,
        source: str | None = None,
        source_type: LoadSourceType = LoadSourceType.USER_SUPPLIED_CSV,
        data_quality: LoadDataQuality = LoadDataQuality.UNSPECIFIED,
        retrieved_at: datetime | None = None,
        location: Location | None = None,
        processing_steps: list[str] | None = None,
        scale_factor: float | None = None,
        target_annual_kwh: float | None = None,
        critical_fraction: float | None = None,
    ) -> None:
        if critical_fraction is not None and not 0 <= critical_fraction <= 1:
            raise ValueError("critical_fraction must be between 0 and 1")
        self.path = Path(path)
        self.source = source or f"User-supplied CSV: {self.path.name}"
        self.source_type = source_type
        self.data_quality = data_quality
        self.retrieved_at = retrieved_at
        self.location = location
        self.processing_steps = processing_steps or []
        self.scale_factor = scale_factor
        self.target_annual_kwh = target_annual_kwh
        self.critical_fraction = critical_fraction

    def read(self) -> LoadDataset:
        if not self.path.is_file():
            raise LoadDataError(f"load CSV does not exist: {self.path}")
        records: list[tuple[datetime, float, float | None]] = []
        with self.path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            allowed = [list(REQUIRED_COLUMNS), [*REQUIRED_COLUMNS, CRITICAL_COLUMN]]
            if reader.fieldnames not in allowed:
                raise LoadDataError(
                    "load CSV columns must be exactly timestamp,total_load_kwh "
                    "with optional critical_load_kwh as the final column"
                )
            has_critical = CRITICAL_COLUMN in reader.fieldnames
            for row_number, row in enumerate(reader, start=2):
                columns = [*REQUIRED_COLUMNS, *([CRITICAL_COLUMN] if has_critical else [])]
                if any(row[column] is None or not row[column].strip() for column in columns):
                    raise LoadDataError(f"row {row_number}: missing load value")
                timestamp = _parse_timestamp(row["timestamp"], row_number)
                total = _parse_energy(row["total_load_kwh"], "total_load_kwh", row_number)
                critical = (
                    _parse_energy(row[CRITICAL_COLUMN], CRITICAL_COLUMN, row_number)
                    if has_critical
                    else None
                )
                if critical is not None and critical > total:
                    raise LoadDataError(
                        f"row {row_number}: critical_load_kwh cannot exceed total_load_kwh"
                    )
                records.append((timestamp, total, critical))
        if not records:
            raise LoadDataError("load CSV contains no data rows")

        timestamps = [record[0] for record in records]
        offsets = [timestamp.utcoffset() for timestamp in timestamps]
        if len(set(offsets)) != 1:
            raise LoadDataError("load CSV timestamps must use one consistent UTC offset")
        if len(timestamps) != len(set(timestamps)):
            raise LoadDataError("load CSV contains duplicate timestamps")
        if timestamps != sorted(timestamps):
            raise LoadDataError("load CSV timestamps must be chronological")
        for previous, current in zip(timestamps, timestamps[1:], strict=False):
            if current - previous != timedelta(hours=1):
                raise LoadDataError(
                    f"load CSV has a missing or non-hourly interval after {previous.isoformat()}"
                )

        total = [record[1] for record in records]
        critical_values = (
            [record[2] for record in records]
            if records[0][2] is not None
            else None
        )
        if critical_values is not None and self.critical_fraction is not None:
            raise LoadDataError(
                "critical_fraction cannot be combined with explicit critical_load_kwh"
            )
        critical_method = None
        steps = ["Parsed without interpolation or timestamp resampling.", *self.processing_steps]
        if critical_values is None and self.critical_fraction is not None:
            critical_values = [value * self.critical_fraction for value in total]
            critical_method = (
                f"Assumed constant critical fraction {self.critical_fraction:g} of total load."
            )
            steps.append(critical_method)
        elif critical_values is not None:
            critical_method = "Read explicit hourly critical_load_kwh values from the CSV."

        dataset = LoadDataset(
            timestamps=timestamps,
            total_load_kwh=total,
            critical_load_kwh=critical_values,
            provenance=LoadProvenance(
                source=self.source,
                source_type=self.source_type,
                data_quality=self.data_quality,
                start_time=timestamps[0],
                end_time=timestamps[-1] + timedelta(hours=1),
                retrieved_or_created_at=self.retrieved_at,
                location=self.location,
                original_units={
                    "total_load_kwh": "kWh/hour",
                    **(
                        {"critical_load_kwh": "kWh/hour"}
                        if critical_values is not None
                        else {}
                    ),
                },
                normalized_units={
                    "total_load_kwh": "kWh/hour",
                    **(
                        {"critical_load_kwh": "kWh/hour"}
                        if critical_values is not None
                        else {}
                    ),
                },
                processing_steps=steps,
                critical_load_method=critical_method,
            ),
        )
        return scale_load_dataset(
            dataset,
            target_annual_kwh=self.target_annual_kwh,
            scale_factor=self.scale_factor,
        )

    def get_hourly_load(self, start: datetime, end: datetime) -> LoadDataset:
        if end <= start:
            raise LoadDataError("load end must be later than start")
        duration = end - start
        hours = int(duration.total_seconds() / 3600)
        if duration != timedelta(hours=hours):
            raise LoadDataError("requested load period must contain whole hours")
        dataset = self.read()
        indexes = [
            index
            for index, timestamp in enumerate(dataset.timestamps)
            if start <= timestamp < end
        ]
        expected = [start + timedelta(hours=index) for index in range(hours)]
        selected_timestamps = [dataset.timestamps[index] for index in indexes]
        if selected_timestamps != expected:
            raise LoadDataError("CSV does not contain every requested hourly timestamp")
        provenance = dataset.provenance.model_copy(
            update={"start_time": start, "end_time": end}
        )
        critical = (
            [dataset.critical_load_kwh[index] for index in indexes]
            if dataset.critical_load_kwh is not None
            else None
        )
        return LoadDataset(
            timestamps=selected_timestamps,
            total_load_kwh=[dataset.total_load_kwh[index] for index in indexes],
            critical_load_kwh=critical,
            provenance=provenance,
        )
