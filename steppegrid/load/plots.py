"""Optional diagnostic plots for normalized load datasets."""

from pathlib import Path

from steppegrid.load.inspection import summarize_load
from steppegrid.simulation.models import LoadDataset


def create_load_plots(dataset: LoadDataset, output_directory: str | Path) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            'Load plots require: python -m pip install -e ".[visualization]"'
        ) from error
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    hourly_path = output / "load_hourly.png"
    figure, axis = plt.subplots(figsize=(12, 4))
    axis.plot(dataset.timestamps, dataset.total_load_kwh, label="Total load")
    if dataset.critical_load_kwh is not None:
        axis.plot(dataset.timestamps, dataset.critical_load_kwh, label="Critical load")
    axis.set_ylabel("Energy (kWh/hour)")
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(hourly_path, dpi=150)
    plt.close(figure)

    summary = summarize_load(dataset)
    daily_path = output / "load_typical_daily.png"
    figure, axis = plt.subplots(figsize=(10, 4))
    axis.plot(
        list(summary.typical_daily_load_kwh),
        list(summary.typical_daily_load_kwh.values()),
        marker="o",
    )
    axis.set_xlabel("Hour of day")
    axis.set_ylabel("Average load (kWh/hour)")
    axis.set_xticks(range(24))
    figure.tight_layout()
    figure.savefig(daily_path, dpi=150)
    plt.close(figure)

    monthly_path = output / "load_monthly_energy.png"
    monthly = summary.monthly_energy_kwh
    figure, axis = plt.subplots(figsize=(10, 4))
    axis.bar(list(monthly), list(monthly.values()))
    axis.set_ylabel("Energy (kWh)")
    axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    figure.savefig(monthly_path, dpi=150)
    plt.close(figure)

    paths = [hourly_path, daily_path, monthly_path]
    if dataset.critical_load_kwh is not None:
        critical_path = output / "load_critical_comparison.png"
        figure, axis = plt.subplots(figsize=(6, 4))
        axis.bar(
            ["Total", "Critical"],
            [summary.total_energy_kwh, summary.critical_energy_kwh or 0.0],
        )
        axis.set_ylabel("Energy (kWh)")
        figure.tight_layout()
        figure.savefig(critical_path, dpi=150)
        plt.close(figure)
        paths.append(critical_path)
    return paths
