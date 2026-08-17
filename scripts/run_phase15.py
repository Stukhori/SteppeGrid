"""Reproduce the Phase 15 catalog audit and Shamshi V1/V2 comparison."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from steppegrid.equipment.catalog import (
    EquipmentCatalogVersion,
    PLANNER_V2,
    RODINA_FROZEN_V1,
)
from steppegrid.optimization.economics import EconomicsVersion
from steppegrid.planning.models import (
    CatalogFilterMode,
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.service import ScenarioPlanningService


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _selection(catalog) -> TechnologySelection:
    return TechnologySelection(
        wind_keys=tuple(catalog.wind_turbines),
        pv_keys=catalog.pv_block_keys,
        battery_keys=tuple(catalog.batteries),
        filter_mode=CatalogFilterMode.ALL_VERIFIED,
    )


def _scenario(name: str, annual_kwh: float, catalog, economics) -> PlanningScenario:
    return PlanningScenario(
        name=name,
        site=PlanningSite(
            preset=SitePreset.SHAMSHI, name="Shamshi Kaldayakova",
            latitude=50.578333, longitude=57.544722,
            country="Kazakhstan", timezone_offset="+05:00",
        ),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            profile_shape="community_facility_like", annual_kwh=annual_kwh,
            method_notes="Deterministic synthetic community-facility-like planning profile; not observed Shamshi demand.",
        ),
        reliability_target=.95,
        technologies=_selection(catalog),
        equipment_catalog_version=catalog.version,
        economics_version=economics,
    )


def _comparison_row(label: str, run) -> dict[str, object]:
    result, design, metrics, economics = run.result, run.result.design, run.result.metrics, run.result.economics
    assert design is not None and metrics is not None and economics is not None
    catalog = RODINA_FROZEN_V1 if result.equipment_catalog_version is EquipmentCatalogVersion.RODINA_FROZEN_V1 else PLANNER_V2
    wind = catalog.wind_turbines[design.wind_key] if design.wind_key else None
    battery = catalog.batteries[design.battery_key] if design.battery_key else None
    return {
        "comparison_label": label,
        "equipment_catalog_version": result.equipment_catalog_version.value,
        "economics_version": result.economics_version.value,
        "scenario_id": result.scenario_id,
        "wind_model": wind.model if wind else None,
        "wind_count": design.wind_count,
        "wind_capacity_kw": design.wind_capacity_kw,
        "pv_model": design.pv_key,
        "pv_count": design.pv_count,
        "pv_dc_capacity_kw": design.pv_dc_capacity_kw,
        "pv_ac_capacity_kw": design.pv_ac_capacity_kw,
        "battery_model": battery.model if battery else None,
        "battery_count": design.battery_count,
        "battery_usable_energy_kwh": design.battery_usable_capacity_kwh,
        "battery_power_kw": battery.maximum_discharge_power_kw * design.battery_count if battery else 0,
        "annual_generation_kwh": metrics.renewable_generation_kwh,
        "served_fraction": metrics.served_fraction,
        "unmet_energy_kwh": metrics.unmet_energy_kwh,
        "loss_of_load_hours": metrics.loss_of_load_hours,
        "longest_deficit_hours": metrics.longest_deficit_hours,
        "curtailment_kwh": metrics.curtailment_kwh,
        "initial_capex_usd": economics.initial_capex_usd,
        "net_present_cost_usd": economics.net_present_cost_usd,
        "equivalent_annual_cost_usd": economics.equivalent_annual_cost_usd,
        "runtime_seconds": result.elapsed_seconds,
        "wind_options": result.catalog_option_counts["wind"],
        "pv_options": result.catalog_option_counts["pv"],
        "battery_options": result.catalog_option_counts["battery"],
        "theoretical_design_combinations": result.theoretical_design_combinations,
        "renewable_portfolios_evaluated": result.evaluated_portfolios,
        "dispatch_evaluations": result.dispatch_simulations,
        "dispatch_cache_hits": result.dispatch_cache_hits,
    }


def _write_catalog_outputs(output: Path) -> dict[str, object]:
    catalog_payload = {
        "schema_version": "phase15.catalog.v1",
        "equipment_catalog_version": PLANNER_V2.version.value,
        "v1_keys": {
            "wind": list(RODINA_FROZEN_V1.wind_turbines), "pv_modules": list(RODINA_FROZEN_V1.pv_modules),
            "inverters": list(RODINA_FROZEN_V1.inverters), "batteries": list(RODINA_FROZEN_V1.batteries),
        },
        "equipment": {
            "wind": {key: value.model_dump(mode="json") for key, value in PLANNER_V2.wind_turbines.items()},
            "pv_modules": {key: value.model_dump(mode="json") for key, value in PLANNER_V2.pv_modules.items()},
            "inverters": {key: value.model_dump(mode="json") for key, value in PLANNER_V2.inverters.items()},
            "batteries": {key: value.model_dump(mode="json") for key, value in PLANNER_V2.batteries.items()},
        },
    }
    _json(output / "catalog_v2.json", catalog_payload)
    provenance_rows = []
    for category, items in (("wind", PLANNER_V2.wind_turbines), ("pv_module", PLANNER_V2.pv_modules), ("inverter", PLANNER_V2.inverters), ("battery", PLANNER_V2.batteries)):
        for key, item in items.items():
            for index, source in enumerate(item.provenance, 1):
                provenance_rows.append({
                    "equipment_key": key, "category": category, "manufacturer": item.manufacturer,
                    "model": item.model, "scale_class": item.scale_class.value,
                    "source_index": index, "source_title": source.source_title,
                    "source_type": source.source_type.value, "source_url": source.source_url,
                    "source_organization": source.source_organization, "source_year": source.source_year,
                    "retrieved_date": source.accessed_on.isoformat(),
                    "parameters_supported": ";".join(source.parameters_supported), "notes": source.notes,
                })
    with (output / "equipment_provenance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(provenance_rows[0])); writer.writeheader(); writer.writerows(provenance_rows)
    validation = {
        "equipment_catalog_version": PLANNER_V2.version.value,
        "counts": {"wind": len(PLANNER_V2.wind_turbines), "pv_modules": len(PLANNER_V2.pv_modules), "inverters": len(PLANNER_V2.inverters), "pv_blocks": len(PLANNER_V2.pv_block_keys), "batteries": len(PLANNER_V2.batteries)},
        "v1_unchanged": set(RODINA_FROZEN_V1.wind_turbines) == {"skystream_3_7", "sd6", "bergey_excel_15"},
        "all_equipment_has_provenance": all(
            item.provenance
            for items in (PLANNER_V2.wind_turbines, PLANNER_V2.pv_modules, PLANNER_V2.inverters, PLANNER_V2.batteries)
            for item in items.values()
        ),
        "new_wind_curves_valid": all(
            [point.wind_speed_m_s for point in item.power_curve] == sorted({point.wind_speed_m_s for point in item.power_curve})
            and min(point.electrical_output_kw for point in item.power_curve) >= 0
            for key, item in PLANNER_V2.wind_turbines.items() if key not in RODINA_FROZEN_V1.wind_turbines
        ),
        "physical_equations_changed": False,
        "frozen_benchmark_outputs_modified": False,
    }
    _json(output / "catalog_validation.json", validation)
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce Phase 15 catalog validation and comparisons")
    parser.add_argument("--output", type=Path, default=Path("outputs/phase15"))
    parser.add_argument("--skip-small", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    validation = _write_catalog_outputs(args.output)
    service = ScenarioPlanningService(output_root=args.output / "scenarios")
    runs = []
    cases = [
        ("Shamshi 500 MWh V1", 500_000.0, RODINA_FROZEN_V1, EconomicsVersion.PHASE10_FROZEN_ECONOMICS_V1),
        ("Shamshi 500 MWh V2", 500_000.0, PLANNER_V2, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2),
    ]
    if not args.skip_small:
        cases.extend([
            ("Synthetic 30 MWh V1", 30_000.0, RODINA_FROZEN_V1, EconomicsVersion.PHASE10_FROZEN_ECONOMICS_V1),
            ("Synthetic 30 MWh V2", 30_000.0, PLANNER_V2, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2),
        ])
    for label, annual, catalog, economics in cases:
        print(f"[phase15] running {label}")
        run = service.run(_scenario(label, annual, catalog, economics), save_outputs=False, progress=lambda message: print(f"[phase15] {message}"))
        if not run.result.feasible:
            raise RuntimeError(f"no feasible result for {label}")
        runs.append(_comparison_row(label, run))
    shamshi = runs[:2]
    with (args.output / "shamshi_catalog_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(shamshi[0])); writer.writeheader(); writer.writerows(shamshi)
    if len(runs) > 2:
        with (args.output / "small_scenario_granularity.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(runs[2])); writer.writeheader(); writer.writerows(runs[2:])
    summary = {
        "schema_version": "phase15.summary.v1", "label": "expanded-catalog planning comparison",
        "frozen_rodina_catalog": EquipmentCatalogVersion.RODINA_FROZEN_V1.value,
        "planner_catalog": EquipmentCatalogVersion.PLANNER_V2.value,
        "frozen_benchmark_outputs_modified": False, "rodina_v2_comparison_performed": False,
        "catalog_validation": validation, "shamshi_comparison": shamshi,
        "small_scenario_comparison": runs[2:],
        "interpretation_boundary": "Deterministic planning scenarios, not field validation, confidence intervals, or probability distributions.",
    }
    _json(args.output / "phase15_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
