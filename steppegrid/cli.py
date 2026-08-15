"""SteppeGrid scenario command-line interface."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from steppegrid.benchmarks.outputs import write_reconstruction, write_source_integrity
from steppegrid.benchmarks.plots import create_benchmark_plots
from steppegrid.benchmarks.reconstruction import (
    VALID_SHAPES,
    VALID_VARIANTS,
    reconstruct_hourly_load,
)
from steppegrid.benchmarks.sensitivity import (
    build_shape_sensitivity,
    write_shape_sensitivity,
)
from steppegrid.benchmarks.source import (
    BenchmarkSourceError,
    load_monthly_benchmark,
    validate_source_integrity,
)
from steppegrid.examples.synthetic import synthetic_24_hour_scenario
from steppegrid.export import export_hourly_results_csv
from steppegrid.load.csv_provider import CSVLoadProvider, LoadDataError
from steppegrid.load.inspection import summarize_load
from steppegrid.load.plots import create_load_plots
from steppegrid.scenario import ResolvedScenario, load_and_resolve_scenario
from steppegrid.site.workflow import analyze_pilot_site
from steppegrid.site.config import PilotSiteConfigError
from steppegrid.simulation.models import LoadDataQuality, Location, SimulationResult
from steppegrid.simulation.simulator import simulate
from steppegrid.weather.inspection import summarize_weather
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider


def _summary(result: SimulationResult, resolved: ResolvedScenario | None = None) -> str:
    metrics = result.metrics
    location = resolved.scenario.location.name if resolved else "Synthetic demonstration"
    start = result.hourly[0].timestamp
    end = resolved.scenario.end_time if resolved else result.hourly[-1].timestamp + timedelta(hours=1)
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
Outage total demand:      {metrics.outage_total_demand_kwh:.3f} kWh
Outage total served:      {metrics.outage_total_served_kwh:.3f} kWh
Outage total unserved:    {metrics.outage_total_unserved_kwh:.3f} kWh
Outage critical demand:   {metrics.outage_critical_demand_kwh:.3f} kWh
Outage critical served:   {metrics.outage_critical_served_kwh:.3f} kWh
Outage critical unserved: {metrics.outage_critical_unserved_kwh:.3f} kWh
Critical load served:     {metrics.critical_load_served_fraction:.1%}

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
            "load_provenance": resolved.load_provenance.model_dump(mode="json"),
        })
    return json.dumps(payload, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steppegrid")
    subparsers = parser.add_subparsers(dest="command")
    simulate_parser = subparsers.add_parser("simulate", help="run a scenario")
    simulate_parser.add_argument("--scenario", required=True, type=Path)
    simulate_parser.add_argument("--format", choices=("text", "json"), default="text")
    simulate_parser.add_argument("--export-csv", type=Path)
    simulate_parser.add_argument(
        "--refresh-weather", action="store_true", help="bypass a live weather cache"
    )

    weather_parser = subparsers.add_parser("weather", help="fetch and inspect weather data")
    weather_subparsers = weather_parser.add_subparsers(dest="weather_command", required=True)
    fetch_parser = weather_subparsers.add_parser("fetch", help="fetch historical reanalysis")
    fetch_parser.add_argument("--lat", type=float, required=True)
    fetch_parser.add_argument("--lon", type=float, required=True)
    fetch_parser.add_argument("--start", type=date.fromisoformat, required=True)
    fetch_parser.add_argument("--end", type=date.fromisoformat, required=True)
    fetch_parser.add_argument("--provider", choices=("open-meteo",), default="open-meteo")
    fetch_parser.add_argument("--model", choices=("era5",), default="era5")
    fetch_parser.add_argument("--cache-dir", type=Path, default=Path("data/weather/cache"))
    fetch_parser.add_argument("--refresh", action="store_true")

    load_parser = subparsers.add_parser("load", help="inspect electricity-load data")
    load_subparsers = load_parser.add_subparsers(dest="load_command", required=True)
    inspect_parser = load_subparsers.add_parser(
        "inspect", help="validate and summarize an hourly load CSV"
    )
    inspect_parser.add_argument("--file", required=True, type=Path)
    inspect_parser.add_argument(
        "--quality",
        choices=tuple(quality.value for quality in LoadDataQuality),
        default=LoadDataQuality.UNSPECIFIED.value,
        help="evidence classification supplied by the user",
    )
    inspect_parser.add_argument("--source")
    inspect_parser.add_argument("--plots-dir", type=Path)

    site_parser = subparsers.add_parser("site", help="pilot-site analysis workflows")
    site_subparsers = site_parser.add_subparsers(dest="site_command", required=True)
    analyze_parser = site_subparsers.add_parser(
        "analyze", help="analyze one complete ERA5 weather year"
    )
    analyze_parser.add_argument("--config", required=True, type=Path)
    analyze_parser.add_argument("--output", type=Path)
    analyze_parser.add_argument("--refresh", action="store_true")

    benchmark_parser = subparsers.add_parser(
        "benchmark", help="validate and reconstruct literature benchmarks"
    )
    benchmark_names = benchmark_parser.add_subparsers(
        dest="benchmark_name", required=True
    )
    rodina_parser = benchmark_names.add_parser(
        "rodina", help="Rodina literature-derived village benchmark"
    )
    rodina_commands = rodina_parser.add_subparsers(
        dest="benchmark_command", required=True
    )
    validate_parser = rodina_commands.add_parser(
        "validate", help="compare printed annual totals with monthly-row sums"
    )
    validate_parser.add_argument(
        "--source-dir", type=Path, default=Path("data/benchmarks/rodina")
    )
    validate_parser.add_argument(
        "--output", type=Path, default=Path("outputs/benchmarks/rodina")
    )

    build_load_parser = rodina_commands.add_parser(
        "build-load", help="build one monthly-constrained hourly reconstruction"
    )
    build_load_parser.add_argument("--variant", choices=VALID_VARIANTS, required=True)
    build_load_parser.add_argument("--shape", choices=VALID_SHAPES, required=True)
    build_load_parser.add_argument("--reference-year", type=int, required=True)
    build_load_parser.add_argument("--timezone-offset", default="+00:00")
    build_load_parser.add_argument(
        "--source-dir", type=Path, default=Path("data/benchmarks/rodina")
    )
    build_load_parser.add_argument(
        "--output", type=Path, default=Path("outputs/benchmarks/rodina")
    )

    sensitivity_parser = rodina_commands.add_parser(
        "sensitivity", help="compare deterministic hourly shape assumptions"
    )
    sensitivity_parser.add_argument("--variant", choices=VALID_VARIANTS, required=True)
    sensitivity_parser.add_argument("--reference-year", type=int, required=True)
    sensitivity_parser.add_argument("--timezone-offset", default="+00:00")
    sensitivity_parser.add_argument(
        "--source-dir", type=Path, default=Path("data/benchmarks/rodina")
    )
    sensitivity_parser.add_argument(
        "--output", type=Path, default=Path("outputs/benchmarks/rodina")
    )
    sensitivity_parser.add_argument("--no-plots", action="store_true")
    return parser


def _utc_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _weather_summary(dataset) -> str:
    provenance = dataset.provenance
    summary = summarize_weather(dataset)
    return f"""STEPPEGRID WEATHER DATA

Provider: {provenance.provider}
Model: {provenance.underlying_model}
Requested coordinates: {provenance.requested_latitude}, {provenance.requested_longitude}
Returned coordinates: {provenance.returned_latitude}, {provenance.returned_longitude}
Approximate grid-cell distance: {provenance.coordinate_distance_km:.3f} km
Period: {provenance.start_time.isoformat()} -> {provenance.end_time.isoformat()} (end exclusive)
Hourly records: {summary.records}
Timezone: {provenance.timezone}
Wind unit: m/s
Solar unit: W/m2
Temperature unit: degC
Cache: {provenance.cache_status}
Normalized file: {provenance.normalized_data_path}
Metadata file: {provenance.metadata_path}
Raw response: {provenance.raw_response_path}

INSPECTION
Mean wind speed: {summary.mean_wind_speed_m_s:.3f} m/s
Median wind speed: {summary.median_wind_speed_m_s:.3f} m/s
95th percentile wind speed: {summary.percentile_95_wind_speed_m_s:.3f} m/s
Maximum wind speed: {summary.maximum_wind_speed_m_s:.3f} m/s
Mean shortwave irradiance: {summary.mean_solar_irradiance_w_m2:.3f} W/m2
Horizontal irradiation over period: {summary.horizontal_irradiation_kwh_m2:.3f} kWh/m2
Mean temperature: {summary.mean_temperature_c:.3f} degC
Minimum temperature: {summary.minimum_temperature_c:.3f} degC
Maximum temperature: {summary.maximum_temperature_c:.3f} degC
Missing records: {summary.missing_records}"""


def _load_summary(dataset) -> str:
    provenance = dataset.provenance
    summary = summarize_load(dataset)
    critical_energy = (
        f"{summary.critical_energy_kwh:.3f} kWh"
        if summary.critical_energy_kwh is not None
        else "not supplied"
    )
    critical_fraction = (
        f"{summary.critical_fraction_of_energy:.1%}"
        if summary.critical_fraction_of_energy is not None
        else "not supplied"
    )
    monthly = "\n".join(
        f"  {month}: {energy:.3f} kWh"
        for month, energy in summary.monthly_energy_kwh.items()
    )
    daily_values = list(summary.daily_energy_kwh.values())
    return f"""STEPPEGRID LOAD DATA

Source: {provenance.source}
Source type: {provenance.source_type.value}
Data quality: {provenance.data_quality.value}
Period: {provenance.start_time.isoformat()} -> {provenance.end_time.isoformat()} (end exclusive)
Hourly records: {summary.records}
Scaling factor: {provenance.scaling_factor:g}
Critical-load method: {provenance.critical_load_method or 'not supplied'}

INSPECTION
Total energy: {summary.total_energy_kwh:.3f} kWh
Average hourly load: {summary.average_hourly_load_kwh:.3f} kWh
Peak hourly load: {summary.peak_hourly_load_kwh:.3f} kWh
Peak timestamp: {summary.peak_timestamp}
Critical energy: {critical_energy}
Critical fraction of energy: {critical_fraction}
Missing hours: {summary.missing_hours}
Duplicate timestamps: {summary.duplicate_timestamps}
Daily energy range: {min(daily_values):.3f} -> {max(daily_values):.3f} kWh
Average daily energy: {sum(daily_values) / len(daily_values):.3f} kWh

MONTHLY ENERGY
{monthly}"""


def _integrity_summary(report) -> str:
    lines = ["STEPPEGRID RODINA SOURCE INTEGRITY", ""]
    for label, comparison in (
        ("Load", report.load),
        ("PV", report.pv),
        ("Wind", report.wind),
        ("Generation", report.generation),
    ):
        lines.extend(
            [
                label.upper(),
                f"Published annual: {comparison.published_annual_kwh:,} kWh",
                f"Monthly-row sum: {comparison.calculated_monthly_sum_kwh:,} kWh",
                f"Difference: {comparison.difference_kwh:+,} kWh "
                f"({comparison.relative_difference:+.3%})",
                f"Equal: {'yes' if comparison.matches else 'no'}",
                "",
            ]
        )
    lines.append(
        "Known source inconsistency: "
        + ("DETECTED" if report.known_source_inconsistency else "not detected")
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "simulate":
        resolved = load_and_resolve_scenario(
            args.scenario, refresh_weather=args.refresh_weather
        )
        result = simulate(resolved.simulation_input)
        if args.export_csv:
            export_hourly_results_csv(result, args.export_csv)
        print(_json_output(result, resolved) if args.format == "json" else _summary(result, resolved))
        return
    if args.command == "weather" and args.weather_command == "fetch":
        location = Location(latitude=args.lat, longitude=args.lon)
        provider = OpenMeteoHistoricalWeatherProvider(cache_root=args.cache_dir)
        dataset = provider.get_hourly_weather(
            location,
            _utc_midnight(args.start),
            _utc_midnight(args.end),
            refresh=args.refresh,
        )
        print(_weather_summary(dataset))
        return
    if args.command == "load" and args.load_command == "inspect":
        try:
            dataset = CSVLoadProvider(
                args.file,
                source=args.source,
                data_quality=LoadDataQuality(args.quality),
            ).read()
            if args.plots_dir:
                create_load_plots(dataset, args.plots_dir)
        except (LoadDataError, RuntimeError) as error:
            parser.error(str(error))
        print(_load_summary(dataset))
        return
    if args.command == "site" and args.site_command == "analyze":
        try:
            output = analyze_pilot_site(
                args.config,
                refresh=args.refresh,
                output_directory=args.output,
            )
        except PilotSiteConfigError as error:
            parser.error(str(error))
        print("STEPPEGRID PILOT SITE ANALYSIS")
        print(f"Output directory: {output.resolve()}")
        return
    if args.command == "benchmark" and args.benchmark_name == "rodina":
        try:
            source = load_monthly_benchmark(args.source_dir)
            if args.benchmark_command == "validate":
                integrity = validate_source_integrity(source)
                output = write_source_integrity(integrity, args.output)
                print(_integrity_summary(integrity))
                print(f"Output directory: {output.resolve()}")
                return
            if args.benchmark_command == "build-load":
                result = reconstruct_hourly_load(
                    source,
                    variant=args.variant,
                    shape=args.shape,
                    reference_year=args.reference_year,
                    timezone_offset=args.timezone_offset,
                )
                output = write_reconstruction(
                    result, args.output / args.variant / args.shape
                )
                print("STEPPEGRID RODINA HOURLY RECONSTRUCTION")
                print("Classification: LITERATURE_DERIVED / reconstructed, not measured")
                print(f"Variant: {args.variant}")
                print(f"Shape: {args.shape}")
                print(f"Records: {result.summary.records}")
                print(f"Annual energy: {result.summary.annual_energy_kwh:.6f} kWh")
                print(f"Peak hourly load: {result.summary.peak_hourly_load_kwh:.6f} kWh")
                print(f"Output directory: {output.resolve()}")
                return
            results = build_shape_sensitivity(
                source,
                variant=args.variant,
                reference_year=args.reference_year,
                timezone_offset=args.timezone_offset,
            )
            for result in results:
                write_reconstruction(
                    result,
                    args.output / args.variant / result.summary.shape,
                )
            output = write_shape_sensitivity(results, args.output)
            if not args.no_plots:
                create_benchmark_plots(source, results, output)
            print("STEPPEGRID RODINA LOAD-SHAPE SENSITIVITY")
            print("Classification: LITERATURE_DERIVED / reconstructed, not measured")
            print(f"Variant: {args.variant}")
            for result in results:
                print(
                    f"{result.summary.shape}: peak "
                    f"{result.summary.peak_hourly_load_kwh:.6f} kWh/hour"
                )
            print(f"Output directory: {output.resolve()}")
            return
        except (BenchmarkSourceError, ValueError, RuntimeError) as error:
            parser.error(str(error))
    print(_summary(simulate(synthetic_24_hour_scenario())))


if __name__ == "__main__":
    main()
