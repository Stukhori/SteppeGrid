from pathlib import Path
from steppegrid.app.data import FrozenDataRepository
from steppegrid.app.product import FEATURED_SITE_ID, _resource_metrics, latest_result, site_rows, weather_summary
from steppegrid.app.sites import _map_rows
from steppegrid.app.services import PlanningService
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
def test_featured_site_semantics_are_blue_and_textual():
    assert COLORS["featured_site"]=="#2878D8"; assert "--sg-featured-site" in GLOBAL_CSS
    assert "MY VILLAGE" in (ROOT/"app.py").read_text(encoding="utf-8")

def test_overview_renders_the_interactive_site_map():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    overview=text[text.index("def overview"):text.index("def demand_weather")]
    assert 'render_site_map(registry, key="overview_site_map")' in overview

def test_map_distinguishes_my_village_and_supports_selection():
    rows=_map_rows(SiteRegistry())
    featured=next(row for row in rows if row["site_id"]==FEATURED_SITE_ID)
    others=[row for row in rows if row["site_id"]!=FEATURED_SITE_ID]
    assert featured["color"]==[40,120,216,220]
    assert {tuple(row["color"]) for row in others}=={(211,57,57,220)}
    text=(ROOT/"steppegrid/app/sites.py").read_text(encoding="utf-8")
    assert 'on_select="rerun"' in text
    assert 'selection_mode="single-object"' in text
    assert "zoom=7 if selected else 3.15" in text
    assert "Choose a site without using the map" in text
    assert "Reset Kazakhstan view" in text
    assert '"result_95": site["95% result"]' in text
    assert '"radius": 38_000 if row["site_id"] == selected_id' in text

def test_overview_actions_and_compact_layout_are_present():
    app_text=(ROOT/"app.py").read_text(encoding="utf-8")
    theme_text=(ROOT/"steppegrid/app/theme.py").read_text(encoding="utf-8")
    assert 'st.button("Plan a microgrid"' in app_text
    assert 'st.button("Compare saved sites"' in app_text
    assert "@media(max-width:640px)" in theme_text

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
