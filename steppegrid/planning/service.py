"""End-to-end orchestration for explicit catalog-versioned planning runs."""

from __future__ import annotations

import math
import time
import hashlib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable

from steppegrid.equipment.catalog import get_equipment_catalog
from steppegrid.planning.demand import (
    estimated_annual_demand,
    estimated_monthly_demand,
    rodina_benchmark_demand,
)
from steppegrid.planning.generation import prepare_generation, weather_cache_status
from steppegrid.planning.models import (
    MAXIMUM_ANNUAL_DEMAND_KWH,
    MINIMUM_ANNUAL_DEMAND_KWH,
    DemandMode,
    PlanningDemand,
    PlanningEconomics,
    PlanningMetrics,
    PlanningResult,
    PlanningScenario,
    SitePreset,
)
from steppegrid.planning.optimizer import OptimizationOutcome, optimize_planning_trace
from steppegrid.planning.outputs import ScenarioArtifacts, write_scenario_outputs
from steppegrid.sites.registry import SiteRegistry
from steppegrid.sites.models import WeatherStatus


@dataclass(frozen=True)
class PlanningRun:
    scenario: PlanningScenario
    demand: PlanningDemand
    result: PlanningResult
    dispatch_rows: list[dict[str, object]]
    artifacts: ScenarioArtifacts | None


def _software_version() -> str:
    try:
        return version("steppegrid")
    except PackageNotFoundError:
        return "0.1.0+workspace"


def _weather_sha256(generation) -> str:
    series = generation.weather.series
    arrays = (
        series.wind_speed_m_s, series.solar_irradiance_w_m2,
        series.temperature_c, series.wind_speed_100m_m_s,
        series.direct_normal_irradiance_w_m2, series.diffuse_radiation_w_m2,
    )
    digest = hashlib.sha256()
    for index, timestamp in enumerate(series.timestamps):
        values = [array[index] if array is not None else None for array in arrays]
        digest.update((timestamp.isoformat() + "," + ",".join(
            "" if value is None else f"{value:.12g}" for value in values
        ) + "\n").encode("utf-8"))
    return digest.hexdigest()


def build_scenario_demand(
    scenario: PlanningScenario, uploaded_demand: PlanningDemand | None = None
) -> PlanningDemand:
    specification = scenario.demand
    if scenario.demand_id is not None:
        if uploaded_demand is None:
            raise ValueError("the registered-demand scenario requires its resolved demand dataset")
        if uploaded_demand.sha256 != scenario.registered_demand_sha256:
            raise ValueError("registered demand content does not match the scenario SHA-256")
        return uploaded_demand
    if specification.mode is DemandMode.RODINA_BENCHMARK:
        return rodina_benchmark_demand(specification.profile_shape)
    if specification.mode is DemandMode.HOURLY_UPLOAD:
        if uploaded_demand is None:
            raise ValueError("the hourly-upload scenario requires its parsed demand trace")
        if uploaded_demand.sha256 != specification.upload_sha256:
            raise ValueError("uploaded demand content does not match the scenario SHA-256")
        return uploaded_demand
    # Existing known-site caches use the frozen Rodina local-year period and a UTC
    # calendar year for Shamshi. The local offset still drives hourly shape timing.
    timestamp_offset = scenario.site.timezone_offset if scenario.site.preset is SitePreset.RODINA else "+00:00"
    common = {
        "reference_year": scenario.reference_year,
        "timezone_offset": timestamp_offset,
        "shape": specification.profile_shape,
        "shape_timezone_offset": scenario.site.timezone_offset,
        "source_type": specification.source_type,
        "confidence": specification.confidence,
        "method": specification.method_notes,
        "source_name": specification.source_name,
        "source_url": specification.source_url,
        "source_year": specification.source_year,
    }
    if specification.mode is DemandMode.ESTIMATED_ANNUAL:
        return estimated_annual_demand(specification.annual_kwh, **common)
    if specification.mode is DemandMode.ESTIMATED_MONTHLY:
        return estimated_monthly_demand(specification.monthly_kwh, **common)
    raise ValueError(f"unsupported demand mode: {specification.mode}")


def _dispatch_detail(
    scenario: PlanningScenario,
    demand: PlanningDemand,
    outcome: OptimizationOutcome,
    wind_unit: list[float] | None,
    pv_unit: list[float] | None,
) -> list[dict[str, object]]:
    if not outcome.feasible or outcome.design is None:
        return []
    design = outcome.design
    catalog = get_equipment_catalog(scenario.equipment_catalog_version)
    battery = catalog.batteries[design.battery_key] if design.battery_key else None
    capacity = battery.nominal_energy_capacity_kwh * design.battery_count if battery else 0.0
    minimum = capacity * battery.minimum_soc_fraction if battery else 0.0
    charge_kw = battery.maximum_charge_power_kw * design.battery_count if battery else 0.0
    discharge_kw = battery.maximum_discharge_power_kw * design.battery_count if battery else 0.0
    efficiency = math.sqrt(battery.round_trip_efficiency) if battery else 1.0
    soc = minimum
    rows: list[dict[str, object]] = []
    zeros = [0.0] * len(demand.demand_kwh)
    for timestamp, load, wind_value, pv_value in zip(
        demand.timestamps, demand.demand_kwh, wind_unit or zeros, pv_unit or zeros, strict=True
    ):
        wind = wind_value * design.wind_count
        pv = pv_value * design.pv_count
        generation = wind + pv
        direct = min(load, generation)
        surplus = generation - direct
        deficit = load - direct
        charge = discharge = loss = 0.0
        if battery:
            charge = min(surplus, charge_kw, (capacity - soc) / efficiency)
            stored = charge * efficiency
            soc += stored
            discharge = min(deficit, discharge_kw, (soc - minimum) * efficiency)
            removed = discharge / efficiency
            soc -= removed
            loss = charge - stored + removed - discharge
        unmet = max(0.0, deficit - discharge)
        rows.append({
            "timestamp": timestamp.isoformat(),
            "demand_kwh": load,
            "wind_generation_kwh": wind,
            "pv_generation_kwh": pv,
            "renewable_generation_kwh": generation,
            "direct_service_kwh": direct,
            "battery_charge_input_kwh": charge,
            "battery_discharge_delivered_kwh": discharge,
            "battery_loss_kwh": loss,
            "battery_soc_end_kwh": soc,
            "curtailment_kwh": surplus - charge,
            "unmet_energy_kwh": unmet,
            "served_energy_kwh": load - unmet,
            "target": scenario.reliability_target,
        })
    return rows


class ScenarioPlanningService:
    def __init__(
        self,
        *,
        cache_root: str | Path = "data/weather/cache",
        output_root: str | Path = "outputs/scenarios",
        site_output_root: str | Path = "outputs/sites",
        registry: SiteRegistry | None = None,
    ) -> None:
        self.cache_root = Path(cache_root)
        self.output_root = Path(output_root)
        self.site_output_root = Path(site_output_root)
        self.registry = registry or SiteRegistry(cache_root=self.cache_root, output_root=self.site_output_root)

    def review(
        self, scenario: PlanningScenario, uploaded_demand: PlanningDemand | None = None
    ) -> tuple[PlanningDemand, dict[str, object]]:
        if scenario.site.site_id is not None:
            registered = self.registry.get_site(scenario.site.site_id)
            if registered.metadata_hash != scenario.site.site_metadata_hash:
                raise ValueError("registered site metadata changed; rebuild the scenario from the current site snapshot")
            if self.registry.get_weather_status(registered.site_id, scenario.reference_year) is not WeatherStatus.CACHED:
                raise ValueError("registered site weather is not validated as CACHED; prepare weather before planning")
            blockers = [
                check.message for check in self.registry.validate_registry().checks
                if check.site_id == registered.site_id and check.status == "BLOCKER"
            ]
            if blockers:
                raise ValueError(f"registered site is invalid: {'; '.join(blockers)}")
        if scenario.demand_id is not None and uploaded_demand is None:
            if scenario.site.site_id is None:
                raise ValueError("registered demand requires a registered site_id")
            uploaded_demand = self.registry.build_demand(scenario.site.site_id, scenario.demand_id)
        demand = build_scenario_demand(scenario, uploaded_demand)
        if not MINIMUM_ANNUAL_DEMAND_KWH <= demand.annual_kwh <= MAXIMUM_ANNUAL_DEMAND_KWH:
            raise ValueError(
                f"annual demand must be within the supported {MINIMUM_ANNUAL_DEMAND_KWH:g}–"
                f"{MAXIMUM_ANNUAL_DEMAND_KWH:g} kWh planning range"
            )
        return demand, weather_cache_status(scenario.site, demand, cache_root=self.cache_root)

    def run(
        self,
        scenario: PlanningScenario,
        uploaded_demand: PlanningDemand | None = None,
        *,
        save_outputs: bool = True,
        progress: Callable[[str], None] | None = None,
    ) -> PlanningRun:
        total_started = time.perf_counter()
        review_started = time.perf_counter()
        demand, _ = self.review(scenario, uploaded_demand)
        review_seconds = time.perf_counter() - review_started
        if progress:
            progress("Loading cached weather or making the explicit weather request")
        generation_started = time.perf_counter()
        generation = prepare_generation(
            scenario.site, demand, cache_root=self.cache_root,
            equipment_catalog_version=scenario.equipment_catalog_version,
        )
        generation_seconds = time.perf_counter() - generation_started
        if progress:
            progress("Building site-specific wind and PV unit traces")
        outcome = optimize_planning_trace(
            load_kwh=demand.demand_kwh,
            target=scenario.reliability_target,
            wind_profiles_kwh=generation.wind_profiles_kwh,
            pv_profiles_kwh=generation.pv_profiles_kwh,
            wind_metadata=generation.wind_metadata,
            pv_metadata=generation.pv_metadata,
            selection=scenario.technologies,
            equipment_catalog_version=scenario.equipment_catalog_version,
            economics_version=scenario.economics_version,
            progress=progress,
        )
        wind_unit = (
            generation.wind_profiles_kwh[outcome.design.wind_key]
            if outcome.design and outcome.design.wind_key else None
        )
        pv_unit = (
            generation.pv_profiles_kwh[outcome.design.pv_key]
            if outcome.design and outcome.design.pv_key else None
        )
        dispatch_started = time.perf_counter()
        dispatch_rows = _dispatch_detail(scenario, demand, outcome, wind_unit, pv_unit)
        dispatch_seconds = time.perf_counter() - dispatch_started
        metrics = PlanningMetrics(**{
            key: outcome.metrics[key] for key in PlanningMetrics.model_fields
        }) if outcome.feasible else None
        economics = PlanningEconomics(
            **outcome.economics,
            cost_per_served_kwh_usd=(
                float(outcome.economics["equivalent_annual_cost_usd"])
                / float(outcome.metrics["served_energy_kwh"])
            ),
        ) if outcome.feasible else None
        result = PlanningResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            scenario_input_hash=scenario.input_hash,
            site_id=scenario.site.site_id,
            site_metadata_hash=scenario.site.site_metadata_hash,
            site_snapshot=scenario.site,
            demand_id=scenario.demand_id,
            demand_sha256=demand.sha256,
            weather_cache_key=generation.weather.provenance.cache_key or "unknown",
            weather_cache_status=generation.weather.provenance.cache_status or "unknown",
            weather_sha256=_weather_sha256(generation),
            weather_source=generation.weather.provenance.source,
            weather_model=generation.weather.provenance.underlying_model or "ERA5",
            weather_start_utc=generation.weather.provenance.start_time,
            weather_end_utc=generation.weather.provenance.end_time,
            scenario_timezone=scenario.site.timezone_offset,
            annual_demand_kwh=demand.annual_kwh,
            demand_source_type=demand.source_type,
            demand_confidence=demand.confidence,
            demand_method=demand.method,
            reliability_target=scenario.reliability_target,
            equipment_catalog_version=scenario.equipment_catalog_version,
            economics_version=scenario.economics_version,
            feasible=outcome.feasible,
            design=outcome.design,
            metrics=metrics,
            economics=economics,
            optimizer_method=outcome.optimizer_method,
            evaluated_portfolios=outcome.evaluated_portfolios,
            dispatch_simulations=outcome.dispatch_simulations,
            dispatch_cache_hits=outcome.dispatch_cache_hits,
            theoretical_design_combinations=outcome.theoretical_design_combinations,
            catalog_option_counts={
                "wind": len(scenario.technologies.wind_keys),
                "pv": len(scenario.technologies.pv_keys),
                "battery": len(scenario.technologies.battery_keys),
            },
            elapsed_seconds=outcome.elapsed_seconds,
            stage_timings_seconds={
                "demand_review": review_seconds,
                "weather_and_generation": generation_seconds,
                "optimization": outcome.elapsed_seconds,
                "dispatch_detail": dispatch_seconds,
                "total_before_export": time.perf_counter() - total_started,
            },
            assumptions=(
                "Reliability is annual served-energy fraction, not a probability of service.",
                "Demand confidence labels are qualitative provenance classes, not confidence intervals.",
                generation.shear_terminology,
                "PV uses fixed tilt equal to absolute site latitude and an equator-facing azimuth.",
                f"Equipment catalog: {scenario.equipment_catalog_version.value}.",
                f"Economics method: {scenario.economics_version.value}; reference base years are explicit per technology.",
                "Result is a planning-model result, not a field-validated optimum or procurement quote.",
            ),
            software_version=_software_version(),
        )
        artifact_root = (
            self.site_output_root / scenario.site.site_id / "scenarios"
            if scenario.site.site_id else self.output_root
        )
        artifacts = (
            write_scenario_outputs(
                scenario, result, dispatch_rows, output_root=artifact_root
            )
            if save_outputs else None
        )
        if progress:
            progress("Planning result and provenance exports are ready")
        return PlanningRun(
            scenario=scenario, demand=demand, result=result,
            dispatch_rows=dispatch_rows, artifacts=artifacts,
        )
