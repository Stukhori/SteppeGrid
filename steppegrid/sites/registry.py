"""File-backed village registry, validation, onboarding, and scenario history."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from steppegrid.planning.demand import (
    estimated_annual_demand,
    estimated_monthly_demand,
    parse_hourly_demand_csv,
    rodina_benchmark_demand,
)
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningDemand,
    PlanningSite,
    SitePreset,
)
from steppegrid.simulation.models import Location
from steppegrid.weather.open_meteo import (
    MODEL_NAME,
    OPEN_METEO_DOCUMENTATION,
    PROVIDER_NAME,
    REQUESTED_VARIABLES,
    OpenMeteoHistoricalWeatherProvider,
)
from steppegrid.sites.models import (
    DemandDatasetRef,
    PlanningReadiness,
    ProvenanceSourceType,
    SiteAuditCheck,
    SiteClassification,
    SiteOrigin,
    SiteRegistryAudit,
    SourceReference,
    VillageSite,
    WeatherDatasetRef,
    WeatherStatus,
    resolve_registry_path,
)


class SiteRegistryError(ValueError):
    """Raised when registry data or an attempted mutation is invalid."""


@dataclass(frozen=True)
class RegistryTiming:
    registry_load_seconds: float
    validation_seconds: float
    demand_index_seconds: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SiteRegistry:
    def __init__(
        self,
        root: str | Path = "data/sites",
        *,
        cache_root: str | Path = "data/weather/cache",
        output_root: str | Path = "outputs/sites",
    ) -> None:
        self.root = Path(root)
        self.cache_root = Path(cache_root)
        self.output_root = Path(output_root)

    def _site_files(self) -> list[Path]:
        files: list[Path] = []
        for origin in ("builtin", "user"):
            directory = self.root / origin
            if directory.is_dir():
                files.extend(sorted(directory.glob("*/site.json")))
        return files

    def _load_pairs(self) -> list[tuple[Path, VillageSite]]:
        pairs: list[tuple[Path, VillageSite]] = []
        for path in self._site_files():
            try:
                site = VillageSite.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise SiteRegistryError(f"invalid site registry file {path}: {error}") from error
            expected = SiteOrigin.BUILT_IN if "builtin" in path.parts else SiteOrigin.USER_REGISTERED
            if site.origin is not expected:
                raise SiteRegistryError(f"site origin/path mismatch: {path}")
            pairs.append((path, site))
        ids = [site.site_id for _, site in pairs]
        duplicate = next((value for value in ids if ids.count(value) > 1), None)
        if duplicate:
            raise SiteRegistryError(f"duplicate site_id: {duplicate}")
        return pairs

    def list_sites(self) -> tuple[VillageSite, ...]:
        return tuple(site for _, site in self._load_pairs())

    def get_site(self, site_id: str) -> VillageSite:
        for _, site in self._load_pairs():
            if site.site_id == site_id:
                return site
        raise SiteRegistryError(f"unknown site_id: {site_id}")

    def _path_for(self, site: VillageSite) -> Path:
        origin = "builtin" if site.origin is SiteOrigin.BUILT_IN else "user"
        return self.root / origin / site.site_id / "site.json"

    def register_site(self, site: VillageSite) -> VillageSite:
        if site.origin is not SiteOrigin.USER_REGISTERED:
            raise SiteRegistryError("only USER_REGISTERED sites can be created through onboarding")
        if any(existing.site_id == site.site_id for existing in self.list_sites()):
            raise SiteRegistryError(f"duplicate site_id: {site.site_id}")
        _atomic_json(self._path_for(site), site.model_dump(mode="json"))
        return self.get_site(site.site_id)

    def onboard_site(
        self,
        *,
        site_id: str,
        name: str,
        region: str,
        country: str,
        latitude: float,
        longitude: float,
        timezone_name: str,
        settlement_type: str = "village",
        classification: SiteClassification = SiteClassification.PLANNING_SITE,
        source_name: str = "User-provided site metadata",
        source_url: str | None = None,
        notes: str | None = None,
        reference_year: int = 2025,
    ) -> VillageSite:
        zone = ZoneInfo(timezone_name)
        offset = datetime(reference_year, 1, 1, tzinfo=zone).utcoffset()
        if offset is None:
            raise SiteRegistryError(f"timezone has no UTC offset: {timezone_name}")
        minutes = int(offset.total_seconds() // 60)
        sign = "+" if minutes >= 0 else "-"
        hours, remainder = divmod(abs(minutes), 60)
        offset_text = f"{sign}{hours:02d}:{remainder:02d}"
        provenance = tuple(
            SourceReference(
                field=field, source_name=source_name,
                source_type=ProvenanceSourceType.USER_PROVIDED,
                source_url=source_url,
                notes="Entered through the Phase 16 local onboarding workflow.",
            )
            for field in ("coordinates", "name", "region", "timezone")
        )
        site = VillageSite(
            site_id=site_id, name=name, settlement_type=settlement_type,
            country=country, region=region, latitude=latitude, longitude=longitude,
            timezone=timezone_name, timezone_offset=offset_text,
            classification=classification, origin=SiteOrigin.USER_REGISTERED,
            provenance=provenance, notes=notes,
        )
        return self.register_site(site)

    def _write_user_site(self, site: VillageSite) -> VillageSite:
        if site.origin is SiteOrigin.BUILT_IN:
            raise SiteRegistryError("built-in sites are read-only")
        _atomic_json(self._path_for(site), site.model_dump(mode="json"))
        return self.get_site(site.site_id)

    def update_site_metadata(self, site_id: str, **changes: object) -> VillageSite:
        site = self.get_site(site_id)
        if site.origin is SiteOrigin.BUILT_IN:
            raise SiteRegistryError("built-in sites are read-only")
        protected = {"site_id", "origin", "weather_datasets", "demand_datasets"}
        if protected & changes.keys():
            raise SiteRegistryError(f"use dedicated methods for: {sorted(protected & changes.keys())}")
        coordinates_changed = any(
            key in changes and changes[key] != getattr(site, key)
            for key in ("latitude", "longitude")
        )
        weather = site.weather_datasets
        if coordinates_changed:
            weather = tuple(item.model_copy(update={"status": WeatherStatus.STALE}) for item in weather)
        updated = site.model_copy(update={**changes, "weather_datasets": weather})
        return self._write_user_site(VillageSite.model_validate(updated.model_dump()))

    def remove_site(self, site_id: str) -> None:
        site = self.get_site(site_id)
        if site.origin is SiteOrigin.BUILT_IN:
            raise SiteRegistryError("built-in sites cannot be removed")
        directory = self._path_for(site).parent.resolve()
        user_root = (self.root / "user").resolve()
        if directory.parent != user_root or directory.name != site.site_id:
            raise SiteRegistryError("refusing to remove a site outside the user registry")
        shutil.rmtree(directory)

    def list_demand_datasets(self, site_id: str) -> tuple[DemandDatasetRef, ...]:
        return self.get_site(site_id).demand_datasets

    def get_demand_dataset(self, site_id: str, demand_id: str) -> DemandDatasetRef:
        for dataset in self.get_site(site_id).demand_datasets:
            if dataset.demand_id == demand_id:
                return dataset
        raise SiteRegistryError(f"unknown demand_id for {site_id}: {demand_id}")

    def get_weather_status(self, site_id: str, year: int = 2025) -> WeatherStatus:
        refs = [item for item in self.get_site(site_id).weather_datasets if item.year == year]
        if not refs:
            return WeatherStatus.MISSING
        if any(item.status is WeatherStatus.CACHED for item in refs):
            return WeatherStatus.CACHED
        return refs[0].status

    def get_planning_readiness(self, site_id: str) -> PlanningReadiness:
        site = self.get_site(site_id)
        if self._site_blockers(site):
            return PlanningReadiness.INVALID
        if self.get_weather_status(site_id) is not WeatherStatus.CACHED:
            return PlanningReadiness.WEATHER_MISSING
        if not site.demand_datasets:
            return PlanningReadiness.DEMAND_MISSING
        return (
            PlanningReadiness.BENCHMARK_READY
            if site.classification is SiteClassification.BENCHMARK
            else PlanningReadiness.READY_FOR_PLANNING
        )

    def planning_site(self, site_id: str) -> PlanningSite:
        site = self.get_site(site_id)
        preset = SitePreset.RODINA if site.classification is SiteClassification.BENCHMARK else SitePreset.REGISTERED
        return PlanningSite(
            preset=preset,
            site_id=site.site_id,
            site_metadata_hash=site.metadata_hash,
            name=site.name,
            latitude=site.latitude,
            longitude=site.longitude,
            country=site.country,
            region=site.region,
            timezone=site.timezone,
            timezone_offset=site.timezone_offset,
            site_classification=site.classification.value,
            registry_origin=site.origin.value,
        )

    def demand_specification(self, site_id: str, demand_id: str) -> DemandSpecification:
        item = self.get_demand_dataset(site_id, demand_id)
        return DemandSpecification(
            mode=item.mode,
            source_type=item.classification,
            confidence=item.confidence,
            profile_shape=item.profile_shape,
            annual_kwh=item.annual_energy_kwh if item.mode is DemandMode.ESTIMATED_ANNUAL else None,
            monthly_kwh=item.monthly_kwh,
            source_name=item.provenance[0].source_name,
            source_url=item.provenance[0].source_url,
            source_year=item.provenance[0].source_year,
            method_notes=item.profile_method,
            upload_filename=Path(item.path).name if item.mode is DemandMode.HOURLY_UPLOAD and item.path else None,
            upload_sha256=item.demand_sha256 if item.mode is DemandMode.HOURLY_UPLOAD else None,
        )

    def build_demand(self, site_id: str, demand_id: str) -> PlanningDemand:
        site = self.get_site(site_id)
        item = self.get_demand_dataset(site_id, demand_id)
        source = item.provenance[0]
        if item.mode is DemandMode.RODINA_BENCHMARK:
            demand = rodina_benchmark_demand(item.profile_shape)
        elif item.mode is DemandMode.ESTIMATED_ANNUAL:
            demand = estimated_annual_demand(
                item.annual_energy_kwh,
                reference_year=item.reference_year,
                timezone_offset="+00:00",
                shape=item.profile_shape,
                shape_timezone_offset=site.timezone_offset,
                source_type=item.classification,
                confidence=item.confidence,
                method=item.profile_method,
                source_name=source.source_name,
                source_url=source.source_url,
                source_year=source.source_year,
            )
        elif item.mode is DemandMode.ESTIMATED_MONTHLY:
            demand = estimated_monthly_demand(
                item.monthly_kwh or (),
                reference_year=item.reference_year,
                timezone_offset="+00:00",
                shape=item.profile_shape,
                shape_timezone_offset=site.timezone_offset,
                source_type=item.classification,
                confidence=item.confidence,
                method=item.profile_method,
                source_name=source.source_name,
                source_url=source.source_url,
                source_year=source.source_year,
            )
        elif item.mode is DemandMode.HOURLY_UPLOAD:
            path = resolve_registry_path(self.root, item.path)
            if path is None or not path.is_file():
                raise SiteRegistryError(f"missing hourly demand file: {item.path}")
            demand = parse_hourly_demand_csv(
                path.read_bytes(), source_type=item.classification,
                confidence=item.confidence, method=item.profile_method,
                source_name=source.source_name, source_year=source.source_year,
            )
        else:
            raise SiteRegistryError(f"unsupported registered demand mode: {item.mode}")
        if demand.sha256 != item.demand_sha256:
            raise SiteRegistryError(
                f"registered demand hash mismatch for {site_id}/{demand_id}: "
                f"expected {item.demand_sha256}, got {demand.sha256}"
            )
        return demand

    def add_demand_dataset(self, site_id: str, dataset: DemandDatasetRef) -> VillageSite:
        site = self.get_site(site_id)
        if site.origin is SiteOrigin.BUILT_IN:
            raise SiteRegistryError("built-in sites are read-only")
        if dataset.site_id != site_id:
            raise SiteRegistryError("demand dataset site_id mismatch")
        if any(item.demand_id == dataset.demand_id for item in site.demand_datasets):
            raise SiteRegistryError(f"duplicate demand_id: {dataset.demand_id}")
        return self._write_user_site(site.model_copy(update={
            "demand_datasets": (*site.demand_datasets, dataset)
        }))

    def create_annual_demand_dataset(
        self,
        site_id: str,
        *,
        demand_id: str,
        name: str,
        annual_kwh: float,
        profile_shape: str = "community_facility_like",
        classification: DemandSourceType = DemandSourceType.SYNTHETIC_ESTIMATE,
        confidence: DemandConfidence = DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        method: str = "User planning assumption distributed with a deterministic hourly shape.",
        source_name: str = "User-provided planning assumption",
        source_url: str | None = None,
        source_year: int | None = None,
        reference_year: int = 2025,
    ) -> DemandDatasetRef:
        site = self.get_site(site_id)
        demand = estimated_annual_demand(
            annual_kwh, reference_year=reference_year, timezone_offset="+00:00",
            shape=profile_shape, shape_timezone_offset=site.timezone_offset,
            source_type=classification, confidence=confidence, method=method,
            source_name=source_name, source_url=source_url, source_year=source_year,
        )
        dataset = DemandDatasetRef(
            demand_id=demand_id, site_id=site_id, name=name,
            mode=DemandMode.ESTIMATED_ANNUAL, classification=classification,
            confidence=confidence, reference_year=reference_year,
            annual_energy_kwh=demand.annual_kwh, profile_method=method,
            profile_shape=profile_shape, demand_sha256=demand.sha256,
            provenance=(SourceReference(
                field="demand", source_name=source_name,
                source_type=ProvenanceSourceType.USER_PROVIDED,
                source_url=source_url, source_year=source_year,
                notes="Numerical planning input; not automatically field validated.",
            ),),
            created_at_utc=datetime.now(timezone.utc),
        )
        self.add_demand_dataset(site_id, dataset)
        return dataset

    def create_monthly_demand_dataset(
        self,
        site_id: str,
        *,
        demand_id: str,
        name: str,
        monthly_kwh: tuple[float, ...],
        profile_shape: str = "community_facility_like",
        classification: DemandSourceType = DemandSourceType.SYNTHETIC_ESTIMATE,
        confidence: DemandConfidence = DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        method: str = "User monthly planning assumptions distributed with a deterministic hourly shape.",
        source_name: str = "User-provided planning assumptions",
        source_url: str | None = None,
        source_year: int | None = None,
        reference_year: int = 2025,
    ) -> DemandDatasetRef:
        site = self.get_site(site_id)
        demand = estimated_monthly_demand(
            monthly_kwh, reference_year=reference_year, timezone_offset="+00:00",
            shape=profile_shape, shape_timezone_offset=site.timezone_offset,
            source_type=classification, confidence=confidence, method=method,
            source_name=source_name, source_url=source_url, source_year=source_year,
        )
        dataset = DemandDatasetRef(
            demand_id=demand_id, site_id=site_id, name=name,
            mode=DemandMode.ESTIMATED_MONTHLY, classification=classification,
            confidence=confidence, reference_year=reference_year,
            annual_energy_kwh=demand.annual_kwh, monthly_kwh=monthly_kwh,
            profile_method=method, profile_shape=profile_shape,
            demand_sha256=demand.sha256,
            provenance=(SourceReference(
                field="demand", source_name=source_name,
                source_type=ProvenanceSourceType.USER_PROVIDED,
                source_url=source_url, source_year=source_year,
                notes="Monthly numerical inputs; not automatically field validated.",
            ),), created_at_utc=datetime.now(timezone.utc),
        )
        self.add_demand_dataset(site_id, dataset)
        return dataset

    def create_hourly_demand_dataset(
        self,
        site_id: str,
        *,
        demand_id: str,
        name: str,
        csv_payload: bytes,
        classification: DemandSourceType = DemandSourceType.USER_PROVIDED,
        confidence: DemandConfidence = DemandConfidence.USER_PROVIDED_UNVERIFIED,
        method: str = "User-uploaded hourly demand CSV.",
        source_name: str = "User-provided hourly demand",
        source_year: int | None = None,
    ) -> DemandDatasetRef:
        site = self.get_site(site_id)
        demand = parse_hourly_demand_csv(
            csv_payload, source_type=classification, confidence=confidence,
            method=method, source_name=source_name, source_year=source_year,
        )
        path = self._path_for(site).parent / "demand" / f"{demand_id}.csv"
        _atomic_bytes(path, csv_payload)
        dataset = DemandDatasetRef(
            demand_id=demand_id, site_id=site_id, name=name,
            mode=DemandMode.HOURLY_UPLOAD, classification=classification,
            confidence=confidence, reference_year=demand.timestamps[0].year,
            annual_energy_kwh=demand.annual_kwh, profile_method=method,
            profile_shape="community_facility_like", path=str(path.resolve()),
            source_file_sha256=_sha256(path), demand_sha256=demand.sha256,
            provenance=(SourceReference(
                field="demand", source_name=source_name,
                source_type=ProvenanceSourceType.USER_PROVIDED,
                source_year=source_year,
                notes="Strict hourly CSV; evidence classification is retained exactly.",
            ),), created_at_utc=datetime.now(timezone.utc),
        )
        try:
            self.add_demand_dataset(site_id, dataset)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return dataset

    def prepare_weather(
        self,
        site_id: str,
        *,
        year: int = 2025,
        refresh: bool = False,
        provider: OpenMeteoHistoricalWeatherProvider | None = None,
    ) -> WeatherDatasetRef:
        site = self.get_site(site_id)
        if site.origin is SiteOrigin.BUILT_IN:
            raise SiteRegistryError("built-in weather references are read-only")
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        weather_provider = provider or OpenMeteoHistoricalWeatherProvider(cache_root=self.cache_root)
        dataset = weather_provider.get_hourly_weather(
            Location(name=site.name, latitude=site.latitude, longitude=site.longitude, country=site.country),
            start, end, refresh=refresh,
        )
        provenance = dataset.provenance
        path = Path(provenance.normalized_data_path or "")
        metadata_path = Path(provenance.metadata_path or "")
        reference = WeatherDatasetRef(
            weather_id=f"era5_{year}", source=PROVIDER_NAME, model=MODEL_NAME,
            year=year, status=WeatherStatus.CACHED, variables=tuple(REQUESTED_VARIABLES),
            start_utc=provenance.start_time, end_utc=provenance.end_time,
            latitude=site.latitude, longitude=site.longitude,
            cache_key=provenance.cache_key, path=path.as_posix(),
            metadata_path=metadata_path.as_posix(), sha256=_sha256(path),
            provenance=(SourceReference(
                field="weather", source_name=PROVIDER_NAME,
                source_type=ProvenanceSourceType.DERIVED,
                source_url=OPEN_METEO_DOCUMENTATION, source_year=year,
                notes="ERA5 gridded reanalysis; not a site measurement.",
            ),),
        )
        others = tuple(item for item in site.weather_datasets if item.weather_id != reference.weather_id)
        self._write_user_site(site.model_copy(update={"weather_datasets": (*others, reference)}))
        return reference

    def _site_blockers(self, site: VillageSite) -> list[str]:
        blockers: list[str] = []
        for weather in site.weather_datasets:
            if weather.status is WeatherStatus.INVALID:
                blockers.append(f"invalid weather reference: {weather.weather_id}")
            if weather.status is WeatherStatus.CACHED:
                for label, relative in (("weather", weather.path), ("weather metadata", weather.metadata_path)):
                    path = resolve_registry_path(self.root, relative)
                    if path is None or not path.is_file():
                        blockers.append(f"missing {label} file: {relative}")
                path = resolve_registry_path(self.root, weather.path)
                if path and path.is_file() and _sha256(path) != weather.sha256:
                    blockers.append(f"weather SHA-256 mismatch: {weather.weather_id}")
                if (weather.latitude, weather.longitude) != (site.latitude, site.longitude):
                    blockers.append(f"weather coordinate mismatch: {weather.weather_id}")
        for demand in site.demand_datasets:
            if demand.path:
                path = resolve_registry_path(self.root, demand.path)
                if path is None or not path.is_file():
                    blockers.append(f"missing demand file: {demand.path}")
                elif demand.source_file_sha256 and _sha256(path) != demand.source_file_sha256:
                    blockers.append(f"demand source SHA-256 mismatch: {demand.demand_id}")
            try:
                self.build_demand(site.site_id, demand.demand_id)
            except (ValueError, OSError) as error:
                blockers.append(str(error))
        return blockers

    def validate_registry(self, *, write_output: bool = False) -> SiteRegistryAudit:
        checks: list[SiteAuditCheck] = []
        try:
            sites = self.list_sites()
        except SiteRegistryError as error:
            return SiteRegistryAudit(
                registered_sites=0, valid_sites=0, planning_ready_sites=0,
                weather_missing=0, demand_missing=0, blockers=1, warnings=0,
                checks=(SiteAuditCheck(site_id=None, category="registry", status="BLOCKER", message=str(error)),),
            )
        ready = weather_missing = demand_missing = valid = 0
        for site in sites:
            blockers = self._site_blockers(site)
            for message in blockers:
                checks.append(SiteAuditCheck(site_id=site.site_id, category="validation", status="BLOCKER", message=message))
            if not blockers:
                valid += 1
                checks.append(SiteAuditCheck(site_id=site.site_id, category="metadata", status="PASS", message="Typed site metadata and provenance are valid"))
            weather_status = self.get_weather_status(site.site_id)
            if weather_status is not WeatherStatus.CACHED:
                weather_missing += 1
                checks.append(SiteAuditCheck(site_id=site.site_id, category="weather", status="WARNING", message=f"Weather status: {weather_status.value}"))
            if not site.demand_datasets:
                demand_missing += 1
                checks.append(SiteAuditCheck(site_id=site.site_id, category="demand", status="WARNING", message="No demand dataset registered; planning is unavailable"))
            for dataset in site.demand_datasets:
                if dataset.classification in {DemandSourceType.SYNTHETIC_ESTIMATE, DemandSourceType.USER_PROVIDED}:
                    checks.append(SiteAuditCheck(site_id=site.site_id, category="demand", status="WARNING", message=f"{dataset.demand_id} is {dataset.classification.value}, not measured demand"))
            if self.get_planning_readiness(site.site_id) in {
                PlanningReadiness.READY_FOR_PLANNING, PlanningReadiness.BENCHMARK_READY
            }:
                ready += 1
        audit = SiteRegistryAudit(
            registered_sites=len(sites), valid_sites=valid, planning_ready_sites=ready,
            weather_missing=weather_missing, demand_missing=demand_missing,
            blockers=sum(item.status == "BLOCKER" for item in checks),
            warnings=sum(item.status == "WARNING" for item in checks), checks=tuple(checks),
        )
        if write_output:
            _atomic_json(Path("outputs/site_registry/site_audit.json"), audit.model_dump(mode="json"))
        return audit

    def scenario_history(self, site_id: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        roots = [self.output_root / site_id / "scenarios", Path("outputs/scenarios")]
        for root in roots:
            if not root.is_dir():
                continue
            for result_path in root.glob("scenario-*/result.json"):
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if result.get("site_id") != site_id:
                    continue
                design, economics = result.get("design") or {}, result.get("economics") or {}
                rows.append({
                    "scenario_id": result.get("scenario_id"),
                    "demand_id": result.get("demand_id"),
                    "target": result.get("reliability_target"),
                    "catalog": result.get("equipment_catalog_version"),
                    "feasible": result.get("feasible"),
                    "design": design,
                    "npc_usd": economics.get("net_present_cost_usd"),
                    "created_at": datetime.fromtimestamp(result_path.stat().st_mtime, timezone.utc).isoformat(),
                    "path": str(result_path.parent),
                })
        return sorted(rows, key=lambda row: str(row["created_at"]), reverse=True)

    def performance_snapshot(self) -> RegistryTiming:
        started = time.perf_counter(); sites = self.list_sites(); loaded = time.perf_counter() - started
        started = time.perf_counter(); self.validate_registry(); validated = time.perf_counter() - started
        started = time.perf_counter(); tuple(item for site in sites for item in site.demand_datasets); indexed = time.perf_counter() - started
        return RegistryTiming(loaded, validated, indexed)

    def export_site(self, site_id: str) -> str:
        return json.dumps(self.get_site(site_id).model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
