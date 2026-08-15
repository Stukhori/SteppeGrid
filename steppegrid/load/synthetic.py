"""Deterministic synthetic load shapes for tests and demonstrations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from steppegrid.load.scaling import scale_load_dataset
from steppegrid.simulation.models import (
    LoadDataQuality,
    LoadDataset,
    LoadProvenance,
    LoadSourceType,
    Location,
)

SyntheticProfile = Literal["constant", "residential_like", "community_facility_like"]


def synthetic_shape_multiplier(profile: SyntheticProfile, hour: int) -> float:
    if profile == "constant":
        return 1.0
    if profile == "residential_like":
        if 0 <= hour < 6:
            return 0.45
        if 6 <= hour < 9:
            return 1.15
        if 9 <= hour < 17:
            return 0.7
        if 17 <= hour < 23:
            return 1.4
        return 0.65
    if profile == "community_facility_like":
        if 8 <= hour < 18:
            return 1.35
        if 18 <= hour < 22:
            return 0.55
        return 0.25
    raise ValueError(f"unsupported synthetic load profile: {profile}")


class SyntheticLoadProvider:
    def __init__(
        self,
        *,
        profile: SyntheticProfile = "constant",
        scale_factor: float | None = None,
        target_annual_kwh: float | None = None,
        critical_fraction: float | None = None,
        location: Location | None = None,
        created_at: datetime | None = None,
        source: str | None = None,
        processing_steps: list[str] | None = None,
    ) -> None:
        if critical_fraction is not None and not 0 <= critical_fraction <= 1:
            raise ValueError("critical_fraction must be between 0 and 1")
        self.profile = profile
        self.scale_factor = scale_factor
        self.target_annual_kwh = target_annual_kwh
        self.critical_fraction = critical_fraction
        self.location = location
        self.created_at = created_at
        self.source = source
        self.processing_steps = processing_steps or []

    def get_hourly_load(self, start: datetime, end: datetime) -> LoadDataset:
        duration = end - start
        hours = int(duration.total_seconds() / 3600)
        if hours <= 0 or duration != timedelta(hours=hours):
            raise ValueError("synthetic load period must contain positive whole hours")
        timestamps = [start + timedelta(hours=index) for index in range(hours)]
        total = [synthetic_shape_multiplier(self.profile, timestamp.hour) for timestamp in timestamps]
        critical = (
            [value * self.critical_fraction for value in total]
            if self.critical_fraction is not None
            else None
        )
        method = (
            f"Assumed constant critical fraction {self.critical_fraction:g} of total load."
            if self.critical_fraction is not None
            else None
        )
        dataset = LoadDataset(
            timestamps=timestamps,
            total_load_kwh=total,
            critical_load_kwh=critical,
            provenance=LoadProvenance(
                source="; ".join(
                    value
                    for value in (
                        self.source,
                        f"SteppeGrid deterministic synthetic {self.profile} shape",
                        "not measured or location-calibrated data",
                    )
                    if value
                ),
                source_type=LoadSourceType.SYNTHETIC_MODEL,
                data_quality=LoadDataQuality.SYNTHETIC,
                start_time=start,
                end_time=end,
                retrieved_or_created_at=self.created_at,
                location=self.location,
                original_units={
                    "total_load_kwh": "kWh/hour",
                    **(
                        {"critical_load_kwh": "kWh/hour"}
                        if critical is not None
                        else {}
                    ),
                },
                normalized_units={
                    "total_load_kwh": "kWh/hour",
                    **(
                        {"critical_load_kwh": "kWh/hour"}
                        if critical is not None
                        else {}
                    ),
                },
                processing_steps=[
                    "Generated from fixed hour-of-day multipliers with no randomness.",
                    *self.processing_steps,
                ],
                critical_load_method=method,
                notes="Shape labels are illustrative and make no empirical regional claim.",
            ),
        )
        return scale_load_dataset(
            dataset,
            target_annual_kwh=self.target_annual_kwh,
            scale_factor=self.scale_factor,
        )
