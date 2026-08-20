from pathlib import Path
from steppegrid.app.data import FrozenDataRepository
from steppegrid.app.product import FEATURED_SITE_ID, latest_result, site_rows
from steppegrid.app.theme import COLORS, GLOBAL_CSS
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]
def test_seven_production_sites_and_values_load():
    rows=site_rows(SiteRegistry()); assert len(rows)==7
    assert {r["Site"] for r in rows}=={"Rodina","Shamshi Kaldayakova","Katon-Karagay","Kegen","Shayan","Sai-Otes","Togyzkuduk"}
    assert next(r for r in rows if r["site_id"]==FEATURED_SITE_ID)["Annual demand (GWh/year)"]==.5
def test_featured_site_semantics_are_blue_and_textual():
    assert COLORS["featured_site"]=="#2878D8"; assert "--sg-featured-site" in GLOBAL_CSS
    assert "MY VILLAGE" in (ROOT/"app.py").read_text(encoding="utf-8")
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
