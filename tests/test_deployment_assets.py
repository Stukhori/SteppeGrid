from pathlib import Path

from scripts.check_deployment_assets import deployment_asset_errors


ROOT = Path(__file__).resolve().parents[1]


def test_repository_contains_complete_deployment_package():
    assert deployment_asset_errors(ROOT) == []


def test_checker_reports_actionable_errors_for_empty_checkout():
    errors = deployment_asset_errors(ROOT / "tests" / "__missing_deployment_root__")
    assert "missing required file: app.py" in errors
    assert "missing required file: outputs/benchmarks/rodina/phase12/provenance_manifest.json" in errors
    assert "expected 14 standardized result files, found 0" in errors
