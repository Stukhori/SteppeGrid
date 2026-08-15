"""Machine-readable simulation result exports."""

import csv
from pathlib import Path

from steppegrid.simulation.models import SimulationResult

RESULT_COLUMNS = (
    "timestamp", "demand_kwh", "solar_generation_kwh", "wind_generation_kwh",
    "renewable_generation_kwh", "battery_soc_kwh", "battery_charge_kwh",
    "battery_discharge_kwh", "grid_import_kwh", "unserved_energy_kwh",
    "curtailed_energy_kwh", "grid_available",
)


def export_hourly_results_csv(result: SimulationResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in result.hourly:
            writer.writerow({
                "timestamp": row.timestamp.isoformat(), "demand_kwh": row.demand_kwh,
                "solar_generation_kwh": row.solar_generation_kwh,
                "wind_generation_kwh": row.wind_generation_kwh,
                "renewable_generation_kwh": row.renewable_generation_kwh,
                "battery_soc_kwh": row.battery_soc_end_kwh,
                "battery_charge_kwh": row.battery_charge_kwh,
                "battery_discharge_kwh": row.battery_discharge_kwh,
                "grid_import_kwh": row.grid_import_kwh,
                "unserved_energy_kwh": row.unserved_energy_kwh,
                "curtailed_energy_kwh": row.curtailed_energy_kwh,
                "grid_available": row.grid_available,
            })
