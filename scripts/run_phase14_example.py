"""Run one explicit-demand Shamshi Phase 14 example (never a field optimum)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from steppegrid.planning.models import (
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an estimated-demand Shamshi planning scenario."
    )
    parser.add_argument(
        "--annual-kwh", required=True, type=float,
        help="Explicit annual demand estimate in kWh/year (10,000 to 20,000,000).",
    )
    parser.add_argument("--target", choices=("0.95", "0.99"), default="0.95")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/scenarios"))
    args = parser.parse_args()
    scenario = PlanningScenario(
        name=f"Shamshi {args.annual_kwh:g} kWh explicit estimate example",
        site=PlanningSite(
            preset=SitePreset.SHAMSHI,
            name="Shamshi Kaldayakova",
            latitude=50.578333,
            longitude=57.544722,
            country="Kazakhstan",
            timezone_offset="+05:00",
        ),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            profile_shape="community_facility_like",
            annual_kwh=args.annual_kwh,
            method_notes=(
                "Explicit Phase 14 example assumption supplied on the command line and "
                "distributed with the deterministic community-facility-like profile; "
                "not observed Shamshi demand."
            ),
        ),
        reliability_target=float(args.target),
        technologies=TechnologySelection(
            wind_keys=("sd6",),
            pv_keys=("trina_tsm_450_neg9r28__sma_core1_stp50_41",),
            battery_keys=("tesla_megapack_2h",),
        ),
    )
    started = time.perf_counter()
    run = ScenarioPlanningService(output_root=args.output_root).run(
        scenario, progress=lambda message: print(f"[phase14] {message}")
    )
    wall_seconds = time.perf_counter() - started
    print(json.dumps({
        "label": "estimated-demand planning scenario; not a field optimum",
        "scenario_id": run.result.scenario_id,
        "annual_demand_kwh": run.demand.annual_kwh,
        "result": run.result.model_dump(mode="json"),
        "total_wall_seconds": wall_seconds,
        "output_directory": str(run.artifacts.directory) if run.artifacts else None,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
