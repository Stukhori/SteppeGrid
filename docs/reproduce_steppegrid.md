# Reproduce SteppeGrid v1.0

This is the authoritative reproduction guide. Historical phase documents remain as technical records.

## Install

From the repository root:

```bash
uv sync --extra app --extra dev --extra visualization
```

## Verify benchmark

```bash
uv run python scripts/run_phase12.py --mode verify
```

This checks the frozen Rodina artifacts without changing the selected designs.

## Reproduce comparative analysis

The public comparison reads saved results and never optimizes on page load. Rebuild release tables and figures with:

```bash
uv run python scripts/build_final_artifacts.py
```

When a complete compatible cross-village result package is not present, the build records unavailable values rather than estimating winners.

## Launch application

```bash
uv run streamlit run app.py
```

## Run planner

Open **Plan a System**, then complete Site → Demand → Reliability → Technologies → Review → Results. Optimization starts only after **Run Planner** is pressed.

## Outputs

- `outputs/final/figures/`: publication figures
- `outputs/final/tables/`: public result tables
- `outputs/final/final_validation.json`: release checks
- `outputs/sites/<site>/scenarios/<id>/`: persisted local runs when supported

Hosted session results remain downloadable, but permanent server storage is not guaranteed.

## Final validation

```bash
uv run python scripts/run_final_validation.py
uv run pytest
```
