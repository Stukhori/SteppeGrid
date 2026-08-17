from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from steppegrid.app.charts import date_window, preset_dates, sensitivity_chart
from steppegrid.app.components import GLOSSARY, design_comparison_rows
from steppegrid.app.services import PlanningService
from steppegrid.app.state import NAVIGATION, PAGES, SHAMSHI_STATUS
from steppegrid.app.theme import COLORS


def test_navigation_hierarchy_contains_every_page_once():
    grouped = tuple(page for pages in NAVIGATION.values() for page in pages)
    assert tuple(NAVIGATION) == ("Study", "Planning", "Analysis", "Research")
    assert grouped == PAGES
    assert len(set(grouped)) == len(PAGES)


def test_semantic_palette_and_glossary_cover_core_concepts():
    assert {"wind", "solar", "storage", "served", "unmet", "curtailment", "success", "caution", "critical"} <= COLORS.keys()
    assert COLORS["wind"] != COLORS["solar"] != COLORS["storage"]
    assert {"served_energy", "lpsp", "lolh", "npc", "eac", "curtailment", "capacity_factor", "poa", "binding_profile"} == GLOSSARY.keys()
    assert "not the percentage of uninterrupted hours" in GLOSSARY["served_energy"]
    assert "No default electricity demand is assumed" in SHAMSHI_STATUS
    assert "estimated-demand planning scenarios" in SHAMSHI_STATUS


def test_design_comparison_is_calculated_from_frozen_values():
    service = PlanningService()
    rows = {row["Measure"]: row for row in design_comparison_rows(service.design(0.95), service.design(0.99))}
    assert rows["Wind capacity"] == {"Measure": "Wind capacity", "95%": "2.04 MW", "99%": "4.98 MW", "Change": "+143.5%"}
    assert rows["Net present cost"]["95%"] == "$49.38M"
    assert rows["Net present cost"]["99%"] == "$105.79M"
    assert rows["Loss-of-load hours"]["Change"] == "-79.5%"


def test_dispatch_date_filters_and_presets_are_data_driven():
    timestamps = pd.date_range("2025-01-01", periods=240, freq="h", tz="Asia/Almaty")
    frame = pd.DataFrame({"timestamp": timestamps, "curtailment_kwh": [0.0] * 120 + [9.0] + [0.0] * 119})
    selected = date_window(frame, date(2025, 1, 2), date(2025, 1, 3))
    assert selected["timestamp"].dt.date.min() == date(2025, 1, 2)
    assert selected["timestamp"].dt.date.max() == date(2025, 1, 3)
    start, end = preset_dates(frame, "Highest-curtailment week")
    peak = timestamps[120].date()
    assert start == peak - timedelta(days=3)
    assert end == peak + timedelta(days=3)


def test_sensitivity_chart_contains_threshold_and_text_status():
    frame = pd.DataFrame(PlanningService().fixed_sensitivity_rows(0.99))
    spec = sensitivity_chart(frame, 0.99).to_dict()
    serialized = str(spec)
    assert "99% threshold" in serialized
    assert "MEETS TARGET" in serialized
    assert "BELOW TARGET" in serialized


def test_deficit_events_reconcile_to_existing_reliability_outputs():
    service = PlanningService()
    for target, profile in ((0.95, "residential_like"), (0.99, "flat_within_month")):
        events = service.deficit_events(target, profile)
        reliability = next(row for row in service.reliability_rows(target) if row["load_profile"] == profile)
        assert events["duration_hours"].sum() == reliability["loss_of_load_hours"]
        assert events["duration_hours"].max() == reliability["longest_deficit_hours"]
        assert events["unmet_energy_kwh"].sum() == pytest.approx(reliability["unmet_energy_kwh"], abs=1e-6)


def test_all_pages_and_primary_interactions_render():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=60)
    for page in PAGES:
        app.session_state["active_page"] = page
        app.run(timeout=150)
        assert not app.exception, (page, [item.value for item in app.exception])
        assert not app.error, (page, [item.value for item in app.error])

    app.session_state["active_page"] = "System Design"
    app.run(timeout=150)
    app.segmented_control[0].set_value("99% annual served-energy target").run(timeout=150)
    app.selectbox[0].set_value("Flat within month").run(timeout=150)
    assert app.segmented_control[0].value == "99% annual served-energy target"
    assert app.selectbox[0].value == "Flat within month"

    app.session_state["active_page"] = "Sensitivity"
    app.run(timeout=60)
    app.segmented_control[0].set_value("99% annual served-energy target").run(timeout=60)
    app.selectbox[0].set_value("Resource Stress").run(timeout=60)
    assert app.selectbox[0].value == "resource_stress"
    assert not app.exception
