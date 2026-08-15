"""Transparent descriptive summaries of hourly load datasets."""

from collections import defaultdict

from pydantic import Field

from steppegrid.simulation.models import DomainModel, LoadDataset


class LoadInspection(DomainModel):
    records: int = Field(ge=1)
    total_energy_kwh: float = Field(ge=0)
    average_hourly_load_kwh: float = Field(ge=0)
    peak_hourly_load_kwh: float = Field(ge=0)
    peak_timestamp: str
    missing_hours: int = Field(default=0, ge=0)
    duplicate_timestamps: int = Field(default=0, ge=0)
    critical_energy_kwh: float | None = Field(default=None, ge=0)
    critical_fraction_of_energy: float | None = Field(default=None, ge=0, le=1)
    monthly_energy_kwh: dict[str, float]
    daily_energy_kwh: dict[str, float]
    typical_daily_load_kwh: dict[int, float]


def summarize_load(dataset: LoadDataset) -> LoadInspection:
    monthly: dict[str, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    by_hour: dict[int, list[float]] = defaultdict(list)
    for timestamp, value in zip(dataset.timestamps, dataset.total_load_kwh, strict=True):
        monthly[timestamp.strftime("%Y-%m")] += value
        daily[timestamp.date().isoformat()] += value
        by_hour[timestamp.hour].append(value)
    peak_index = max(range(len(dataset.total_load_kwh)), key=dataset.total_load_kwh.__getitem__)
    total = sum(dataset.total_load_kwh)
    critical = (
        sum(dataset.critical_load_kwh)
        if dataset.critical_load_kwh is not None
        else None
    )
    return LoadInspection(
        records=len(dataset.timestamps),
        total_energy_kwh=total,
        average_hourly_load_kwh=total / len(dataset.timestamps),
        peak_hourly_load_kwh=dataset.total_load_kwh[peak_index],
        peak_timestamp=dataset.timestamps[peak_index].isoformat(),
        critical_energy_kwh=critical,
        critical_fraction_of_energy=(critical / total if critical is not None and total else 0.0)
        if critical is not None
        else None,
        monthly_energy_kwh=dict(monthly),
        daily_energy_kwh=dict(daily),
        typical_daily_load_kwh={
            hour: sum(values) / len(values) for hour, values in sorted(by_hour.items())
        },
    )
