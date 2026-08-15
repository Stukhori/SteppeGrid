"""SteppeGrid scenario command-line interface."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from steppegrid.examples.synthetic import synthetic_24_hour_scenario
from steppegrid.export import export_hourly_results_csv
from steppegrid.scenario import ResolvedScenario, load_and_resolve_scenario
from steppegrid.simulation.models import SimulationResult
from steppegrid.simulation.simulator import simulate


def _summary(result: SimulationResult, resolved: ResolvedScenario | None = None) -> str:
    metrics = result.metrics
    location = resolved.scenario.location.name if resolved else "Synthetic demonstration"
    start = result.hourly[0].timestamp
    end = resolved.scenario.end_time if resolved else result.hourly[-1].timestamp + timedelta(hours=1)
    outage_fraction = (
        metrics.outage_served_energy_kwh / metrics.outage_demand_kwh
        if metrics.outage_demand_kwh else 0.0
    )
    return f"""STEPPEGRID SIMULATION

Location: {location or 'Unnamed location'}
Period: {start.isoformat()} -> {end.isoformat()}

ENERGY
Demand:                 {metrics.total_demand_kwh:.3f} kWh
Solar generation:       {metrics.solar_generation_kwh:.3f} kWh
Wind generation:        {metrics.wind_generation_kwh:.3f} kWh
Grid import:             {metrics.grid_import_kwh:.3f} kWh
Battery discharge:      {metrics.battery_discharge_kwh:.3f} kWh
Battery losses:         {metrics.battery_loss_kwh:.3f} kWh
Curtailed energy:       {metrics.curtailed_energy_kwh:.3f} kWh
Unserved energy:        {metrics.unserved_energy_kwh:.3f} kWh

RESILIENCE
Outage demand:           {metrics.outage_demand_kwh:.3f} kWh
Outage served:           {metrics.outage_served_energy_kwh:.3f} kWh
Outage unserved:         {metrics.outage_unserved_energy_kwh:.3f} kWh
Outage load served:      {outage_fraction:.1%}

RENEWABLES
Renewable fraction:      {metrics.renewable_fraction:.1%}"""


def _json_output(result: SimulationResult, resolved: ResolvedScenario | None) -> str:
    payload: dict[str, object] = {"metrics": result.metrics.model_dump(mode="json")}
    if resolved:
        payload.update({
            "location": resolved.scenario.location.model_dump(mode="json"),
            "period": {
                "start": resolved.scenario.start_time.isoformat(),
                "end": resolved.scenario.end_time.isoformat(),
            },
            "weather_provenance": resolved.weather_provenance.model_dump(mode="json"),
        })
    return json.dumps(payload, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steppegrid")
    subparsers = parser.add_subparsers(dest="command")
    simulate_parser = subparsers.add_parser("simulate", help="run a scenario")
    simulate_parser.add_argument("--scenario", required=True, type=Path)
    simulate_parser.add_argument("--format", choices=("text", "json"), default="text")
    simulate_parser.add_argument("--export-csv", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "simulate":
        resolved = load_and_resolve_scenario(args.scenario)
        result = simulate(resolved.simulation_input)
        if args.export_csv:
            export_hourly_results_csv(result, args.export_csv)
        print(_json_output(result, resolved) if args.format == "json" else _summary(result, resolved))
        return
    print(_summary(simulate(synthetic_24_hour_scenario())))


if __name__ == "__main__":
    main()
