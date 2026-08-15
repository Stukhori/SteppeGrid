"""Explicit scaling operations for hourly load datasets."""

from datetime import datetime

from steppegrid.simulation.models import LoadDataset


def _is_full_calendar_year(start: datetime, end: datetime) -> bool:
    return (
        start.month == start.day == 1
        and start.hour == start.minute == start.second == start.microsecond == 0
        and end.month == end.day == 1
        and end.hour == end.minute == end.second == end.microsecond == 0
        and end.year == start.year + 1
    )


def scale_load_dataset(
    dataset: LoadDataset,
    *,
    target_annual_kwh: float | None = None,
    scale_factor: float | None = None,
) -> LoadDataset:
    """Scale total and critical load together, recording the applied factor."""
    if target_annual_kwh is not None and scale_factor is not None:
        raise ValueError("choose either target_annual_kwh or scale_factor, not both")
    if target_annual_kwh is not None:
        if target_annual_kwh <= 0:
            raise ValueError("target_annual_kwh must be positive")
        if not _is_full_calendar_year(
            dataset.provenance.start_time, dataset.provenance.end_time
        ):
            raise ValueError("target_annual_kwh requires one complete calendar year")
        reference_total = sum(dataset.total_load_kwh)
        if reference_total <= 0:
            raise ValueError("cannot scale a zero-energy reference profile")
        applied_factor = target_annual_kwh / reference_total
        step = f"Scaled complete-year energy to {target_annual_kwh:g} kWh."
    elif scale_factor is not None:
        if scale_factor <= 0:
            raise ValueError("scale_factor must be positive")
        applied_factor = scale_factor
        step = f"Applied user-specified scale factor {scale_factor:g}."
    else:
        return dataset

    provenance = dataset.provenance.model_copy(
        update={
            "scaling_factor": dataset.provenance.scaling_factor * applied_factor,
            "processing_steps": [*dataset.provenance.processing_steps, step],
        }
    )
    critical = (
        [value * applied_factor for value in dataset.critical_load_kwh]
        if dataset.critical_load_kwh is not None
        else None
    )
    return dataset.model_copy(
        update={
            "total_load_kwh": [value * applied_factor for value in dataset.total_load_kwh],
            "critical_load_kwh": critical,
            "provenance": provenance,
        }
    )
