"""Demand construction and strict CSV ingestion for planning scenarios."""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timedelta

from steppegrid.benchmarks.phase9 import load_phase9_loads, load_phase9_weather
from steppegrid.benchmarks.reconstruction import parse_fixed_utc_offset
from steppegrid.load.synthetic import synthetic_shape_multiplier
from steppegrid.planning.models import (
    DemandConfidence,
    DemandSourceType,
    PlanningDemand,
)

UPLOAD_COLUMNS = ("timestamp", "demand_kwh")


class PlanningDemandError(ValueError):
    """Raised when planning-demand inputs are incomplete or invalid."""


def _year_timestamps(reference_year: int, timezone_offset: str) -> list[datetime]:
    tz = parse_fixed_utc_offset(timezone_offset)
    start = datetime(reference_year, 1, 1, tzinfo=tz)
    end = datetime(reference_year + 1, 1, 1, tzinfo=tz)
    hours = int((end - start).total_seconds() / 3600)
    return [start + timedelta(hours=index) for index in range(hours)]


def _shape_weights(
    timestamps: list[datetime], shape: str, shape_timezone_offset: str | None = None
) -> list[float]:
    if shape == "flat_within_month":
        return [1.0] * len(timestamps)
    if shape not in ("residential_like", "community_facility_like"):
        raise PlanningDemandError(f"unsupported planning profile shape: {shape}")
    tz = parse_fixed_utc_offset(shape_timezone_offset) if shape_timezone_offset else None
    return [
        synthetic_shape_multiplier(shape, timestamp.astimezone(tz).hour if tz else timestamp.hour)
        for timestamp in timestamps
    ]


def estimated_annual_demand(
    annual_kwh: float,
    *,
    reference_year: int,
    timezone_offset: str,
    shape: str,
    source_type: DemandSourceType,
    confidence: DemandConfidence,
    method: str,
    shape_timezone_offset: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    source_year: int | None = None,
) -> PlanningDemand:
    if not math.isfinite(annual_kwh) or annual_kwh <= 0:
        raise PlanningDemandError("annual demand must be finite and positive")
    timestamps = _year_timestamps(reference_year, timezone_offset)
    weights = _shape_weights(timestamps, shape, shape_timezone_offset)
    factor = annual_kwh / math.fsum(weights)
    values = [weight * factor for weight in weights]
    values[-1] += annual_kwh - math.fsum(values)
    return PlanningDemand(
        timestamps=tuple(timestamps), demand_kwh=tuple(values), source_type=source_type,
        confidence=confidence, method=method, source_name=source_name,
        source_url=source_url, source_year=source_year,
    )


def estimated_monthly_demand(
    monthly_kwh: tuple[float, ...],
    *,
    reference_year: int,
    timezone_offset: str,
    shape: str,
    source_type: DemandSourceType,
    confidence: DemandConfidence,
    method: str,
    shape_timezone_offset: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    source_year: int | None = None,
) -> PlanningDemand:
    if len(monthly_kwh) != 12:
        raise PlanningDemandError("monthly demand requires exactly 12 totals")
    if any(not math.isfinite(value) or value < 0 for value in monthly_kwh):
        raise PlanningDemandError("monthly totals must be finite and non-negative")
    timestamps = _year_timestamps(reference_year, timezone_offset)
    values = [0.0] * len(timestamps)
    for month, target in enumerate(monthly_kwh, start=1):
        indices = [index for index, timestamp in enumerate(timestamps) if timestamp.month == month]
        weights = _shape_weights(
            [timestamps[index] for index in indices], shape, shape_timezone_offset
        )
        if target == 0:
            continue
        factor = target / math.fsum(weights)
        for index, weight in zip(indices, weights, strict=True):
            values[index] = weight * factor
        values[indices[-1]] += target - math.fsum(values[index] for index in indices)
    return PlanningDemand(
        timestamps=tuple(timestamps), demand_kwh=tuple(values), source_type=source_type,
        confidence=confidence, method=method, source_name=source_name,
        source_url=source_url, source_year=source_year,
    )


def rodina_benchmark_demand(shape: str = "community_facility_like") -> PlanningDemand:
    loads, _ = load_phase9_loads()
    if shape not in loads:
        raise PlanningDemandError(f"unsupported Rodina benchmark shape: {shape}")
    weather = load_phase9_weather()
    return PlanningDemand(
        timestamps=tuple(weather.series.timestamps),
        demand_kwh=tuple(loads[shape]),
        source_type=DemandSourceType.SOURCE_RECONSTRUCTED,
        confidence=DemandConfidence.STRONG_SOURCE_RECONSTRUCTION,
        method=(
            "Phase 9 Rodina literature monthly-row reconstruction with the selected "
            f"deterministic {shape} hourly shape"
        ),
        source_name="Rodina Phase 9 literature-derived benchmark",
        source_url="https://doi.org/10.1051/e3sconf/202340101052",
        source_year=2023,
    )


def parse_hourly_demand_csv(
    payload: bytes | str,
    *,
    source_type: DemandSourceType = DemandSourceType.USER_PROVIDED,
    confidence: DemandConfidence = DemandConfidence.USER_PROVIDED_UNVERIFIED,
    method: str = "User-uploaded hourly demand CSV",
    source_name: str | None = None,
    source_year: int | None = None,
) -> PlanningDemand:
    try:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
    except UnicodeDecodeError as error:
        raise PlanningDemandError("hourly demand CSV must use UTF-8 encoding") from error
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != list(UPLOAD_COLUMNS):
        raise PlanningDemandError(
            "hourly demand CSV must have exactly: timestamp,demand_kwh"
        )
    timestamps: list[datetime] = []
    values: list[float] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise PlanningDemandError(
                f"invalid ISO-8601 timestamp on CSV line {line_number}"
            ) from error
        if timestamp.tzinfo is None:
            raise PlanningDemandError(
                f"timestamp on CSV line {line_number} must include a UTC offset"
            )
        try:
            value = float(row["demand_kwh"])
        except (TypeError, ValueError) as error:
            raise PlanningDemandError(
                f"invalid demand_kwh on CSV line {line_number}"
            ) from error
        if not math.isfinite(value) or value < 0:
            raise PlanningDemandError(
                f"demand_kwh on CSV line {line_number} must be finite and non-negative"
            )
        timestamps.append(timestamp)
        values.append(value)
    try:
        return PlanningDemand(
            timestamps=tuple(timestamps), demand_kwh=tuple(values),
            source_type=source_type, confidence=confidence, method=method,
            source_name=source_name, source_year=source_year,
        )
    except ValueError as error:
        raise PlanningDemandError(str(error)) from error


def demand_preview(demand: PlanningDemand) -> dict[str, object]:
    monthly = [
        math.fsum(
            value for timestamp, value in zip(demand.timestamps, demand.demand_kwh, strict=True)
            if timestamp.month == month
        )
        for month in range(1, 13)
    ]
    peak_index = max(range(len(demand.demand_kwh)), key=demand.demand_kwh.__getitem__)
    return {
        "hours": len(demand.timestamps),
        "annual_kwh": demand.annual_kwh,
        "mean_hourly_kwh": demand.annual_kwh / len(demand.demand_kwh),
        "peak_hourly_kwh": demand.demand_kwh[peak_index],
        "load_factor": (demand.annual_kwh / len(demand.demand_kwh)) / demand.demand_kwh[peak_index],
        "peak_timestamp": demand.timestamps[peak_index],
        "monthly_kwh": monthly,
        "source_type": demand.source_type.value,
        "confidence": demand.confidence.value,
        "method": demand.method,
        "sha256": demand.sha256,
    }
