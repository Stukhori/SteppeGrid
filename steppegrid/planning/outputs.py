"""Deterministic, catalog-versioned scenario exports."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from steppegrid.planning.models import PlanningResult, PlanningScenario


@dataclass(frozen=True)
class ScenarioArtifacts:
    directory: Path
    scenario_json: Path
    result_json: Path
    reliability_csv: Path
    dispatch_csv: Path
    provenance_json: Path


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_scenario_outputs(
    scenario: PlanningScenario,
    result: PlanningResult,
    dispatch_rows: list[dict[str, object]],
    *,
    output_root: str | Path = "outputs/scenarios",
) -> ScenarioArtifacts:
    directory = Path(output_root) / scenario.scenario_id
    directory.mkdir(parents=True, exist_ok=True)
    scenario_path = directory / "scenario.json"
    result_path = directory / "result.json"
    reliability_path = directory / "reliability.csv"
    dispatch_path = directory / "dispatch.csv"
    provenance_path = directory / "provenance.json"
    scenario_path.write_bytes(_json_bytes({
        "schema_version": "phase16.v1",
        "scenario_id": scenario.scenario_id,
        "scenario_input_hash": scenario.input_hash,
        "site_id": scenario.site.site_id,
        "site_metadata_hash": scenario.site.site_metadata_hash,
        "demand_id": scenario.demand_id,
        "registered_demand_sha256": scenario.registered_demand_sha256,
        "scenario": scenario.model_dump(mode="json"),
    }))
    result_path.write_bytes(_json_bytes(result.model_dump(mode="json")))
    reliability_row = {
        "scenario_id": result.scenario_id,
        "site_id": result.site_id,
        "site_metadata_hash": result.site_metadata_hash,
        "demand_id": result.demand_id,
        "demand_sha256": result.demand_sha256,
        "equipment_catalog_version": result.equipment_catalog_version.value,
        "economics_version": result.economics_version.value,
        "target": result.reliability_target,
        "served_fraction": result.metrics.served_fraction if result.metrics else None,
        "served_energy_kwh": result.metrics.served_energy_kwh if result.metrics else None,
        "unmet_energy_kwh": result.metrics.unmet_energy_kwh if result.metrics else None,
        "loss_of_load_hours": result.metrics.loss_of_load_hours if result.metrics else None,
        "longest_deficit_hours": result.metrics.longest_deficit_hours if result.metrics else None,
        "feasible": result.feasible,
    }
    with reliability_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(reliability_row))
        writer.writeheader()
        writer.writerow(reliability_row)
    with dispatch_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(dispatch_rows[0]) if dispatch_rows else ["timestamp"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dispatch_rows)
    files = (scenario_path, result_path, reliability_path, dispatch_path)
    provenance_path.write_bytes(_json_bytes({
        "schema_version": "phase16.v1",
        "scenario_id": scenario.scenario_id,
        "scenario_input_hash": scenario.input_hash,
        "site_id": result.site_id,
        "site_metadata_hash": result.site_metadata_hash,
        "site_snapshot": result.site_snapshot.model_dump(mode="json") if result.site_snapshot else None,
        "demand_id": result.demand_id,
        "equipment_catalog_version": result.equipment_catalog_version.value,
        "economics_version": result.economics_version.value,
        "demand_sha256": result.demand_sha256,
        "weather_cache_key": result.weather_cache_key,
        "weather_cache_status": result.weather_cache_status,
        "weather_sha256": result.weather_sha256,
        "weather_source": result.weather_source,
        "weather_model": result.weather_model,
        "weather_start_utc": result.weather_start_utc.isoformat(),
        "weather_end_utc": result.weather_end_utc.isoformat(),
        "scenario_timezone": result.scenario_timezone,
        "software_version": result.software_version,
        "file_sha256": {path.name: _sha256(path) for path in files},
        "benchmark_outputs_modified": False,
    }))
    return ScenarioArtifacts(
        directory=directory,
        scenario_json=scenario_path,
        result_json=result_path,
        reliability_csv=reliability_path,
        dispatch_csv=dispatch_path,
        provenance_json=provenance_path,
    )
