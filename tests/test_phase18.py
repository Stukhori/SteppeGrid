from pathlib import Path
from streamlit.testing.v1 import AppTest
from steppegrid.app.data import FrozenDataRepository
from steppegrid.app.product import FEATURED_SITE_ID, _resource_metrics, latest_result, site_rows, weather_summary
from steppegrid.app.sites import _map_rows
from steppegrid.app.services import PlanningService
from steppegrid.app.state import PAGES, PRIMARY_DESTINATIONS, RESEARCH_PAGES
from steppegrid.app.theme import COLORS, GLOBAL_CSS
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]
def test_seven_production_sites_and_values_load():
    rows=site_rows(SiteRegistry()); assert len(rows)==7
    assert {r["Site"] for r in rows}=={"Rodina","Shamshi Kaldayakova","Katon-Karagay","Kegen","Shayan","Sai-Otes","Togyzkuduk"}
    assert next(r for r in rows if r["site_id"]==FEATURED_SITE_ID)["Annual demand (GWh/year)"]==.5

def test_resource_summaries_reuse_the_frozen_table():
    registry=SiteRegistry(); _resource_metrics.cache_clear()
    assert weather_summary(registry.get_site("rodina"))["hours"]==8760
    assert weather_summary(registry.get_site(FEATURED_SITE_ID))["hours"]==8760
    assert _resource_metrics.cache_info().misses==1
    assert _resource_metrics.cache_info().hits==1
def test_featured_site_semantics_are_amber_and_textual():
    assert COLORS["featured_site"]=="#DFA52F"; assert "--sg-amber" in GLOBAL_CSS
    assert "My Village" in (ROOT/"steppegrid/app/sites.py").read_text(encoding="utf-8")

def test_overview_renders_the_interactive_site_map():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    overview=text[text.index("def overview"):text.index("def demand_weather")]
    assert 'render_site_map(registry, key="overview_site_map")' in overview

def test_map_distinguishes_my_village_and_supports_selection():
    rows=_map_rows(SiteRegistry())
    featured=next(row for row in rows if row["site_id"]==FEATURED_SITE_ID)
    others=[row for row in rows if row["site_id"]!=FEATURED_SITE_ID]
    assert featured["color"]==[223,165,47,235]
    assert {tuple(row["color"]) for row in others}=={(13,118,100,220)}
    text=(ROOT/"steppegrid/app/sites.py").read_text(encoding="utf-8")
    assert 'on_select="rerun"' in text
    assert 'selection_mode="single-object"' in text
    assert "zoom=7 if is_focused else 3.15" in text
    assert '"Village"' in text
    assert "Reset Kazakhstan view" in text
    assert '"result_95": site["95% result"]' in text
    assert '"radius": 38_000 if row["site_id"] == selected_id' in text

def test_overview_actions_and_compact_layout_are_present():
    app_text=(ROOT/"app.py").read_text(encoding="utf-8")
    theme_text=(ROOT/"steppegrid/app/theme.py").read_text(encoding="utf-8")
    assert 'st.button("Build a village scenario"' in app_text
    assert 'st.button("Compare village results"' in app_text
    assert "@media(max-width:600px)" in theme_text

def test_visual_system_includes_schematic_focus_and_map_guidance():
    components=(ROOT/"steppegrid/app/components.py").read_text(encoding="utf-8")
    sites=(ROOT/"steppegrid/app/sites.py").read_text(encoding="utf-8")
    theme=(ROOT/"steppegrid/app/theme.py").read_text(encoding="utf-8")
    assert 'class="sg-overview-intro"' in components
    assert 'class="sg-schematic"' in components
    assert 'aria-label="Energy flows from wind and solar generation' in components
    assert 'class="sg-map-legend"' in sites
    assert ":focus-visible" in theme
    assert ".sg-map-dot--featured{background:var(--sg-amber)}" in theme
    assert ".sg-map-dot--site{background:var(--sg-primary)}" in theme

def test_horizontal_navigation_replaces_sidebar_and_keeps_routes():
    app_text=(ROOT/"app.py").read_text(encoding="utf-8")
    theme=(ROOT/"steppegrid/app/theme.py").read_text(encoding="utf-8")
    assert PRIMARY_DESTINATIONS == ("Overview", "Sites", "Plan a System", "Compare", "Research")
    assert set(RESEARCH_PAGES) == set(PAGES) - {"Overview"}
    assert "with st.sidebar:" not in app_text
    assert 'initial_sidebar_state="collapsed"' in app_text
    assert 'st.segmented_control(' in app_text
    assert 'button[role="radio"][data-selected="true"]' in theme
    assert 'button[role="radio"][data-selected="true"] p' in theme
    assert 'button[role="radio"][data-selected="true"]:hover:not(:disabled)' in theme
    assert '[data-testid="stButtonGroup"]' in theme
    assert "color:#FFFFFF!important" in theme

def test_wide_workspace_and_responsive_breakpoints_are_explicit():
    theme=(ROOT/"steppegrid/app/theme.py").read_text(encoding="utf-8")
    assert "width:min(92vw,1560px)" in theme
    assert "@media(max-width:900px)" in theme
    assert "@media(max-width:600px)" in theme
    assert "overflow-x:hidden" in theme

def test_no_heavy_dashboard_dependency_was_added():
    project=(ROOT/"pyproject.toml").read_text(encoding="utf-8").lower()
    lock=(ROOT/"uv.lock").read_text(encoding="utf-8").lower()
    assert "streamlit-elements" not in project
    assert "streamlit-shadcn-ui" not in project
    assert 'name = "streamlit-elements"' not in lock
    assert 'name = "streamlit-shadcn-ui"' not in lock

def _contrast(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels=[int(color[index:index+2],16)/255 for index in (1,3,5)]
        linear=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in channels]
        return .2126*linear[0]+.7152*linear[1]+.0722*linear[2]
    first,second=luminance(foreground),luminance(background)
    return (max(first,second)+.05)/(min(first,second)+.05)

def test_core_text_pairs_meet_wcag_aa_contrast():
    assert _contrast("#FFFFFF","#0D7664")>=4.5
    assert _contrast("#102D35","#DFA52F")>=4.5
    assert _contrast("#5B6E73","#F6F2E8")>=4.5
    assert _contrast("#142A31","#FFFDF8")>=4.5

def test_all_primary_destinations_render_from_horizontal_navigation():
    app=AppTest.from_file(ROOT/"app.py").run(timeout=90)
    expected_modes={"Overview":"Explore Benchmark","Sites":"Sites","Plan a System":"Plan a System","Compare":"Compare Sites","Research":"Explore Benchmark"}
    for destination in PRIMARY_DESTINATIONS:
        next(control for control in app.segmented_control if control.label=="Primary navigation").set_value(destination).run(timeout=120)
        assert app.session_state["app_mode"]==expected_modes[destination]
        assert not app.exception

def test_public_site_and_compare_views_hide_lineage_fields():
    columns=set(site_rows(SiteRegistry())[0])
    assert "Demand evidence" not in columns; assert "Demand confidence" not in columns
def test_methodology_has_no_dedicated_limitations_section():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    body=text[text.index("def methodology"):text.index("ROUTES =")]
    assert "Scientific limitations" not in body; assert "How SteppeGrid Works" in body
def test_internal_lineage_is_retained():
    registry=SiteRegistry()
    for site in registry.list_sites():
        assert site.provenance and site.metadata_hash
        assert site.weather_datasets[0].sha256
        assert site.demand_datasets[0].demand_sha256 and site.demand_datasets[0].provenance
def test_shamshi_saved_result_and_product_artifacts():
    assert latest_result(FEATURED_SITE_ID,.95)["metrics"]["served_fraction"]>.95
    assert latest_result(FEATURED_SITE_ID,.99)["metrics"]["served_fraction"]>.99
    assert (ROOT/"docs/steppegrid_final_report.md").is_file()

def test_final_release_packages_are_complete():
    tables={p.name for p in (ROOT/"outputs/final/tables").glob("*.csv")}
    assert {"site_summary.csv","results_95.csv","results_99.csv","normalized_comparison.csv","reliability_escalation.csv","key_findings.csv"}<=tables
    assert len(list((ROOT/"outputs/final/figures").glob("*.png")))==10

def test_deployed_app_packages_required_benchmark_artifacts():
    repository=FrozenDataRepository()
    repository.validate()
    assert all(repository.path(key).is_file() for key in repository.REQUIRED)
    assert len(PlanningService().demand_weather_frame("residential_like"))==8760
