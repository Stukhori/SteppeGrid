"""Efficient cached dispatch and optimization primitives."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from steppegrid.equipment.models import BatterySystemSpec

DEFICIT_TOLERANCE_KWH = 1e-6
BALANCE_TOLERANCE_KWH = 1e-6


@dataclass(frozen=True)
class RenewablePortfolio:
    wind_key: str | None
    wind_count: int
    pv_key: str | None
    pv_count: int

    def __post_init__(self):
        if any(not isinstance(value, int) or value < 0 for value in (self.wind_count, self.pv_count)):
            raise ValueError("equipment counts must be nonnegative integers")
        if (self.wind_count > 0) != (self.wind_key is not None) or (self.pv_count > 0) != (self.pv_key is not None):
            raise ValueError("equipment key/count mismatch")
        if self.wind_count + self.pv_count == 0:
            raise ValueError("empty renewable portfolio")

    @property
    def key(self):
        return f"w={self.wind_key or 'none'}:{self.wind_count}|pv={self.pv_key or 'none'}:{self.pv_count}"


def scale_trace(portfolio: RenewablePortfolio, wind: Mapping[str, Sequence[float]],
                pv: Mapping[str, Sequence[float]]) -> list[float]:
    source = next(iter(wind.values()), next(iter(pv.values())))
    zeros = [0.0] * len(source)
    wt = wind[portfolio.wind_key] if portfolio.wind_key else zeros
    pt = pv[portfolio.pv_key] if portfolio.pv_key else zeros
    return [portfolio.wind_count * a + portfolio.pv_count * b for a, b in zip(wt, pt, strict=True)]


def annual_energy_sufficient(generation_kwh: float, load_kwh: float, target: float) -> bool:
    if generation_kwh < 0 or load_kwh <= 0 or not 0 <= target <= 1:
        raise ValueError("invalid annual-energy pruning input")
    return generation_kwh + 1e-9 >= target * load_kwh


def dispatch(load: Sequence[float], generation: Sequence[float], battery: BatterySystemSpec | None,
             count: int) -> dict:
    if len(load) != len(generation) or not load or count < 0 or not isinstance(count, int):
        raise ValueError("invalid dispatch inputs")
    if (battery is None) != (count == 0):
        raise ValueError("battery/count mismatch")
    capacity = minimum = usable = charge_kw = discharge_kw = 0.0
    charge_eff = discharge_eff = 1.0
    soc = None
    if battery:
        capacity = battery.nominal_energy_capacity_kwh * count
        minimum = capacity * battery.minimum_soc_fraction
        usable = battery.usable_energy_capacity_kwh * count
        charge_kw = battery.maximum_charge_power_kw * count
        discharge_kw = battery.maximum_discharge_power_kw * count
        charge_eff = discharge_eff = math.sqrt(battery.round_trip_efficiency)
        soc = minimum
    direct = charge = discharge = losses = curtailment = unmet = 0.0
    loss_hours = longest = run = 0; maximum_deficit = 0.0
    for demand, renewable in zip(load, generation, strict=True):
        served = min(demand, renewable); surplus = renewable - served; deficit = demand - served
        charged = delivered = flow_loss = 0.0
        if soc is not None:
            charged = min(surplus, charge_kw, (capacity - soc) / charge_eff)
            stored = charged * charge_eff; soc += stored
            delivered = min(deficit, discharge_kw, (soc - minimum) * discharge_eff)
            removed = delivered / discharge_eff; soc -= removed
            flow_loss = charged - stored + removed - delivered
        remaining = max(0.0, deficit - delivered)
        direct += served; charge += charged; discharge += delivered; losses += flow_loss
        curtailment += surplus - charged; unmet += remaining
        maximum_deficit = max(maximum_deficit, remaining)
        if remaining > DEFICIT_TOLERANCE_KWH:
            loss_hours += 1; run += 1; longest = max(longest, run)
        else: run = 0
    load_total = math.fsum(load); generation_total = math.fsum(generation)
    ending = soc if soc is not None else 0.0
    result = {"annual_load_kwh": load_total, "renewable_generation_kwh": generation_total,
        "direct_service_kwh": direct, "battery_charge_input_kwh": charge,
        "battery_discharge_delivered_kwh": discharge, "battery_losses_kwh": losses,
        "curtailment_kwh": curtailment,
        "curtailment_fraction": curtailment / generation_total if generation_total else 0.0,
        "served_energy_kwh": load_total - unmet, "unmet_energy_kwh": unmet,
        "served_fraction": 1 - unmet / load_total, "lpsp": unmet / load_total,
        "loss_of_load_hours": loss_hours, "longest_deficit_hours": longest,
        "maximum_hourly_deficit_kwh": maximum_deficit, "initial_soc_kwh": minimum,
        "ending_soc_kwh": ending, "initial_inventory_discharge_kwh": 0.0,
        "battery_throughput_kwh": charge + discharge,
        "equivalent_full_cycles": discharge / usable if usable else 0.0,
        "usable_battery_kwh": usable, "battery_charge_kw": charge_kw,
        "battery_discharge_kw": discharge_kw,
        "generation_balance_error_kwh": generation_total - direct - charge - curtailment,
        "load_balance_error_kwh": load_total - direct - discharge - unmet,
        "storage_balance_error_kwh": ending - minimum - (charge - discharge - losses)}
    if max(abs(result[key]) for key in ("generation_balance_error_kwh", "load_balance_error_kwh",
                                        "storage_balance_error_kwh")) > BALANCE_TOLERANCE_KWH:
        raise ArithmeticError("candidate violates energy conservation")
    return result


class DispatchCache:
    def __init__(self, loads, traces, batteries):
        self.loads = loads; self.traces = traces; self.batteries = batteries
        self.values = {}; self.hits = 0; self.simulations = 0; self.no_storage_simulations = 0
        self.ordered_evaluations_avoided = 0
        self.no_storage_seconds = 0.0; self.battery_seconds = 0.0

    def get(self, portfolio: RenewablePortfolio, shape: str, battery_key: str | None, count: int):
        # All zero-storage requests collapse to one canonical key.
        if count == 0: battery_key = None
        key = (portfolio.key, shape, battery_key, count)
        if key in self.values:
            self.hits += 1; return self.values[key]
        started=time.perf_counter()
        value = dispatch(self.loads[shape], self.traces[portfolio.key],
                         self.batteries[battery_key] if battery_key else None, count)
        elapsed=time.perf_counter()-started
        if count == 0: self.no_storage_seconds += elapsed
        else: self.battery_seconds += elapsed
        self.values[key] = value; self.simulations += 1
        if count == 0: self.no_storage_simulations += 1
        return value


def minimum_battery_count(cache: DispatchCache, portfolio: RenewablePortfolio, shapes: Sequence[str],
                          battery_key: str, target: float, maximum: int) -> tuple[int | None, dict]:
    evaluations = {}
    def feasible(count):
        if count not in evaluations:
            evaluations[count] = {shape: cache.get(portfolio, shape, battery_key, count) for shape in shapes}
        return min(row["served_fraction"] for row in evaluations[count].values()) + 1e-12 >= target
    if feasible(0):
        cache.ordered_evaluations_avoided += maximum * len(shapes); return 0, evaluations
    if not feasible(maximum):
        cache.ordered_evaluations_avoided += max(0, maximum + 1 - len(evaluations)) * len(shapes); return None, evaluations
    low, high = 0, maximum
    while high - low > 1:
        middle = (low + high) // 2
        if feasible(middle): high = middle
        else: low = middle
    cache.ordered_evaluations_avoided += max(0, maximum + 1 - len(evaluations)) * len(shapes)
    return high, evaluations

def next_selective_battery_bound(selected_count: int, current_maximum: int) -> int | None:
    if selected_count != current_maximum: return None
    if current_maximum == 4: return 6
    if current_maximum == 6: return 8
    return None


def pareto_cost_reliability(rows):
    ordered = sorted(rows, key=lambda row: (row["net_present_cost_usd"], -row["worst_served_fraction"], row["design_key"]))
    frontier = []; best = -1.0
    for row in ordered:
        if row["worst_served_fraction"] > best + 1e-12:
            frontier.append(row); best = row["worst_served_fraction"]
    return frontier

def physically_nondominated(rows):
    kept=[]
    for candidate in rows:
        d=candidate["design"]
        group=[other for other in rows if other["optimization_mode"]==candidate["optimization_mode"]
          and other["target"]==candidate["target"] and other["design"]["wind_key"]==d["wind_key"]
          and other["design"]["pv_key"]==d["pv_key"] and other["design"]["battery_key"]==d["battery_key"]]
        dominated=False
        for other in group:
            od=other["design"]
            quantities=(od["wind_count"]<=d["wind_count"] and od["pv_count"]<=d["pv_count"]
                        and od["battery_count"]<=d["battery_count"])
            reliability=all(other["performance"][shape]["served_fraction"]+1e-12>=candidate["performance"][shape]["served_fraction"]
                            for shape in candidate["performance"])
            curtailment=all(other["performance"][shape]["curtailment_kwh"]<=candidate["performance"][shape]["curtailment_kwh"]+1e-9
                            for shape in candidate["performance"])
            strict=(od["wind_count"],od["pv_count"],od["battery_count"])!=(d["wind_count"],d["pv_count"],d["battery_count"])
            if quantities and reliability and curtailment and strict:
                dominated=True;break
        if not dominated:kept.append(candidate)
    return kept
