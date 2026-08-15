# SteppeGrid

SteppeGrid is an open-source research software project for studying renewable-energy resilience in rural Kazakhstan. It provides a deterministic hourly model of load, solar PV, empirical wind-turbine output, battery storage, grid availability, curtailment, and unserved energy. Location-aware scenarios can use strict hourly CSV weather or a deterministic synthetic provider.

No included inputs are claimed to represent a Kazakh village, a commercial turbine, or HelixGen. The bundled scenario and turbine curve are synthetic demonstration data.

## Current architecture

```text
steppegrid/
  simulation/       typed domain models, component equations, dispatch, metrics
  weather/          provider interface and normalized synthetic/CSV providers
  data/             source-data loaders such as turbine-curve CSV parsing
  examples/         explicitly synthetic input construction
  scenario.py       serializable YAML/JSON scenario resolution
  export.py         hourly result CSV export
  visualize.py      optional diagnostic plotting
  cli.py            scenario CLI and legacy synthetic demonstration
data/
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

The old `python -m steppegrid.cli` command remains a quick synthetic demo. Scenario-relative CSV paths are resolved relative to the scenario file.

Optional diagnostic plots are isolated from the engine:

```powershell
python -m pip install -e ".[visualization]"
python -m steppegrid.visualize outputs/hourly.csv --output outputs/diagnostics.png
```

## Input CSV schemas

Weather CSV columns must be exactly:

```text
timestamp,wind_speed_m_s,solar_irradiance_w_m2,temperature_c
```

Timestamps use ISO 8601 and must be unique, chronological, and consecutive hourly values. Missing fields and invalid values are errors; no interpolation occurs. Turbine curve columns must be exactly:

```text
wind_speed_m_s,power_kw
```

See [data sources](docs/data_sources.md) for provenance and validation details.

## Scope and status

The engine is suitable for reproducible scenario and dispatch studies when inputs are independently defensible. No external historical weather API or measured dataset is bundled. It is not yet suitable for investment decisions, equipment selection, site assessment, or claims about expected performance. See [methodology](docs/methodology.md), [assumptions](docs/assumptions.md), and [roadmap](docs/roadmap.md).

## License

The package metadata declares the MIT License. Add the final project copyright and a `LICENSE` file before public release.
