# SteppeGrid

SteppeGrid is an open-source research software project for studying renewable-energy resilience in rural Kazakhstan. It provides a deterministic hourly model of load, solar PV, empirical wind-turbine output, battery storage, grid availability, curtailment, and unserved energy. Location-aware scenarios can use strict hourly CSV weather, deterministic synthetic weather, or cached ERA5 historical reanalysis from Open-Meteo.

## Current research status

Phases 1–13 of the Rodina benchmark are complete. The final validation layer records provenance,
checks the aligned 8,760-hour reconstruction, reproduces the selected 95%/99% designs without a new
optimizer search, and consolidates publication-style tables and figures. Phase 13 adds a read-only
interactive planning application over those frozen results.

```powershell
.\.venv\Scripts\python.exe scripts\run_phase12.py --mode verify
.\.venv\Scripts\python.exe scripts\run_phase12.py --mode reproduce
```

Final artifacts live in `outputs/benchmarks/rodina/phase12/`; reproduction details are in
[the Rodina reproduction guide](docs/reproducing_rodina_results.md). Rodina hourly demand is
reconstructed rather than measured, and annual served-energy fraction is not uptime. A future
Shamshi field case remains contingent on obtaining real electricity-demand data; no Shamshi
optimization is currently reported.

Launch the interactive MVP:

```powershell
python -m pip install -e ".[app]"
streamlit run app.py
```

The app compares the frozen 95% and 99% designs and explores demand, weather, generation, hourly
dispatch, reliability, economics, sensitivity, assumptions, and provenance. It never runs an
optimizer. See [the Phase 13 application guide](docs/phase13_application.md).

Shamshi optimization will be enabled only after real demand data are available.

No included inputs are claimed to represent a Kazakh village, a commercial turbine, or HelixGen. The bundled scenario and turbine curve are synthetic demonstration data.

## Current architecture

```text
steppegrid/
  simulation/       typed domain models, component equations, dispatch, metrics
  weather/          provider interface and synthetic/CSV/Open-Meteo providers
  load/             provider interface, strict CSV/synthetic load, scaling, inspection
  benchmarks/       literature-source integrity and monthly load reconstruction
  data/             source-data loaders such as turbine-curve CSV parsing
  examples/         explicitly synthetic input construction
  scenario.py       serializable YAML/JSON scenario resolution
  export.py         hourly result CSV export
  visualize.py      optional diagnostic plotting
  cli.py            scenario CLI and legacy synthetic demonstration
data/
  benchmarks/       checked-in source transcriptions and publication metadata
  weather/          future validated weather inputs
  load_profiles/    future measured or sourced load inputs
  turbine_curves/   future source-attributed empirical curves
docs/               methodology, assumptions, and roadmap
tests/              deterministic unit and system tests
```

Data ingestion remains outside the simulation package. Providers validate and normalize external sources before constructing the existing simulation models.

## Install and run

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
python -m steppegrid simulate --scenario examples/scenarios/synthetic_household.yaml
```

Export hourly results or print machine-readable metadata and metrics:

```powershell
python -m steppegrid simulate --scenario examples/scenarios/synthetic_household.yaml --export-csv outputs/hourly.csv
python -m steppegrid simulate --scenario examples/scenarios/synthetic_household.yaml --format json
```

Run the provider-based total/critical-load example:

```powershell
python -m steppegrid simulate --scenario examples/scenarios/synthetic_critical_load.yaml
```

The old `python -m steppegrid.cli` command remains a quick synthetic demo. Scenario-relative CSV paths are resolved relative to the scenario file.

## Historical ERA5 weather

Fetch and inspect one half-open UTC date range (`--end` is excluded):

```powershell
python -m steppegrid weather fetch `
  --lat 50.0 --lon 51.0 `
  --start 2025-01-01 --end 2025-01-07 `
  --provider open-meteo --model era5
```

The first successful request stores the exact raw JSON response, normalized CSV, and provenance metadata below `data/weather/cache/open_meteo/era5/<cache-key>/`. Identical requests use the cache, including while offline. Add `--refresh` to the weather command or `--refresh-weather` to simulation to explicitly replace a cache entry.

Run the live-weather scenario example:

```powershell
python -m steppegrid simulate `
  --scenario examples/scenarios/historical_weather_example.yaml `
  --export-csv outputs/historical_hourly.csv
```

The example coordinates and equipment inputs are arbitrary software examples, not a pilot-village dataset. Open-Meteo data are ERA5 gridded historical reanalysis associated with the requested coordinates, not measurements from a local weather station.

Optional diagnostic plots are isolated from the engine:

```powershell
python -m pip install -e ".[visualization]"
python -m steppegrid.visualize outputs/hourly.csv --output outputs/diagnostics.png
```

## Pilot-site annual analysis

Edit `examples/sites/pilot_site.yaml` and replace every `REPLACE_ME` value with the real village name and coordinates. The configured period must be one complete calendar year using the half-open convention, such as `2025-01-01` through `2026-01-01`.

Install the optional plotting dependency and run:

```powershell
python -m pip install -e ".[visualization]"
python -m steppegrid site analyze --config examples/sites/pilot_site.yaml
```

The workflow validates all 8,760 normal-year or 8,784 leap-year UTC records, reuses the existing ERA5 cache, and writes:

```text
outputs/pilot_site/
  weather_summary.json
  weather_summary.csv
  monthly_summary.csv
  provenance.json
  report.md
  simulation_weather_reference.yaml
  wind_distribution.png
  monthly_wind.png
  monthly_solar.png
  wind_solar_seasonality.png
```

The simulation reference contains location, dates, provider, model, and cache location fields compatible with the existing scenario schema. It is a fragment to combine with explicit load, solar, turbine, battery, grid, and outage settings; the workflow does not invent those inputs.

## Input CSV schemas

Weather CSV columns must be exactly:

```text
timestamp,wind_speed_m_s,solar_irradiance_w_m2,temperature_c
```

Timestamps use ISO 8601 and must be unique, chronological, and consecutive hourly values. Missing fields and invalid values are errors; no interpolation occurs. Turbine curve columns must be exactly:

```text
wind_speed_m_s,power_kw
```

Load CSV columns must be exactly either:

```text
timestamp,total_load_kwh
timestamp,total_load_kwh,critical_load_kwh
```

Validate and summarize a load file before using it:

```powershell
python -m steppegrid load inspect --file examples/load/pilot_load_template.csv
```

The template values are synthetic examples of the file format. See [electricity load data](docs/load_data.md) for evidence-quality classifications, scaling, critical-load assumptions, and scenario configuration.

## Rodina literature benchmark

SteppeGrid includes a checked-in transcription of the monthly energy table from a 2026 Rodina, Akmola Region modelling paper. The paper does not publish measured hourly demand, and its printed monthly rows conflict arithmetically with several printed annual totals. SteppeGrid preserves both and exposes the differences.

```powershell
python -m steppegrid benchmark rodina validate
python -m steppegrid benchmark rodina sensitivity --variant published_monthly_rows --reference-year 2025 --timezone-offset +05:00
python -m steppegrid benchmark rodina pair-weather --reference-year 2025 --variant published_monthly_rows
```

Generated hourly profiles are deterministic literature-derived reconstructions constrained by monthly energy. They are not measured Rodina demand. See [Rodina benchmark methodology](docs/benchmarks/rodina.md).

The paired command uses the verified Rodina sampling anchor in `data/benchmarks/rodina/site.yaml`, treats UTC+05:00 as local civil time with no daylight-saving transition, and fetches the exact matching UTC interval from `2024-12-31T19:00:00Z` through `2025-12-31T19:00:00Z` (end exclusive). It validates and writes 8,760 aligned records for all three load-shape assumptions under `outputs/benchmarks/rodina/paired_analysis/`. The resulting correlations and plots describe resource-demand timing only; they are not PV/wind generation, renewable coverage, sizing, or performance estimates.

See [data sources](docs/data_sources.md) for provenance and validation details.

## Scope and status

The engine is suitable for reproducible scenario and dispatch studies when inputs are independently defensible. Cached Open-Meteo access is available, but no measured load dataset is bundled and SteppeGrid does not infer a village's demand. It is not yet suitable for investment decisions, equipment selection, site assessment, or claims about expected performance. See [methodology](docs/methodology.md), [assumptions](docs/assumptions.md), and [roadmap](docs/roadmap.md).

## License

The package metadata declares the MIT License. Add the final project copyright and a `LICENSE` file before public release.
