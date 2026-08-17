from pathlib import Path

import pytest

from steppegrid.benchmarks.phase12 import assumptions_registry, run_phase12


@pytest.fixture(scope="module")
def verified():
    return run_phase12(mode="verify",write_outputs=False)


def test_provenance_has_frozen_rodina_identity(verified):
    manifest=verified["manifest"]
    assert manifest["site"]=={"name":"Rodina","region":"Akmola Region","country":"Kazakhstan",
      "latitude":51.302445,"longitude":70.541645,"timezone":"UTC+05:00","reference_year":2025}
    assert manifest["weather"]["records"]==8760
    assert manifest["software"]["repository_test_count_at_phase12"]==167
    assert manifest["demand"]["printed_annual_kwh"]==7720000
    assert manifest["demand"]["monthly_rows_reconstructed_annual_kwh"]==8020000
    assert "not measured" in manifest["demand"]["status"]


def test_time_series_and_frozen_results_pass(verified):
    checks={row["check"]:row for row in verified["audit"]}
    assert checks["8760_aligned_hours"]["status"]=="PASS"
    assert checks["unique_consecutive_weather"]["status"]=="PASS"
    assert checks["annual_total"]["status"]=="PASS"
    assert checks["selected_design_0.95"]["status"]=="PASS"
    assert checks["selected_design_0.99"]["status"]=="PASS"
    assert verified["blockers"]==0


def test_assumption_classifications_are_explicit():
    rows={row["input"]:row for row in assumptions_registry()}
    assert rows["Rodina printed annual load"]["classification"]=="SOURCE_REPORTED"
    assert rows["Rodina optimization annual load"]["classification"]=="SOURCE_RECONSTRUCTED"
    assert rows["Nominal wind shear alpha"]["classification"]=="ERA5_DERIVED"
    assert rows["Demand sensitivity"]["classification"]=="RESEARCH_SENSITIVITY_SCENARIO"


def test_semantic_safeguards(verified):
    manifest=verified["manifest"]
    assert manifest["optimization"]["target_definition"]=="annual served-energy fraction, not uptime"
    assert manifest["sensitivity"]["full_reoptimization_performed"] is False
    assert "not confidence intervals" in manifest["sensitivity"]["scenario_type"]
    assert not list(Path("outputs").glob("**/*shamshi*optim*"))


def test_corrected_combined_shear_direction(verified):
    scenarios={row["name"]:row for row in verified["manifest"]["sensitivity"]["scenarios"]}
    assert scenarios["resource_stress"]["wind_shear_alpha"] > scenarios["nominal"]["wind_shear_alpha"]
    assert scenarios["resource_favorable"]["wind_shear_alpha"] < scenarios["nominal"]["wind_shear_alpha"]
