"""Deterministic hourly reconstruction from literature-derived monthly constraints."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from steppegrid.benchmarks.models import (
    MonthlyLoadDataset,
    MonthlyReconstructionValidation,
    ReconstructionResult,
    ReconstructedLoadSummary,
)
from steppegrid.load.synthetic import synthetic_shape_multiplier
from steppegrid.simulation.models import (
    LoadDataQuality,
    LoadDataset,
    LoadProvenance,
    LoadSourceType,
)

BenchmarkVariant = Literal["published_monthly_rows", "annual_total_normalized"]
ReconstructionShape = Literal[
    "flat_within_month", "residential_like", "community_facility_like"
]
VALID_VARIANTS = ("published_monthly_rows", "annual_total_normalized")
VALID_SHAPES = (
    "flat_within_month",
    "residential_like",
    "community_facility_like",
)
MONTHLY_ABSOLUTE_TOLERANCE_KWH = 1e-6


def parse_fixed_utc_offset(raw: str) -> timezone:
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", raw)
    if not match:
        raise ValueError("timezone offset must use +HH:MM or -HH:MM")
    hours, minutes = int(match.group(2)), int(match.group(3))
    if hours > 23 or minutes > 59:
        raise ValueError("timezone offset is outside the supported fixed-offset range")
    delta = timedelta(hours=hours, minutes=minutes)
    if match.group(1) == "-":
        delta = -delta
    return timezone(delta)


def monthly_targets(
    source: MonthlyLoadDataset, variant: BenchmarkVariant
) -> tuple[list[float], float]:
    if variant not in VALID_VARIANTS:
        raise ValueError(f"unsupported benchmark variant: {variant}")
    published_rows = [float(row.load_kwh) for row in source.rows]
    if variant == "published_monthly_rows":
        return published_rows, 1.0
    factor = source.provenance.published_annual_load_kwh / math.fsum(published_rows)
    return [value * factor for value in published_rows], factor


def _month_bounds(year: int, month: int, tz: timezone) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + 1, 1, 1, tzinfo=tz) if month == 12 else datetime(
        year, month + 1, 1, tzinfo=tz
    )
    return start, end


def reconstruct_hourly_load(
    source: MonthlyLoadDataset,
    *,
    variant: BenchmarkVariant,
    shape: ReconstructionShape,
    reference_year: int,
    timezone_offset: str = "+00:00",
) -> ReconstructionResult:
    if not 1900 <= reference_year <= 9998:
        raise ValueError("reference_year must be between 1900 and 9998")
    if shape not in VALID_SHAPES:
        raise ValueError(f"unsupported reconstruction shape: {shape}")
    tz = parse_fixed_utc_offset(timezone_offset)
    targets, variant_factor = monthly_targets(source, variant)
    timestamps: list[datetime] = []
    hourly_values: list[float] = []
    validation: list[MonthlyReconstructionValidation] = []

    for row, target in zip(source.rows, targets, strict=True):
        start, end = _month_bounds(reference_year, row.month, tz)
        hours = int((end - start).total_seconds() / 3600)
        month_timestamps = [start + timedelta(hours=index) for index in range(hours)]
        if shape == "flat_within_month":
            weights = [1.0] * hours
        else:
            weights = [
                synthetic_shape_multiplier(shape, timestamp.hour)
                for timestamp in month_timestamps
            ]
        factor = target / math.fsum(weights)
        values = [weight * factor for weight in weights]
        values[-1] += target - math.fsum(values)
        reconstructed = math.fsum(values)
        absolute_error = abs(reconstructed - target)
        if absolute_error > MONTHLY_ABSOLUTE_TOLERANCE_KWH:
            raise ValueError(
                f"hourly reconstruction failed monthly conservation for {row.month_name}: "
                f"{absolute_error} kWh error"
            )
        timestamps.extend(month_timestamps)
        hourly_values.extend(values)
        validation.append(
            MonthlyReconstructionValidation(
                month=row.month,
                month_name=row.month_name,
                published_monthly_row_kwh=row.load_kwh,
                source_target_kwh=target,
                reconstructed_kwh=reconstructed,
                absolute_error_kwh=absolute_error,
                relative_error=absolute_error / target if target else 0.0,
            )
        )

    metadata = source.provenance
    integrity_note = (
        "The paper's monthly rows and annual total conflict. This derived variant "
        "proportionally rescales the monthly rows to match the printed annual total."
        if variant == "annual_total_normalized"
        else "Monthly constraints use each printed table row without correction."
    )
    shape_method = "flat_within_month" if shape == "flat_within_month" else (
        "template_scaled_monthly"
    )
    shape_note = (
        "Hourly demand is constant within each month."
        if shape == "flat_within_month"
        else f"Hourly timing uses the deterministic synthetic {shape} template."
    )
    dataset = LoadDataset(
        timestamps=timestamps,
        total_load_kwh=hourly_values,
        critical_load_kwh=None,
        provenance=LoadProvenance(
            source=f"{metadata.publication_title}; {metadata.doi}",
            source_type=LoadSourceType.LITERATURE_DERIVED,
            data_quality=LoadDataQuality.LITERATURE_DERIVED,
            start_time=timestamps[0],
            end_time=timestamps[-1] + timedelta(hours=1),
            location_description=(
                f"{metadata.location_name}, {metadata.region}, {metadata.country}; "
                "coordinates not supplied or inferred"
            ),
            processing_steps=[
                integrity_note,
                shape_note,
                "Scaled independently within every calendar month to conserve its target energy.",
                "Applied any floating-point residual to the final hour of that month.",
            ],
            scaling_factor=variant_factor,
            critical_load_method="Unknown; the publication does not support a critical-load series.",
            notes=(
                "Literature-derived Rodina benchmark. Hourly values are reconstructed, not "
                "measured or utility-reported demand."
            ),
            source_publication=metadata.publication_title,
            doi=metadata.doi,
            source_table=metadata.source_table,
            published_values_transcribed=True,
            hourly_values_measured=False,
            hourly_values_reconstructed=True,
            monthly_constraint_interpretation=variant,
            hourly_shape_method=shape_method,
            hourly_shape_template=None if shape == "flat_within_month" else shape,
            reference_year=reference_year,
            reference_year_is_source_period=False,
            known_source_inconsistency=True,
            timezone_assumption=(
                f"Fixed offset {timezone_offset} is a configurable simulation timestamp carrier; "
                "the publication does not identify the source load timezone or calendar year."
            ),
        ),
    )
    annual = math.fsum(hourly_values)
    peak_index = max(range(len(hourly_values)), key=hourly_values.__getitem__)
    mean = annual / len(hourly_values)
    peak = hourly_values[peak_index]
    summary = ReconstructedLoadSummary(
        variant=variant,
        shape=shape,
        reference_year=reference_year,
        timezone_offset=timezone_offset,
        records=len(timestamps),
        annual_energy_kwh=annual,
        published_annual_total_kwh=metadata.published_annual_load_kwh,
        difference_from_published_annual_kwh=annual - metadata.published_annual_load_kwh,
        peak_hourly_load_kwh=peak,
        peak_timestamp=timestamps[peak_index].isoformat(),
        mean_hourly_load_kwh=mean,
        load_factor=mean / peak if peak else 0.0,
    )
    return ReconstructionResult(dataset=dataset, validation=validation, summary=summary)
