import pytest

from steppegrid.app.product import site_rows
from steppegrid.planning.models import DemandSourceType
from steppegrid.sites import SiteRegistry
from steppegrid.sites.models import ProvenanceSourceType


def test_featured_populations_have_distinct_sources_and_preserve_demand():
    registry = SiteRegistry()
    shamshi = registry.get_site("shamshi_kaldayakova")
    rodina = registry.get_site("rodina")
    assert shamshi.population == 4673
    assert shamshi.population_year is None
    source = next(row for row in shamshi.provenance if row.field == "population")
    assert source.source_type is ProvenanceSourceType.USER_PROVIDED
    assert rodina.population == 1184
    assert rodina.population_year == 2024
    source = next(row for row in rodina.provenance if row.field == "population")
    assert source.source_type is ProvenanceSourceType.AUTHORITATIVE_SOURCE
    assert source.source_url == "https://www.gov.kz/org/aqmola-selinograd-rodina/activities/49162"
    assert shamshi.demand_datasets[0].annual_energy_kwh == 500000
    assert shamshi.demand_datasets[0].classification is DemandSourceType.SYNTHETIC_ESTIMATE
    assert rodina.demand_datasets[0].annual_energy_kwh == pytest.approx(8020000)
    rows = {row["site_id"]: row for row in site_rows(registry)}
    assert rows["shamshi_kaldayakova"]["Population"] == 4673
    assert rows["rodina"]["Population"] == 1184
