from pathlib import Path

from streamlit.testing.v1 import AppTest

from steppegrid.benchmarks.phase9 import load_phase9_weather
from steppegrid.planning.generation import PlanningGeneration
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.service import ScenarioPlanningService
from steppegrid.app.planner import result_is_stale

PV_KEY = "trina_tsm_450_neg9r28__sma_core1_stp50_41"


def test_shamshi_explicit_estimate_executes_and_stays_isolated(monkeypatch, tmp_path):
    weather = load_phase9_weather()
    hours = len(weather.series.timestamps)
    generation = PlanningGeneration(
        weather=weather,
        wind_profiles_kwh={"sd6": [100.0] * hours},
        pv_profiles_kwh={PV_KEY: [50.0] * hours},
        wind_metadata={"sd6": {"rated_power_kw": 5.2}},
        pv_metadata={PV_KEY: {"dc_capacity_kw": 49.95, "ac_capacity_kw": 50.0}},
        shear_exponent=0.2,
        shear_terminology="Test ERA5-derived shear; not measured",
    )
    monkeypatch.setattr("steppegrid.planning.service.prepare_generation", lambda *args, **kwargs: generation)
    scenario = PlanningScenario(
        name="Explicit Shamshi estimate",
        site=PlanningSite(
            preset=SitePreset.SHAMSHI, name="Shamshi Kaldayakova",
            latitude=50.578333, longitude=57.544722, timezone_offset="+05:00",
        ),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            annual_kwh=500_000,
            method_notes="Explicit 500 MWh user estimate; not observed demand",
        ),
        reliability_target=0.95,
        technologies=TechnologySelection(wind_keys=("sd6",), pv_keys=(PV_KEY,)),
    )
    run = ScenarioPlanningService(output_root=tmp_path).run(scenario)
    assert run.result.feasible
    assert run.result.demand_source_type is DemandSourceType.SYNTHETIC_ESTIMATE
    assert "not observed demand" in run.result.demand_method
    assert run.result.scenario_input_hash == scenario.input_hash
    assert run.artifacts.directory.parent == tmp_path
    assert len(run.dispatch_rows) == 8760
    assert run.result.metrics.served_fraction >= 0.95


def test_plan_mode_renders_review_without_running_optimizer():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(button for button in app.button if button.label == "Plan").click().run(timeout=90)
    assert app.session_state["app_mode"] == "Plan a System"
    assert not app.exception
    assert {selectbox.label for selectbox in app.selectbox} >= {
        "Site preset", "Demand workflow", "Deterministic hourly shape"
    }
    assert any(button.label == "Run Planner" for button in app.button)
    assert not app.error


def test_shamshi_ui_rejects_missing_estimate_then_reaches_review():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(button for button in app.button if button.label == "Plan").click().run(timeout=90)
    next(box for box in app.selectbox if box.label == "Site preset").set_value("Shamshi Kaldayakova").run(timeout=90)
    assert app.warning
    assert not any(button.label == "Run Planner" for button in app.button)
    next(field for field in app.number_input if field.label == "Estimated annual demand (kWh/year)").set_value(500_000).run(timeout=90)
    assert not app.warning
    assert any(button.label == "Run Planner" for button in app.button)
    assert not app.exception


def test_stale_result_detection_uses_scenario_input_hash():
    scenario = PlanningScenario(
        name="A",
        site=PlanningSite(preset=SitePreset.CUSTOM, name="X", latitude=50, longitude=60),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            annual_kwh=500_000, method_notes="Explicit",
        ),
        reliability_target=0.95,
        technologies=TechnologySelection(wind_keys=("sd6",)),
    )
    changed = scenario.model_copy(update={"reliability_target": 0.99})
    class Result:
        scenario_input_hash = scenario.input_hash
    assert not result_is_stale(Result(), scenario)
    assert result_is_stale(Result(), changed)
