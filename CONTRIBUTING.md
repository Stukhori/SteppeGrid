# Contributing to SteppeGrid

Thank you for helping improve SteppeGrid. Contributions should preserve the
project's reproducibility, explicit assumptions, and distinction between
measured, reconstructed, proxy, and synthetic data.

## Development setup

```bash
git clone https://github.com/Stukhori/SteppeGrid.git
cd SteppeGrid
uv sync --frozen --extra app --extra dev --extra visualization
```

Create a focused branch and keep each commit limited to one coherent change.

## Validation

Run the test suite before opening a pull request:

```bash
uv run pytest
```

Changes to release artifacts or cross-village results should also run:

```bash
uv run python scripts/run_final_validation.py
uv run python scripts/run_phase17.py --verify
```

## Pull requests

Describe the motivation, implementation, user impact, and validation performed.
Do not commit secrets, local caches, virtual environments, or generated outputs
that are intentionally excluded by `.gitignore`. Document new assumptions and
data provenance alongside any modeling change.
