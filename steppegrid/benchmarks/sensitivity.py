"""Load-shape sensitivity analysis with fixed monthly energy constraints."""

from __future__ import annotations

import csv
from pathlib import Path

from steppegrid.benchmarks.models import MonthlyLoadDataset, ReconstructionResult
from steppegrid.benchmarks.reconstruction import (
    BenchmarkVariant,
    VALID_SHAPES,
    reconstruct_hourly_load,
)


def hour_of_day_profile(result: ReconstructionResult) -> dict[int, float]:
    grouped = {hour: [] for hour in range(24)}
    for timestamp, value in zip(
        result.dataset.timestamps, result.dataset.total_load_kwh, strict=True
    ):
        grouped[timestamp.hour].append(value)
    return {hour: sum(values) / len(values) for hour, values in grouped.items()}


def build_shape_sensitivity(
    source: MonthlyLoadDataset,
    *,
    variant: BenchmarkVariant,
    reference_year: int,
    timezone_offset: str,
) -> list[ReconstructionResult]:
    return [
        reconstruct_hourly_load(
            source,
            variant=variant,
            shape=shape,
            reference_year=reference_year,
            timezone_offset=timezone_offset,
        )
        for shape in VALID_SHAPES
    ]


def write_shape_sensitivity(
    results: list[ReconstructionResult], output_directory: str | Path
) -> Path:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    summaries = [result.summary for result in results]
    with (output / "load_shape_sensitivity.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = [
            "shape",
            "annual_energy_kwh",
            "maximum_monthly_error_kwh",
            "peak_hourly_load_kwh",
            "peak_timestamp",
            "mean_hourly_load_kwh",
            "load_factor",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "shape": result.summary.shape,
                    "annual_energy_kwh": result.summary.annual_energy_kwh,
                    "maximum_monthly_error_kwh": max(
                        row.absolute_error_kwh for row in result.validation
                    ),
                    "peak_hourly_load_kwh": result.summary.peak_hourly_load_kwh,
                    "peak_timestamp": result.summary.peak_timestamp,
                    "mean_hourly_load_kwh": result.summary.mean_hourly_load_kwh,
                    "load_factor": result.summary.load_factor,
                }
            )
    profiles = {result.summary.shape: hour_of_day_profile(result) for result in results}
    with (output / "hour_of_day_profile.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("hour", *profiles))
        for hour in range(24):
            writer.writerow((hour, *(profiles[shape][hour] for shape in profiles)))

    peaks = {summary.shape: summary.peak_hourly_load_kwh for summary in summaries}
    peak_range = max(peaks.values()) - min(peaks.values())
    lines = [
        "# Rodina Hourly Load-Shape Sensitivity",
        "",
        "Monthly energy is constrained by the publication, but intraday timing is not. "
        "Different deterministic hourly shapes therefore produce different peaks and timing "
        "while preserving the same selected monthly totals.",
        "",
        f"- Variant: `{summaries[0].variant}`",
        f"- Reference year carrier: {summaries[0].reference_year}",
        f"- Fixed timezone offset carrier: `{summaries[0].timezone_offset}`",
        "- No shape is asserted to be the true Rodina hourly load.",
        "",
        "| Shape | Annual energy (kWh) | Peak hourly load (kWh) | Mean hourly load (kWh) | Load factor |",
        "|---|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            f"| {summary.shape} | {summary.annual_energy_kwh:.6f} | "
            f"{summary.peak_hourly_load_kwh:.6f} | "
            f"{summary.mean_hourly_load_kwh:.6f} | {summary.load_factor:.6f} |"
        )
    lines.extend(
        [
            "",
            f"Peak range across shapes: {peak_range:.6f} kWh/hour.",
            "",
            "## Pairwise Peak Differences",
            "",
        ]
    )
    for index, left in enumerate(summaries):
        for right in summaries[index + 1 :]:
            lines.append(
                f"- `{right.shape}` minus `{left.shape}`: "
                f"{right.peak_hourly_load_kwh - left.peak_hourly_load_kwh:+.6f} kWh/hour"
            )
    lines.extend(
        [
            "",
            "These differences quantify reconstruction uncertainty only. They do not validate "
            "a shape, establish measured peaks, or support equipment sizing.",
            "",
        ]
    )
    (output / "load_shape_sensitivity.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return output
