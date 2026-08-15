"""Optional plots for literature benchmark transcription and shape sensitivity."""

from __future__ import annotations

from pathlib import Path

from steppegrid.benchmarks.models import MonthlyLoadDataset, ReconstructionResult
from steppegrid.benchmarks.sensitivity import hour_of_day_profile


def create_benchmark_plots(
    source: MonthlyLoadDataset,
    results: list[ReconstructionResult],
    output_directory: str | Path,
) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            'Benchmark plots require: python -m pip install -e ".[visualization]"'
        ) from error
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    months = [row.month_name[:3] for row in source.rows]
    colors = ("#3b6f8f", "#b64d42", "#4f7d4a")

    monthly_path = output / "published_monthly_load.png"
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(months, [row.load_kwh for row in source.rows], color="#3b6f8f")
    axis.set_title("Published Rodina monthly load rows")
    axis.set_ylabel("Literature-derived monthly energy (kWh)")
    axis.set_xlabel("Month")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(monthly_path, dpi=180)
    plt.close(figure)

    comparison_path = output / "hourly_shape_comparison.png"
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    windows = ((0, "Representative winter week"), (181 * 24, "Representative summer week"))
    for axis, (start, title) in zip(axes, windows, strict=True):
        hours = range(168)
        for result, color in zip(results, colors, strict=True):
            axis.plot(
                hours,
                result.dataset.total_load_kwh[start : start + 168],
                label=result.summary.shape,
                color=color,
            )
        axis.set_title(title)
        axis.set_ylabel("Reconstructed load (kWh/hour)")
        axis.grid(alpha=0.25)
        axis.legend()
    axes[-1].set_xlabel("Hour in selected week")
    figure.tight_layout()
    figure.savefig(comparison_path, dpi=180)
    plt.close(figure)

    typical_path = output / "typical_day.png"
    figure, axis = plt.subplots(figsize=(10, 5))
    for result, color in zip(results, colors, strict=True):
        profile = hour_of_day_profile(result)
        axis.plot(
            list(profile),
            list(profile.values()),
            marker="o",
            label=result.summary.shape,
            color=color,
        )
    axis.set_xticks(range(24))
    axis.set_xlabel("Hour of day in configured fixed-offset carrier")
    axis.set_ylabel("Mean reconstructed load (kWh/hour)")
    axis.set_title("Rodina reconstructed typical-day shape sensitivity")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(typical_path, dpi=180)
    plt.close(figure)

    validation_path = output / "monthly_reconstruction_validation.png"
    figure, axis = plt.subplots(figsize=(10, 5))
    target = [row.source_target_kwh for row in results[0].validation]
    axis.bar(months, target, color="#c8c8c8", label="Selected monthly target")
    for result, color in zip(results, colors, strict=True):
        axis.plot(
            months,
            [row.reconstructed_kwh for row in result.validation],
            marker="o",
            color=color,
            label=result.summary.shape,
        )
    axis.set_xlabel("Month")
    axis.set_ylabel("Energy (kWh)")
    axis.set_title("Monthly constraints versus reconstructed sums")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(validation_path, dpi=180)
    plt.close(figure)
    return [monthly_path, comparison_path, typical_path, validation_path]
