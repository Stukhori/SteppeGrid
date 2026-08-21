"""Application service layer over frozen outputs and existing model components."""

from __future__ import annotations

import math
from functools import cached_property, lru_cache
from pathlib import Path

import pandas as pd

from steppegrid.app.data import AppDataError, FrozenDataRepository
from steppegrid.benchmarks.phase10 import precompute
from steppegrid.equipment.catalog import BATTERIES
from steppegrid.optimization.core import RenewablePortfolio, dispatch, scale_trace
from steppegrid.simulation.battery import BatteryState
from steppegrid.simulation.models import BatteryConfig


def _number(row: dict[str, str], key: str, kind=float):
    return kind(row[key])


class PlanningService:
    """Read-only planning queries; no optimization method is exposed."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.repository = FrozenDataRepository(root)
        self.repository.validate()

    @cached_property
    def designs(self) -> dict[float, dict]:
        result = {}
        for raw in self.repository.rows("designs"):
            row = dict(raw)
            for key in (
                "target", "installed_wind_kw", "installed_pv_dc_kw", "installed_pv_ac_kw",
                "installed_usable_battery_kwh", "battery_power_kw", "worst_served_fraction",
                "unmet_energy_kwh", "lpsp", "maximum_hourly_deficit_kwh", "curtailment_kwh",
                "initial_capex_usd", "net_present_cost_usd", "equivalent_annual_cost_usd",
                "cost_per_served_kwh_usd",
            ):
                row[key] = float(row[key])
            for key in ("wind_count", "pv_count", "battery_count", "loss_of_load_hours", "longest_deficit_hours"):
                row[key] = int(row[key])
            result[row["target"]] = row
        return result

    def design(self, target: float) -> dict:
        try:
            return self.designs[target]
        except KeyError as error:
            raise ValueError("target must identify a frozen 95% or 99% design") from error

    def benchmark_rows(self) -> list[dict]:
        rows = []
        for raw in self.repository.rows("benchmark"):
            row = dict(raw)
            for key in ("value", "capacity_factor", "specific_yield_kwh_per_kwp", "clipping_kwh"):
                row[key] = float(row[key]) if row.get(key) else None
            rows.append(row)
        return rows

    def reliability_rows(self, target: float | None = None) -> list[dict]:
        rows = []
        for raw in self.repository.rows("reliability"):
            row = dict(raw)
            row["target"] = float(row["target"])
            row["served_fraction"] = float(row["served_fraction"])
            row["served_energy_kwh"] = float(row["served_energy_kwh"])
            row["unmet_energy_kwh"] = float(row["unmet_energy_kwh"])
            row["loss_of_load_hours"] = int(row["loss_of_load_hours"])
            row["longest_deficit_hours"] = int(row["longest_deficit_hours"])
            if target is None or row["target"] == target:
                rows.append(row)
        return rows

    def sensitivity_rows(self, target: float | None = None) -> list[dict]:
        rows = []
        for raw in self.repository.rows("sensitivity"):
            row = dict(raw)
            row["target"] = float(row["target"])
            row["wind_shear_alpha"] = float(row["wind_shear_alpha"])
            row["served_fraction"] = float(row["served_fraction"])
            row["passes_target"] = row["passes_target"].lower() == "true"
            row["loss_of_load_hours"] = int(row["loss_of_load_hours"])
            row["longest_deficit_hours"] = int(row["longest_deficit_hours"])
            if target is None or row["target"] == target:
                rows.append(row)
        return rows

    def fixed_sensitivity_rows(self, target: float) -> list[dict]:
        """Return the binding profile for every fixed-design Phase 11 scenario."""
        grouped: dict[str, list[dict]] = {}
        for raw in self.repository.rows("fixed_sensitivity"):
            if float(raw["target"]) != target:
                continue
            row = dict(raw)
            for key in ("served_fraction", "net_present_cost_usd", "equivalent_annual_cost_usd"):
                row[key] = float(row[key])
            for key in ("loss_of_load_hours", "longest_deficit_hours"):
                row[key] = int(row[key])
            row["passes_target"] = row["served_fraction"] + 1e-12 >= target
            grouped.setdefault(row["scenario"], []).append(row)
        return [min(rows, key=lambda row: row["served_fraction"]) for rows in grouped.values()]

    def nominal_dispatch_summary(self, target: float) -> dict:
        """Return the frozen nominal binding-profile annual flows for a final design."""
        rows = [row for row in self.repository.rows("fixed_sensitivity")
                if row["scenario"] == "nominal" and float(row["target"]) == target]
        if not rows:
            raise AppDataError(f"No saved nominal replay exists for target {target}")
        selected = min(rows, key=lambda row: float(row["served_fraction"]))
        result = dict(selected)
        for key in (
            "annual_raw_renewable_generation_kwh", "wind_generation_kwh", "pv_generation_kwh",
            "served_energy_kwh", "served_fraction", "unmet_energy_kwh", "curtailed_energy_kwh",
            "battery_charge_kwh", "battery_discharge_kwh", "ending_soc_kwh",
        ):
            result[key] = float(result[key])
        return result

    def margin_rows(self) -> list[dict]:
        rows = []
        for raw in self.repository.rows("margins"):
            row = dict(raw)
            for key in (
                "target", "maximum_demand_multiplier_for_target", "minimum_pv_multiplier_for_target",
                "minimum_wind_shear_for_target", "maximum_wind_shear_for_target",
                "wind_tested_low_served_fraction", "wind_tested_nominal_served_fraction",
                "wind_tested_high_served_fraction",
            ):
                row[key] = float(row[key])
            rows.append(row)
        return rows

    def provenance(self) -> dict:
        return self.repository.json("provenance")

    def validation(self) -> dict:
        return self.repository.json("audit")

    def assumptions(self) -> list[dict[str, str]]:
        return [dict(row) for row in self.repository.rows("assumptions")]

    def adaptation_metadata(self) -> dict:
        summary = self.repository.json("phase11_summary")
        return {
            "adaptation_method": summary.get("adaptation_method"),
            "full_reoptimization_performed": summary.get("full_reoptimization_performed"),
            "single_profile_comparison_provenance": summary.get("single_profile_comparison_provenance"),
        }

    @lru_cache(maxsize=1)
    def _model_inputs(self):
        project = Path(__file__).resolve().parents[2]
        cached = self.provenance()["weather"].get("cached_inputs", [])
        missing = [entry["path"] for entry in cached
                   if not (project / Path(entry["path"].replace("\\", "/"))).is_file()]
        if missing:
            raise AppDataError(
                "The frozen ERA5 runtime package is incomplete. Before deployment, run "
                "`python scripts/check_deployment_assets.py`. For local use, restore the "
                "provenance-listed cache files before opening hourly views. The app never fetches "
                "live weather during normal navigation. "
                "Missing: " + ", ".join(missing)
            )
        weather, phase9, loads, load_meta, wind, pv, _ = precompute()
        return weather, phase9, loads, load_meta, wind, pv

    def demand_weather_frame(self, profile: str) -> pd.DataFrame:
        weather, _, loads, _, _, _ = self._model_inputs()
        if profile not in loads:
            raise ValueError(f"unknown reconstructed load profile: {profile}")
        series = weather.series
        return pd.DataFrame({
            "timestamp": pd.to_datetime(series.timestamps).tz_convert("Asia/Almaty"),
            "load_kwh": loads[profile],
            "wind_speed_10m_m_s": series.wind_speed_m_s,
            "wind_speed_100m_m_s": series.wind_speed_100m_m_s,
            "ghi_w_m2": series.solar_irradiance_w_m2,
            "temperature_c": series.temperature_c,
        })

    def demand_comparison_frame(self) -> pd.DataFrame:
        weather, _, loads, _, _, _ = self._model_inputs()
        values = {"timestamp": pd.to_datetime(weather.series.timestamps).tz_convert("Asia/Almaty")}
        values.update(loads)
        return pd.DataFrame(values)

    def generation_catalog(self) -> tuple[list[dict], list[dict]]:
        _, phase9, _, _, _, _ = self._model_inputs()
        wind = [dict(equipment_key=key, **value) for key, value in phase9.wind.items() if key != "resource"]
        pv = [dict(equipment_key=key, **value) for key, value in phase9.pv.items()]
        return wind, pv

    def generation_frame(self, wind_key: str, pv_key: str) -> pd.DataFrame:
        weather, _, _, _, wind, pv = self._model_inputs()
        if wind_key not in wind or pv_key not in pv:
            raise ValueError("unknown frozen equipment trace")
        return pd.DataFrame({
            "timestamp": pd.to_datetime(weather.series.timestamps).tz_convert("Asia/Almaty"),
            "wind_kwh_per_unit": wind[wind_key],
            "pv_kwh_per_block": pv[pv_key],
        })

    @lru_cache(maxsize=6)
    def dispatch_frame(self, target: float, profile: str) -> pd.DataFrame:
        design = self.design(target)
        weather, _, loads, _, wind, pv = self._model_inputs()
        if profile not in loads:
            raise ValueError(f"unknown reconstructed load profile: {profile}")
        portfolio = RenewablePortfolio(
            design["wind_key"], design["wind_count"], design["pv_key"], design["pv_count"]
        )
        generation = scale_trace(portfolio, wind, pv)
        wind_total = [design["wind_count"] * value for value in wind[design["wind_key"]]]
        pv_total = [design["pv_count"] * value for value in pv[design["pv_key"]]]
        battery = BATTERIES[design["battery_key"]]
        count = design["battery_count"]
        capacity = battery.nominal_energy_capacity_kwh * count
        minimum = capacity * battery.minimum_soc_fraction
        efficiency = math.sqrt(battery.round_trip_efficiency)
        battery_state = BatteryState(BatteryConfig(
            capacity_kwh=capacity,
            initial_soc_kwh=minimum,
            minimum_soc_kwh=minimum,
            maximum_charge_kw=battery.maximum_charge_power_kw * count,
            maximum_discharge_kw=battery.maximum_discharge_power_kw * count,
            charging_efficiency=efficiency,
            discharging_efficiency=efficiency,
        ))
        records = []
        for timestamp, load, wind_hour, pv_hour, renewable in zip(
            weather.series.timestamps, loads[profile], wind_total, pv_total, generation, strict=True
        ):
            direct = min(load, renewable)
            surplus = renewable - direct
            deficit = load - direct
            charge = battery_state.charge(surplus).bus_energy_kwh
            discharge = battery_state.discharge(deficit).bus_energy_kwh
            records.append({
                "timestamp": timestamp,
                "load_kwh": load,
                "wind_generation_kwh": wind_hour,
                "pv_generation_kwh": pv_hour,
                "total_generation_kwh": renewable,
                "battery_soc_kwh": max(0.0, battery_state.soc_kwh),
                "unmet_energy_kwh": max(0.0, deficit - discharge),
                "curtailment_kwh": max(0.0, surplus - charge),
            })
        aggregate = dispatch(loads[profile], generation, battery, count)
        if abs(sum(row["unmet_energy_kwh"] for row in records) - aggregate["unmet_energy_kwh"]) > 1e-6:
            raise ArithmeticError("hourly replay does not match the established dispatch aggregate")
        frame = pd.DataFrame(records)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_convert("Asia/Almaty")
        return frame

    @lru_cache(maxsize=6)
    def deficit_events(self, target: float, profile: str) -> pd.DataFrame:
        """Summarize contiguous deficit runs from an existing deterministic dispatch replay."""
        frame = self.dispatch_frame(target, profile)
        events = []
        start = None
        energy_total = maximum = 0.0
        duration = 0
        previous_timestamp = None
        for row in frame.itertuples(index=False):
            if row.unmet_energy_kwh > 1e-6:
                if start is None:
                    start = row.timestamp; energy_total = maximum = 0.0; duration = 0
                duration += 1
                energy_total += row.unmet_energy_kwh
                maximum = max(maximum, row.unmet_energy_kwh)
                previous_timestamp = row.timestamp
            elif start is not None:
                events.append({"start": start, "end": previous_timestamp, "duration_hours": duration,
                               "unmet_energy_kwh": energy_total, "maximum_hourly_deficit_kwh": maximum})
                start = None
        if start is not None:
            events.append({"start": start, "end": previous_timestamp, "duration_hours": duration,
                           "unmet_energy_kwh": energy_total, "maximum_hourly_deficit_kwh": maximum})
        return pd.DataFrame(events, columns=["start", "end", "duration_hours", "unmet_energy_kwh", "maximum_hourly_deficit_kwh"])
