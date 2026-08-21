"""Verify that a clean checkout contains every file used by the Streamlit app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BENCHMARK_FILES = (
    "outputs/benchmarks/rodina/phase11/fixed_design_sensitivity.csv",
    "outputs/benchmarks/rodina/phase11/phase11_summary.json",
    "outputs/benchmarks/rodina/phase11/robustness_margins.csv",
    "outputs/benchmarks/rodina/phase12/assumptions_registry.csv",
    "outputs/benchmarks/rodina/phase12/final_benchmark_table.csv",
    "outputs/benchmarks/rodina/phase12/final_optimization_table.csv",
    "outputs/benchmarks/rodina/phase12/final_reliability_table.csv",
    "outputs/benchmarks/rodina/phase12/final_sensitivity_table.csv",
    "outputs/benchmarks/rodina/phase12/provenance_manifest.json",
    "outputs/benchmarks/rodina/phase12/validation_audit.json",
)
PRODUCT_FILES = (
    "app.py",
    ".streamlit/config.toml",
    "uv.lock",
    "outputs/phase17/site_resource_metrics.csv",
    "outputs/phase17/normalized_metrics.csv",
    "outputs/phase17/reliability_escalation.csv",
)


def deployment_asset_errors(root: Path) -> list[str]:
    """Return actionable problems found in the deployment asset package."""
    errors = [f"missing required file: {path}" for path in (*PRODUCT_FILES, *BENCHMARK_FILES)
              if not (root / path).is_file()]

    manifest_path = root / "outputs/benchmarks/rodina/phase12/provenance_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cached_inputs = manifest["weather"]["cached_inputs"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            errors.append(f"invalid provenance manifest: {error}")
        else:
            for entry in cached_inputs:
                relative = Path(str(entry.get("path", "")).replace("\\", "/"))
                if not relative.as_posix() or not (root / relative).is_file():
                    errors.append(f"missing provenance-listed weather file: {relative.as_posix()}")

    result_files = tuple((root / "outputs/phase17/standardized_runs").glob("**/result.json"))
    if len(result_files) != 14:
        errors.append(f"expected 14 standardized result files, found {len(result_files)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = deployment_asset_errors(args.root.resolve())
    if errors:
        print("SteppeGrid deployment asset check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SteppeGrid deployment assets are complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
