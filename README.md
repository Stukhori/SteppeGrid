# SteppeGrid

**Renewable Microgrid Planning for Rural Kazakhstan**

SteppeGrid v1.0 is an interactive Streamlit platform for exploring hourly weather, electricity demand, wind–solar–battery design, reliability, and planning economics across seven Kazakhstan settlements.

## What SteppeGrid Does

Weather + Demand → Wind / Solar → Battery Dispatch → Reliability → Optimization → Economics

Normal pages read cached weather and saved results. Only an explicit planner run invokes optimization.

## Kazakhstan Sites

| Site | Region | Annual demand |
|---|---|---:|
| Rodina | Akmola Region | 8.02 GWh/year |
| Shamshi Kaldayakova | Aktobe Region | 0.50 GWh/year |
| Katon-Karagay | East Kazakhstan Region | 2.96 GWh/year |
| Kegen | Almaty Region | 8.00 GWh/year |
| Shayan | Turkistan Region | 8.17 GWh/year |
| Sai-Otes | Mangystau Region | 1.51 GWh/year |
| Togyzkuduk | Karaganda Region | 0.89 GWh/year |

## My Village — Shamshi Kaldayakova

Shamshi Kaldayakova is the featured personal village case, shown with a semantic blue `MY VILLAGE` identity. Its current registered planning demand is 0.50 GWh/year. The standardized 95% design contains 200 kW wind, 347.8 kWdc solar, and 1.03 MWh usable storage. It serves 95.83% of modeled annual electricity, with 549 loss-of-load hours, 139 hours as the longest deficit, $1.84M CAPEX, $2.64M NPC, and $0.15M/year EAC. The standardized 99% design contains 500 kW wind, 298.1 kWdc solar, and 1.54 MWh storage, serving 99.12% at $4.22M NPC.

## Key Results

The frozen Rodina Benchmark selects 2.04 MW wind, 8.30 MWac solar, and 15.42 MWh storage at the 95% annual energy target, with $49.4M NPC. At 99%, it selects 4.98 MW wind, 20.20 MWac solar, and 23.12 MWh storage, with $105.8M NPC. The higher target more than doubles modeled NPC while reducing the longest deficit from 41 to 16 hours.

Cross-village findings use the fourteen frozen standardized Planner V2 scenarios and distinguish the five-site proxy cohort from the Rodina and Shamshi contextual cases.

The frozen standardized cross-village comparison is available in `outputs/phase17/` and can be verified with `uv run python scripts/run_phase17.py --verify`.

## Interactive Planner

Choose a registered or custom site, use registered demand or provide annual/monthly/hourly demand, select a 95% or 99% annual energy served target, choose technologies, review inputs, and run. Session results can be downloaded as JSON or CSV; hosted deployments do not promise permanent scenario storage.

## Architecture

- `steppegrid/`: physical models, dispatch, optimization, economics, registry, and app services
- `data/`: repository-relative site definitions and cached weather
- `outputs/`: frozen benchmark, saved scenarios, and release artifacts
- `app.py`: Streamlit entry point

## Run Locally

Prerequisites: Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Stukhori/SteppeGrid.git
cd SteppeGrid
uv sync --frozen --extra app --extra dev --extra visualization
uv run streamlit run app.py
```

Open `http://localhost:8501` if Streamlit does not open a browser automatically.

## Reproduce Results

See [docs/reproduce_steppegrid.md](docs/reproduce_steppegrid.md).

## Documentation

- [Final technical report](docs/steppegrid_final_report.md)
- [Portfolio summary](docs/steppegrid_portfolio_summary.md)
- [Research abstract](docs/steppegrid_research_abstract.md)
- [Plain-language summary](docs/steppegrid_plain_language_summary.md)
- [Rodina benchmark](docs/benchmarks/rodina.md)

## Validation

```bash
uv run python scripts/run_final_validation.py
uv run pytest
```

Reliability percentages refer to annual energy served, not uptime.
