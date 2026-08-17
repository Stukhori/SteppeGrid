from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from steppegrid.app.sites import _site_rows
from steppegrid.planning.models import DemandSourceType
from steppegrid.simulation.models import Location
from steppegrid.sites import PlanningReadiness, SiteRegistry, WeatherStatus
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider, REQUESTED_VARIABLES

POPULATED = {
    "katon_karagay": ((49.17466, 85.59937), 3_700, 2_963_855.701579716),
    "kegen": ((43.014513, 79.226383), 9_993, 8_004_813.520509757),
    "shayan": ((43.03231, 69.38075), 10_200, 8_170_629.231381919),
    "sai_otes": ((44.32771, 53.53314), 1_880, 1_505_959.113235099),
    "togyzkuduk": ((49.88107, 73.57845), 1_110, 889_156.7104739148),
}


def test_all_real_planning_sites_are_unique_registered_and_provenanced():
    registry = SiteRegistry()
    sites = registry.list_sites()
    assert {site.site_id for site in sites} == {
        "rodina", "shamshi_kaldayakova", *POPULATED
    }
    assert len({site.site_id for site in sites}) == len(sites)
    assert len({(site.name, site.latitude, site.longitude) for site in sites}) == len(sites)
    for site_id, (coordinates, population, _) in POPULATED.items():
        site = registry.get_site(site_id)
        assert (site.latitude, site.longitude) == coordinates
        assert site.population == population
        assert site.population_is_approximate
        assert any(source.field == "population" and source.source_url for source in site.provenance)
        assert site.timezone_offset == "+05:00"


def test_kz_rural_proxy_v1_is_explicit_and_conserved_hourly():
    registry = SiteRegistry()
    method = registry.get_demand_methodology("kz_rural_proxy_v1")
    assert method.rural_household_electricity_gwh == 4_827.4
    assert method.rural_population == 7_533_000
    assert method.household_kwh_per_capita == pytest.approx(640.8336652064251)
    assert method.community_service_multiplier == 1.25
    assert method.planning_kwh_per_capita == pytest.approx(801.0420815080313)
    assert method.classification is DemandSourceType.PROXY_DERIVED
    assert method.profile_shape == "community_facility_like"

    for site_id, (_, population, expected_annual) in POPULATED.items():
        datasets = registry.list_demand_datasets(site_id)
        assert len(datasets) == 1
        dataset = datasets[0]
        assert dataset.demand_id == "proxy_rural_community_v1"
        assert dataset.classification is DemandSourceType.PROXY_DERIVED
        assert dataset.classification is not DemandSourceType.MEASURED
        assert dataset.profile_shape == "community_facility_like"
        assert dataset.proxy_calculation is not None
        assert dataset.proxy_calculation.methodology_id == "kz_rural_proxy_v1"
        assert dataset.proxy_calculation.population_basis == population
        assert dataset.annual_energy_kwh == pytest.approx(expected_annual)
        trace = registry.build_demand(site_id, dataset.demand_id)
        assert len(trace.timestamps) == 8_760
        assert all(value >= 0 for value in trace.demand_kwh)
        assert math.fsum(trace.demand_kwh) == pytest.approx(expected_annual, abs=1e-6)


def test_populated_weather_caches_are_complete_and_sites_are_ready():
    registry = SiteRegistry()
    provider = OpenMeteoHistoricalWeatherProvider(cache_root=registry.cache_root)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for site_id in POPULATED:
        site = registry.get_site(site_id)
        assert registry.get_weather_status(site_id) is WeatherStatus.CACHED
        assert registry.get_planning_readiness(site_id) is PlanningReadiness.READY_FOR_PLANNING
        reference = next(item for item in site.weather_datasets if item.year == 2025)
        assert set(reference.variables) == set(REQUESTED_VARIABLES)
        dataset = provider.get_hourly_weather(
            Location(
                name=site.name,
                latitude=site.latitude,
                longitude=site.longitude,
                country=site.country,
            ),
            start,
            end,
        )
        assert dataset.provenance.cache_status == "HIT"
        assert len(dataset.series.timestamps) == 8_760
        assert len(set(dataset.series.timestamps)) == 8_760


def test_registry_drives_production_site_table_and_population_audit():
    registry = SiteRegistry()
    rows = _site_rows(registry)
    assert {row["Site ID"] for row in rows} == {
        "rodina", "shamshi_kaldayakova", *POPULATED
    }
    for row in rows:
        if row["Site ID"] in POPULATED:
            assert row["Classification"] == "PLANNING_SITE"
            assert row["Demand evidence"] == "Proxy-derived demand"
            assert row["Population"].startswith("~")
            assert row["Weather"] == "CACHED"
            assert row["Planning"] == "READY_FOR_PLANNING"

    audit = registry.populated_sites_audit()
    assert audit.blockers == 0
    assert {item.site_id for item in audit.sites} == set(POPULATED)
    assert all(item.weather_status is WeatherStatus.CACHED for item in audit.sites)
    assert all(item.demand_classification is DemandSourceType.PROXY_DERIVED for item in audit.sites)


def test_production_ui_does_not_call_real_sites_test_demo_or_fake_villages():
    root = Path(__file__).parents[1]
    production_ui = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "app.py", *(root / "steppegrid" / "app").glob("*.py"))
    ).lower()
    for forbidden in ("test village", "demo village", "fake site"):
        assert forbidden not in production_ui


def test_rodina_and_shamshi_registry_evidence_remains_frozen():
    registry = SiteRegistry()
    rodina = registry.get_site("rodina")
    shamshi = registry.get_site("shamshi_kaldayakova")
    assert rodina.demand_datasets[0].demand_sha256 == "331983aa57dc786a0fb6adca4f8fe3fe4a68d8d271e42044f1ea9c64851705fd"
    assert rodina.weather_datasets[0].sha256 == "dea975f31577ef2674e95c97a2d89c9aaaa1cdc03f65607dbfd965004a6ef396"
    assert shamshi.demand_datasets[0].demand_sha256 == "5b998ba8ab9eeda1e796791f16098e9f359e0e1dd7e1bcc5bcb64b64f3ec7864"
    assert shamshi.weather_datasets[0].sha256 == "8be8d01745afd271fd51f6ba341e15bf3b3519fbdd36ff227f2a006572ffb5b3"
