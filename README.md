# SteppeGrid

SteppeGrid is an open-source research software project for studying renewable-energy resilience in rural Kazakhstan. This repository currently contains the first, deliberately small simulation core: a deterministic hourly model of load, solar PV, empirical wind-turbine output, battery storage, grid availability, curtailment, and unserved energy.

No included inputs are claimed to represent a Kazakh village, a commercial turbine, or HelixGen. The bundled scenario and turbine curve are synthetic demonstration data.

## Current architecture

```text
steppegrid/
  simulation/       typed domain models, component equations, dispatch, metrics
  examples/         explicitly synthetic input construction
  cli.py            24-hour demonstration
data/
  weather/          future validated weather inputs
  load_profiles/    future measured or sourced load inputs
  turbine_curves/   future source-attributed empirical curves
docs/               methodology, assumptions, and roadmap
tests/              deterministic unit and system tests
```

Data ingestion is intentionally absent from the simulation package. Future importers should validate and convert external sources into the domain models rather than placing parsing logic in the physical model.

## Install and run

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
python -m steppegrid.cli
```

The demo prints aggregate metrics for one synthetic day. Library use begins with a validated `SimulationInput` and `steppegrid.simulation.simulate()`.

## Scope and status

The present engine is suitable for checking dispatch logic and energy accounting. It is not yet suitable for investment decisions, equipment selection, site assessment, or claims about expected performance. See [methodology](docs/methodology.md), [assumptions](docs/assumptions.md), and [roadmap](docs/roadmap.md).

## License

The package metadata declares the MIT License. Add the final project copyright and a `LICENSE` file before public release.
