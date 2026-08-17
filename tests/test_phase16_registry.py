import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from steppegrid.planning.models import DemandSourceType
from steppegrid.sites import (
    PlanningReadiness,
    SiteClassification,
    SiteOrigin,
    SiteRegistry,
    SiteRegistryError,
    VillageSite,
    WeatherDatasetRef,
    WeatherStatus,
    suggest_site_id,
)


def _registry(tmp_path):
    return SiteRegistry(tmp_path / "sites", output_root=tmp_path / "outputs")


def _onboard(registry, site_id="test_village_north"):
    return registry.onboard_site(
        site_id=site_id, name="Test Village North", region="Synthetic Test Region",
        country="Kazakhstan", latitude=50.578333, longitude=57.544722,
        timezone_name="Asia/Aqtobe", source_name="Test fixture",
    )


def test_site_model_serialization_ids_coordinates_and_timezone(tmp_path):
    registry = _registry(tmp_path)
    site = _onboard(registry)
    restored = VillageSite.model_validate_json(registry.export_site(site.site_id))
    assert restored == site
    assert restored.metadata_hash == site.metadata_hash
    assert suggest_site_id("Aul № 7 / North") == "aul_7_north"
    with pytest.raises(ValidationError):
        site.model_copy(update={"site_id": "Not Safe"}).model_validate(site.model_copy(update={"site_id": "Not Safe"}).model_dump())
    with pytest.raises((ValidationError, ValueError)):
        VillageSite.model_validate({**site.model_dump(), "latitude": 91})
    with pytest.raises((ValidationError, ValueError)):
        VillageSite.model_validate({**site.model_dump(), "timezone": "Not/A_Timezone"})


def test_duplicate_ids_and_built_in_mutation_are_rejected(tmp_path):
    registry = _registry(tmp_path)
    site = _onboard(registry)
    with pytest.raises(SiteRegistryError, match="duplicate site_id"):
        registry.register_site(site)
    with pytest.raises(SiteRegistryError, match="only USER_REGISTERED"):
        registry.register_site(site.model_copy(update={"origin": SiteOrigin.BUILT_IN}))

    builtin_root = tmp_path / "protected" / "builtin" / "fixed"
    builtin_root.mkdir(parents=True)
    builtin = site.model_copy(update={"site_id": "fixed", "origin": SiteOrigin.BUILT_IN})
    (builtin_root / "site.json").write_text(json.dumps(builtin.model_dump(mode="json")), encoding="utf-8")
    protected = SiteRegistry(tmp_path / "protected")
    with pytest.raises(SiteRegistryError, match="read-only"):
        protected.update_site_metadata("fixed", name="Changed")
    with pytest.raises(SiteRegistryError, match="cannot be removed"):
        protected.remove_site("fixed")


def test_user_persistence_removal_and_coordinate_weather_invalidation(tmp_path):
    registry = _registry(tmp_path)
    site = _onboard(registry)
    weather = WeatherDatasetRef(
        weather_id="era5_2025", source="Open-Meteo", model="ERA5", year=2025,
        status=WeatherStatus.CACHED, variables=("wind_speed_100m",),
        start_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        latitude=site.latitude, longitude=site.longitude,
        cache_key="a" * 64, path=str(tmp_path / "missing.csv"),
        metadata_path=str(tmp_path / "missing.json"), sha256="b" * 64,
    )
    registry._write_user_site(site.model_copy(update={"weather_datasets": (weather,)}))
    changed = registry.update_site_metadata(site.site_id, latitude=50.6)
    assert changed.weather_datasets[0].status is WeatherStatus.STALE
    assert registry.get_planning_readiness(site.site_id) is PlanningReadiness.WEATHER_MISSING
    assert SiteRegistry(registry.root).get_site(site.site_id).latitude == 50.6
    registry.remove_site(site.site_id)
    with pytest.raises(SiteRegistryError, match="unknown site_id"):
        registry.get_site(site.site_id)


def test_missing_referenced_files_are_a_registry_blocker(tmp_path):
    registry = _registry(tmp_path)
    site = _onboard(registry)
    weather = WeatherDatasetRef(
        weather_id="era5_2025", source="Open-Meteo", model="ERA5", year=2025,
        status=WeatherStatus.CACHED, variables=("wind_speed_100m",),
        start_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        latitude=site.latitude, longitude=site.longitude,
        cache_key="a" * 64, path=str(tmp_path / "missing.csv"),
        metadata_path=str(tmp_path / "missing.json"), sha256="b" * 64,
    )
    registry._write_user_site(site.model_copy(update={"weather_datasets": (weather,)}))
    audit = registry.validate_registry()
    assert audit.blockers >= 2
    assert registry.get_planning_readiness(site.site_id) is PlanningReadiness.INVALID


def test_builtin_rodina_and_shamshi_registry_metadata_is_faithful():
    registry = SiteRegistry()
    rodina = registry.get_site("rodina")
    assert (rodina.latitude, rodina.longitude) == (51.302445, 70.541645)
    assert rodina.timezone_offset == "+05:00"
    assert rodina.classification is SiteClassification.BENCHMARK
    assert rodina.weather_datasets[0].year == 2025
    assert rodina.demand_datasets[0].classification is DemandSourceType.SOURCE_RECONSTRUCTED
    assert rodina.demand_datasets[0].annual_energy_kwh == 8_020_000
    assert registry.get_planning_readiness("rodina") is PlanningReadiness.BENCHMARK_READY

    shamshi = registry.get_site("shamshi_kaldayakova")
    assert (shamshi.latitude, shamshi.longitude) == (50.578333, 57.544722)
    assert shamshi.region == "Aktobe Region"
    assert shamshi.classification is SiteClassification.FIELD_CASE
    assert shamshi.demand_datasets[0].classification is DemandSourceType.SYNTHETIC_ESTIMATE
    assert registry.get_planning_readiness(shamshi.site_id) is PlanningReadiness.READY_FOR_PLANNING
    audit = registry.validate_registry()
    assert (audit.registered_sites, audit.valid_sites, audit.blockers, audit.warnings) == (2, 2, 0, 1)


def test_multiple_versioned_demand_datasets_coexist_and_hash_differ(tmp_path):
    registry = _registry(tmp_path)
    site = _onboard(registry)
    first = registry.create_annual_demand_dataset(
        site.site_id, demand_id="estimate_v1", name="Estimate v1", annual_kwh=30_000,
    )
    second = registry.create_annual_demand_dataset(
        site.site_id, demand_id="estimate_v2", name="Estimate v2", annual_kwh=40_000,
    )
    monthly = registry.create_monthly_demand_dataset(
        site.site_id, demand_id="monthly_v1", name="Monthly v1",
        monthly_kwh=(3_000.0,) * 12,
    )
    trace = registry.build_demand(site.site_id, first.demand_id)
    payload = ("timestamp,demand_kwh\n" + "\n".join(
        f"{timestamp.isoformat()},{value:.12g}"
        for timestamp, value in zip(trace.timestamps, trace.demand_kwh, strict=True)
    ) + "\n").encode()
    hourly = registry.create_hourly_demand_dataset(
        site.site_id, demand_id="hourly_v1", name="Hourly v1", csv_payload=payload,
    )
    assert {item.demand_id for item in registry.list_demand_datasets(site.site_id)} == {
        "estimate_v1", "estimate_v2", "monthly_v1", "hourly_v1"
    }
    assert first.demand_sha256 != second.demand_sha256
    assert monthly.demand_sha256 not in {first.demand_sha256, second.demand_sha256}
    assert hourly.path and hourly.source_file_sha256
    assert registry.build_demand(site.site_id, first.demand_id).annual_kwh == pytest.approx(30_000)
    assert registry.build_demand(site.site_id, second.demand_id).annual_kwh == pytest.approx(40_000)
    assert registry.build_demand(site.site_id, hourly.demand_id).sha256 == hourly.demand_sha256
