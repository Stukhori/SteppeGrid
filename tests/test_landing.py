from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from steppegrid.app.landing import COPY, _dispatch
from steppegrid.app.product import FEATURED_SITE_ID, latest_result


ROOT = Path(__file__).parents[1]


def test_landing_uses_saved_case_and_language_copy():
    for variants in COPY.values():
        assert len(variants) == 3
        assert all(variants)
    for target in (.95, .99):
        frame = _dispatch(target)
        result = latest_result(FEATURED_SITE_ID, target)
        assert len(frame) == 8760
        assert frame.demand_kwh.sum() == pytest.approx(result["annual_demand_kwh"])
        assert frame.served_energy_kwh.sum() / frame.demand_kwh.sum() == pytest.approx(result["metrics"]["served_fraction"])
        assert frame.battery_soc_end_kwh.min() >= -1e-6
        assert frame.battery_soc_end_kwh.max() <= result["design"]["battery_usable_capacity_kwh"] + 1e-6


def test_landing_switches_saved_target_and_opens_existing_planner():
    app = AppTest.from_file(ROOT / "app.py").run(timeout=90)
    assert not app.exception
    initial = "\n".join(item.value for item in app.markdown)
    assert 'href="#planning-workspace"' in initial
    assert "Shamshi Kaldayakova" in initial
    assert "95.83%" in initial
    assert "Illustrative demand estimate" in initial
    next(control for control in app.segmented_control if control.key == "landing_target").set_value(.99).run(timeout=90)
    assert not app.exception
    changed = "\n".join(item.value for item in app.markdown)
    assert '<div class="sg-lp-served">99.12%</div>' in changed
    assert '500 kW' in changed
    assert changed != initial
    app.button(key="overview_plan_action").click().run(timeout=90)
    assert not app.exception
    assert app.session_state["app_mode"] == "Plan a System"
