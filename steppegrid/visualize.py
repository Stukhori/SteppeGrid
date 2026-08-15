"""Optional diagnostic charts from an exported hourly-results CSV."""

import argparse
import csv
from datetime import datetime
from pathlib import Path


def create_diagnostic_charts(csv_path: Path, output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError('Visualization requires: python -m pip install -e ".[visualization]"') from error
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("result CSV is empty")
    timestamps = [datetime.fromisoformat(row["timestamp"]) for row in rows]

    def series(name: str) -> list[float]:
        return [float(row[name]) for row in rows]

    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(timestamps, series("demand_kwh"), label="Demand")
    axes[0].plot(timestamps, series("renewable_generation_kwh"), label="Renewables")
    axes[0].set_ylabel("Energy (kWh/hour)")
    axes[0].legend()
    axes[1].plot(timestamps, series("battery_soc_kwh"), label="Battery SOC")
    axes[1].set_ylabel("Stored energy (kWh)")
    axes[1].legend()
    axes[2].plot(timestamps, series("grid_import_kwh"), label="Grid import")
    axes[2].plot(timestamps, series("unserved_energy_kwh"), label="Unserved")
    axes[2].set_ylabel("Energy (kWh)")
    axes[2].legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("steppegrid-diagnostics.png"))
    args = parser.parse_args()
    create_diagnostic_charts(args.csv_path, args.output)


if __name__ == "__main__":
    main()
