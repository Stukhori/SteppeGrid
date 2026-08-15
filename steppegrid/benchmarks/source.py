"""Strict literature-source loading and arithmetic integrity checks."""

from __future__ import annotations

import calendar
import csv
from pathlib import Path

import yaml

from steppegrid.benchmarks.models import (
    BenchmarkSourceMetadata,
    IntegrityComparison,
    MonthlyLoadDataset,
    PublishedMonthlyEnergyRow,
    SourceIntegrityReport,
)

RODINA_SOURCE_DIRECTORY = Path("data/benchmarks/rodina")
MONTHLY_COLUMNS = (
    "month",
    "load_kwh",
    "pv_generation_kwh",
    "wind_generation_kwh",
    "published_total_generation_kwh",
    "li_ion_soc_average",
    "supercapacitor_soc_average",
    "published_unserved_kwh",
)


class BenchmarkSourceError(ValueError):
    pass


def load_monthly_benchmark(directory: str | Path = RODINA_SOURCE_DIRECTORY) -> MonthlyLoadDataset:
    root = Path(directory)
    metadata_path = root / "source_metadata.yaml"
    monthly_path = root / "published_monthly_energy.csv"
    if not metadata_path.is_file() or not monthly_path.is_file():
        raise BenchmarkSourceError(f"benchmark source files are incomplete: {root}")
    metadata = BenchmarkSourceMetadata.model_validate(
        yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    )
    rows: list[PublishedMonthlyEnergyRow] = []
    with monthly_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(MONTHLY_COLUMNS):
            raise BenchmarkSourceError(
                "published monthly CSV columns must be exactly: " + ",".join(MONTHLY_COLUMNS)
            )
        for month, raw in enumerate(reader, start=1):
            try:
                rows.append(
                    PublishedMonthlyEnergyRow(
                        month=month,
                        month_name=raw["month"],
                        load_kwh=int(raw["load_kwh"]),
                        pv_generation_kwh=int(raw["pv_generation_kwh"]),
                        wind_generation_kwh=int(raw["wind_generation_kwh"]),
                        published_total_generation_kwh=int(
                            raw["published_total_generation_kwh"]
                        ),
                        li_ion_soc_average=float(raw["li_ion_soc_average"]),
                        supercapacitor_soc_average=float(
                            raw["supercapacitor_soc_average"]
                        ),
                        published_unserved_kwh=int(raw["published_unserved_kwh"]),
                    )
                )
            except (TypeError, ValueError) as error:
                raise BenchmarkSourceError(f"invalid published row {month + 1}") from error
    if len(rows) != 12:
        raise BenchmarkSourceError("published monthly CSV must contain exactly 12 rows")
    for row in rows:
        if row.month_name != calendar.month_name[row.month]:
            raise BenchmarkSourceError(
                f"published row {row.month} must be named {calendar.month_name[row.month]}"
            )
    return MonthlyLoadDataset(rows=rows, provenance=metadata)


def _compare(published: int, calculated: int) -> IntegrityComparison:
    difference = calculated - published
    return IntegrityComparison(
        published_annual_kwh=published,
        calculated_monthly_sum_kwh=calculated,
        difference_kwh=difference,
        relative_difference=difference / published if published else 0.0,
        matches=difference == 0,
    )


def validate_source_integrity(dataset: MonthlyLoadDataset) -> SourceIntegrityReport:
    metadata = dataset.provenance
    report = SourceIntegrityReport(
        benchmark_name=metadata.benchmark_name,
        load=_compare(
            metadata.published_annual_load_kwh,
            sum(row.load_kwh for row in dataset.rows),
        ),
        pv=_compare(
            metadata.published_annual_pv_kwh,
            sum(row.pv_generation_kwh for row in dataset.rows),
        ),
        wind=_compare(
            metadata.published_annual_wind_kwh,
            sum(row.wind_generation_kwh for row in dataset.rows),
        ),
        generation=_compare(
            metadata.published_annual_generation_kwh,
            sum(row.published_total_generation_kwh for row in dataset.rows),
        ),
        known_source_inconsistency=False,
    )
    return report.model_copy(
        update={
            "known_source_inconsistency": not all(
                comparison.matches
                for comparison in (report.load, report.pv, report.wind, report.generation)
            )
        }
    )
