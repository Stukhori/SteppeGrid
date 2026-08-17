"""Read-only access to frozen Phase 9--12 artifacts."""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class AppDataError(RuntimeError):
    """A required frozen result is missing or unreadable."""


class FrozenDataRepository:
    """Load final research artifacts without recomputing or mutating them."""

    REQUIRED = {
        "designs": "phase12/final_optimization_table.csv",
        "benchmark": "phase12/final_benchmark_table.csv",
        "reliability": "phase12/final_reliability_table.csv",
        "sensitivity": "phase12/final_sensitivity_table.csv",
        "assumptions": "phase12/assumptions_registry.csv",
        "provenance": "phase12/provenance_manifest.json",
        "audit": "phase12/validation_audit.json",
        "margins": "phase11/robustness_margins.csv",
        "fixed_sensitivity": "phase11/fixed_design_sensitivity.csv",
        "phase11_summary": "phase11/phase11_summary.json",
    }

    def __init__(self, root: str | Path | None = None) -> None:
        project = Path(__file__).resolve().parents[2]
        self.root = Path(root) if root else project / "outputs" / "benchmarks" / "rodina"

    def path(self, key: str) -> Path:
        if key not in self.REQUIRED:
            raise KeyError(key)
        return self.root / self.REQUIRED[key]

    def validate(self) -> None:
        missing = [str(self.path(key)) for key in self.REQUIRED if not self.path(key).is_file()]
        if missing:
            raise AppDataError(
                "Required benchmark outputs are missing. Run "
                "`python scripts/run_phase12.py --mode verify`. Missing: " + ", ".join(missing)
            )

    @lru_cache(maxsize=None)
    def json(self, key: str) -> dict[str, Any]:
        path = self.path(key)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AppDataError(f"Cannot read frozen artifact {path}: {error}") from error

    @lru_cache(maxsize=None)
    def rows(self, key: str) -> tuple[dict[str, str], ...]:
        path = self.path(key)
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return tuple(csv.DictReader(handle))
        except OSError as error:
            raise AppDataError(f"Cannot read frozen artifact {path}: {error}") from error
