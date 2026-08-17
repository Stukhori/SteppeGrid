"""Generalized Phase 10 staged sizing for one explicit planning scenario."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from steppegrid.benchmarks.phase10 import (
    ANNUAL_ENERGY_BOUND_MULTIPLIER,
    WIND_ENERGY_SHARES,
    _ensure_trace,
    _minimum_scale,
    _portfolio,
)
from steppegrid.equipment.catalog import EquipmentCatalog, EquipmentCatalogVersion, get_equipment_catalog
from steppegrid.optimization.core import (
    DispatchCache,
    RenewablePortfolio,
    annual_energy_sufficient,
    minimum_battery_count,
    scale_trace,
)
from steppegrid.optimization.economics import EconomicsVersion, system_cost
from steppegrid.planning.models import PlanningDesign, TechnologySelection

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class SearchLimits:
    maximum_equipment_count: int = 25_000
    maximum_battery_count: int = 64
    exact_renewable_portfolio_limit: int = 2_500
    maximum_estimated_dispatches: int = 500_000


@dataclass(frozen=True)
class OptimizationOutcome:
    feasible: bool
    design: PlanningDesign | None
    metrics: dict[str, float | int]
    economics: dict[str, object]
    optimizer_method: str
    evaluated_portfolios: int
    dispatch_simulations: int
    elapsed_seconds: float
    generation_kwh: tuple[float, ...] | None
    dispatch_cache_hits: int = 0
    theoretical_design_combinations: int = 0


def _validated_selection(selection: TechnologySelection, catalog: EquipmentCatalog) -> None:
    unknown_wind = set(selection.wind_keys) - set(catalog.wind_turbines)
    unknown_pv = set(selection.pv_keys) - {
        f"{module}__{inverter}" for module in catalog.pv_modules for inverter in catalog.inverters
    }
    unknown_battery = set(selection.battery_keys) - set(catalog.batteries)
    if unknown_wind or unknown_pv or unknown_battery:
        raise ValueError(
            f"unknown equipment keys: wind={sorted(unknown_wind)}, "
            f"pv={sorted(unknown_pv)}, battery={sorted(unknown_battery)}"
        )


def _bounds(
    annual_load_kwh: float,
    wind: Mapping[str, Sequence[float]],
    pv: Mapping[str, Sequence[float]],
    limits: SearchLimits,
) -> tuple[dict[str, int], dict[str, int]]:
    target = ANNUAL_ENERGY_BOUND_MULTIPLIER * annual_load_kwh
    wind_bounds = {key: math.ceil(target / math.fsum(trace)) for key, trace in wind.items()}
    pv_bounds = {key: math.ceil(target / math.fsum(trace)) for key, trace in pv.items()}
    all_bounds = (*wind_bounds.values(), *pv_bounds.values())
    if any(value > limits.maximum_equipment_count for value in all_bounds):
        raise ValueError(
            "scenario exceeds the supported equipment-count search bound; reduce demand, "
            "select a larger unit technology, or split the planning problem"
        )
    return wind_bounds, pv_bounds


def _battery_bounds(annual_load_kwh: float, keys: Sequence[str], limits: SearchLimits,
                    catalog: EquipmentCatalog) -> dict[str, int]:
    # Two average-load days is a deterministic scenario-aware screening ceiling.
    energy = 2 * annual_load_kwh / 365
    return {
        key: min(
            limits.maximum_battery_count,
            max(4, math.ceil(energy / catalog.batteries[key].usable_energy_capacity_kwh)),
        )
        for key in keys
    }


def _technology_pairs(
    wind_keys: Sequence[str], pv_keys: Sequence[str]
) -> list[tuple[str | None, str | None, tuple[float, ...]]]:
    if wind_keys and pv_keys:
        return [
            (wind_key, pv_key, WIND_ENERGY_SHARES)
            for wind_key in wind_keys for pv_key in pv_keys
        ]
    if wind_keys:
        return [(wind_key, None, (1.0,)) for wind_key in wind_keys]
    return [(None, pv_key, (0.0,)) for pv_key in pv_keys]


def _design_and_cost(
    portfolio: RenewablePortfolio,
    battery_key: str | None,
    battery_count: int,
    wind_metadata: Mapping[str, Mapping[str, object]],
    pv_metadata: Mapping[str, Mapping[str, object]],
    catalog: EquipmentCatalog,
    economics_version: EconomicsVersion,
) -> tuple[PlanningDesign, dict[str, object]]:
    wind_kw = (
        portfolio.wind_count * float(wind_metadata[portfolio.wind_key]["rated_power_kw"])
        if portfolio.wind_key else 0.0
    )
    pv_dc_kw = (
        portfolio.pv_count * float(pv_metadata[portfolio.pv_key]["dc_capacity_kw"])
        if portfolio.pv_key else 0.0
    )
    pv_ac_kw = (
        portfolio.pv_count * float(pv_metadata[portfolio.pv_key]["ac_capacity_kw"])
        if portfolio.pv_key else 0.0
    )
    battery_kwh = (
        battery_count * catalog.batteries[battery_key].usable_energy_capacity_kwh
        if battery_key else 0.0
    )
    design = PlanningDesign(
        wind_key=portfolio.wind_key,
        wind_count=portfolio.wind_count,
        pv_key=portfolio.pv_key,
        pv_count=portfolio.pv_count,
        battery_key=battery_key if battery_count else None,
        battery_count=battery_count,
        wind_capacity_kw=wind_kw,
        pv_dc_capacity_kw=pv_dc_kw,
        pv_ac_capacity_kw=pv_ac_kw,
        battery_usable_capacity_kwh=battery_kwh,
    )
    return design, system_cost(
        wind_kw=wind_kw,
        pv_dc_kw=pv_dc_kw,
        pv_ac_kw=pv_ac_kw,
        battery_usable_kwh=battery_kwh,
        economics_version=economics_version,
    )


def _exact_candidates(
    *,
    load: Sequence[float],
    target: float,
    wind: Mapping[str, Sequence[float]],
    pv: Mapping[str, Sequence[float]],
    wind_bounds: Mapping[str, int],
    pv_bounds: Mapping[str, int],
    battery_bounds: Mapping[str, int],
    selection: TechnologySelection,
    wind_metadata: Mapping[str, Mapping[str, object]],
    pv_metadata: Mapping[str, Mapping[str, object]],
    catalog: EquipmentCatalog,
    economics_version: EconomicsVersion,
) -> tuple[list[dict], DispatchCache, dict[str, list[float]]]:
    traces: dict[str, list[float]] = {}
    cache = DispatchCache({"scenario": load}, traces, catalog.batteries)
    rows: list[dict] = []
    for wind_key, pv_key, _ in _technology_pairs(selection.wind_keys, selection.pv_keys):
        wind_range = range(wind_bounds[wind_key] + 1) if wind_key else range(1)
        pv_range = range(pv_bounds[pv_key] + 1) if pv_key else range(1)
        for wind_count in wind_range:
            for pv_count in pv_range:
                if wind_count + pv_count == 0:
                    continue
                portfolio = _portfolio(wind_key, pv_key, wind_count, pv_count)
                _ensure_trace(portfolio, traces, wind, pv)
                if not annual_energy_sufficient(math.fsum(traces[portfolio.key]), math.fsum(load), target):
                    continue
                battery_options: list[tuple[str | None, int]] = [(None, 0)]
                for battery_key, maximum in battery_bounds.items():
                    count, _ = minimum_battery_count(
                        cache, portfolio, ("scenario",), battery_key, target, maximum
                    )
                    if count is not None:
                        battery_options.append((battery_key if count else None, count))
                for battery_key, count in battery_options:
                    metrics = cache.get(portfolio, "scenario", battery_key, count)
                    if metrics["served_fraction"] + 1e-12 < target:
                        continue
                    design, economics = _design_and_cost(
                        portfolio, battery_key, count, wind_metadata, pv_metadata,
                        catalog, economics_version,
                    )
                    rows.append({"portfolio": portfolio, "design": design, "metrics": metrics, "economics": economics})
    return rows, cache, traces


def _staged_candidates(
    *,
    load: Sequence[float],
    target: float,
    wind: Mapping[str, Sequence[float]],
    pv: Mapping[str, Sequence[float]],
    wind_bounds: Mapping[str, int],
    pv_bounds: Mapping[str, int],
    battery_bounds: Mapping[str, int],
    selection: TechnologySelection,
    wind_metadata: Mapping[str, Mapping[str, object]],
    pv_metadata: Mapping[str, Mapping[str, object]],
    catalog: EquipmentCatalog,
    economics_version: EconomicsVersion,
) -> tuple[list[dict], DispatchCache, dict[str, list[float]]]:
    traces: dict[str, list[float]] = {}
    cache = DispatchCache({"scenario": load}, traces, catalog.batteries)
    stats = {"annual_energy_pruned": 0}
    rows_by_design: dict[str, dict] = {}
    annual_load = math.fsum(load)
    for wind_key, pv_key, shares in _technology_pairs(selection.wind_keys, selection.pv_keys):
        wind_maximum = wind_bounds[wind_key] if wind_key else 0
        pv_maximum = pv_bounds[pv_key] if pv_key else 0
        for share in shares:
            wind_count = (
                math.ceil(target * annual_load * share / math.fsum(wind[wind_key]))
                if wind_key and share else 0
            )
            pv_count = (
                math.ceil(target * annual_load * (1 - share) / math.fsum(pv[pv_key]))
                if pv_key and share < 1 else 0
            )
            base = _portfolio(wind_key, pv_key, wind_count, pv_count)
            for battery_key, maximum in ((None, 0), *battery_bounds.items()):
                portfolio = _minimum_scale(
                    base, wind_maximum, pv_maximum, ("scenario",), target,
                    battery_key, maximum, cache, traces, wind, pv, stats,
                )
                if portfolio is None:
                    continue
                _ensure_trace(portfolio, traces, wind, pv)
                if battery_key is None:
                    count = 0
                else:
                    count, _ = minimum_battery_count(
                        cache, portfolio, ("scenario",), battery_key, target, maximum
                    )
                    if count is None:
                        continue
                metrics = cache.get(portfolio, "scenario", battery_key, count)
                if metrics["served_fraction"] + 1e-12 < target:
                    continue
                design, economics = _design_and_cost(
                    portfolio, battery_key, count, wind_metadata, pv_metadata,
                    catalog, economics_version,
                )
                key = (
                    f"{portfolio.key}|b={design.battery_key or 'none'}:{design.battery_count}"
                )
                rows_by_design[key] = {
                    "portfolio": portfolio, "design": design,
                    "metrics": metrics, "economics": economics,
                }
    return list(rows_by_design.values()), cache, traces


def optimize_planning_trace(
    *,
    load_kwh: Sequence[float],
    target: float,
    wind_profiles_kwh: Mapping[str, Sequence[float]],
    pv_profiles_kwh: Mapping[str, Sequence[float]],
    wind_metadata: Mapping[str, Mapping[str, object]],
    pv_metadata: Mapping[str, Mapping[str, object]],
    selection: TechnologySelection,
    equipment_catalog_version: EquipmentCatalogVersion = EquipmentCatalogVersion.RODINA_FROZEN_V1,
    economics_version: EconomicsVersion = EconomicsVersion.PHASE10_FROZEN_ECONOMICS_V1,
    limits: SearchLimits = SearchLimits(),
    progress: ProgressCallback | None = None,
) -> OptimizationOutcome:
    """Choose least-NPC feasible design using the generalized Phase 10 search."""
    started = time.perf_counter()
    if target not in (0.95, 0.99):
        raise ValueError("planning reliability target must be exactly 0.95 or 0.99")
    if not load_kwh or any(not math.isfinite(value) or value < 0 for value in load_kwh):
        raise ValueError("load must be a non-empty finite non-negative trace")
    if math.fsum(load_kwh) <= 0:
        raise ValueError("annual load must be positive")
    catalog = get_equipment_catalog(equipment_catalog_version)
    _validated_selection(selection, catalog)
    wind = {key: wind_profiles_kwh[key] for key in selection.wind_keys}
    pv = {key: pv_profiles_kwh[key] for key in selection.pv_keys}
    if any(len(trace) != len(load_kwh) for trace in (*wind.values(), *pv.values())):
        raise ValueError("all generation traces must align with the load trace")
    if progress:
        progress("Computing deterministic scenario-aware bounds")
    wind_bounds, pv_bounds = _bounds(math.fsum(load_kwh), wind, pv, limits)
    battery_bounds = _battery_bounds(math.fsum(load_kwh), selection.battery_keys, limits, catalog)
    pairs = _technology_pairs(selection.wind_keys, selection.pv_keys)
    renewable_space = sum(
        (wind_bounds[wind_key] + 1 if wind_key else 1)
        * (pv_bounds[pv_key] + 1 if pv_key else 1)
        for wind_key, pv_key, _ in pairs
    )
    estimated_dispatches = len(pairs) * max(len(WIND_ENERGY_SHARES), 1) * (
        1 + sum(1 + math.ceil(math.log2(maximum + 1)) for maximum in battery_bounds.values())
    ) * 16
    if estimated_dispatches > limits.maximum_estimated_dispatches:
        raise ValueError(
            "selected technology set exceeds the supported staged-search scale; "
            "select fewer technologies"
        )
    if renewable_space <= limits.exact_renewable_portfolio_limit:
        method = "exact_reduced_space"
        if progress:
            progress(f"Enumerating the reduced search space ({renewable_space:,} renewable portfolios)")
        rows, cache, traces = _exact_candidates(
            load=load_kwh, target=target, wind=wind, pv=pv,
            wind_bounds=wind_bounds, pv_bounds=pv_bounds, battery_bounds=battery_bounds,
            selection=selection, wind_metadata=wind_metadata, pv_metadata=pv_metadata,
            catalog=catalog, economics_version=EconomicsVersion(economics_version),
        )
    else:
        method = "phase10_staged_generalized"
        if progress:
            progress("Running adaptive Phase 10 energy-share rays and monotonic storage search")
        rows, cache, traces = _staged_candidates(
            load=load_kwh, target=target, wind=wind, pv=pv,
            wind_bounds=wind_bounds, pv_bounds=pv_bounds, battery_bounds=battery_bounds,
            selection=selection, wind_metadata=wind_metadata, pv_metadata=pv_metadata,
            catalog=catalog, economics_version=EconomicsVersion(economics_version),
        )
    elapsed = time.perf_counter() - started
    if not rows:
        return OptimizationOutcome(
            feasible=False, design=None, metrics={}, economics={}, optimizer_method=method,
            evaluated_portfolios=len(traces), dispatch_simulations=cache.simulations,
            elapsed_seconds=elapsed, generation_kwh=None, dispatch_cache_hits=cache.hits,
            theoretical_design_combinations=renewable_space * (1 + sum(value + 1 for value in battery_bounds.values())),
        )
    selected = min(
        rows,
        key=lambda row: (
            row["economics"]["net_present_cost_usd"],
            row["design"].wind_key or "",
            row["design"].wind_count,
            row["design"].pv_key or "",
            row["design"].pv_count,
            row["design"].battery_key or "",
            row["design"].battery_count,
        ),
    )
    portfolio = selected["portfolio"]
    return OptimizationOutcome(
        feasible=True,
        design=selected["design"],
        metrics=selected["metrics"],
        economics=selected["economics"],
        optimizer_method=method,
        evaluated_portfolios=len(traces),
        dispatch_simulations=cache.simulations,
        elapsed_seconds=elapsed, dispatch_cache_hits=cache.hits,
        theoretical_design_combinations=renewable_space * (1 + sum(value + 1 for value in battery_bounds.values())),
        generation_kwh=tuple(traces[portfolio.key]),
    )
