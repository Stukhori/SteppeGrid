import math

import pytest

from steppegrid.equipment.catalog import EquipmentCatalogVersion, PLANNER_V2
from steppegrid.optimization.core import RenewablePortfolio, dispatch, scale_trace
from steppegrid.optimization.economics import EconomicsVersion, system_cost
from steppegrid.planning.models import TechnologySelection
from steppegrid.planning.optimizer import optimize_planning_trace


PV = "trina_tsm_450_neg9r28__sma_sunny_tripower_x_25"


def _brute(load, wind, pv, selection, wind_meta, pv_meta, target):
    annual = math.fsum(load)
    wind_bounds = {key: math.ceil(3 * annual / math.fsum(trace)) for key, trace in wind.items()}
    pv_bounds = {key: math.ceil(3 * annual / math.fsum(trace)) for key, trace in pv.items()}
    pairs = [(w, p) for w in selection.wind_keys for p in selection.pv_keys]
    best = None
    for wind_key, pv_key in pairs:
        for wc in range(wind_bounds[wind_key] + 1):
            for pc in range(pv_bounds[pv_key] + 1):
                if wc + pc == 0:
                    continue
                portfolio = RenewablePortfolio(wind_key if wc else None, wc, pv_key if pc else None, pc)
                generation = scale_trace(portfolio, wind, pv)
                for battery_key in (None, *selection.battery_keys):
                    maximum = 0 if battery_key is None else 4
                    for bc in range(maximum + 1):
                        if battery_key is None and bc:
                            continue
                        metrics = dispatch(load, generation, PLANNER_V2.batteries[battery_key] if battery_key and bc else None, bc)
                        if metrics["served_fraction"] + 1e-12 < target:
                            continue
                        costs = system_cost(
                            wind_kw=wc * wind_meta[wind_key]["rated_power_kw"],
                            pv_dc_kw=pc * pv_meta[pv_key]["dc_capacity_kw"],
                            pv_ac_kw=pc * pv_meta[pv_key]["ac_capacity_kw"],
                            battery_usable_kwh=(PLANNER_V2.batteries[battery_key].usable_energy_capacity_kwh * bc if battery_key else 0),
                            economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,
                        )
                        row = (costs["net_present_cost_usd"], wind_key if wc else None, wc, pv_key if pc else None, pc, battery_key if bc else None, bc)
                        best = row if best is None or row < best else best
    return best


@pytest.mark.parametrize("battery_keys", [(), ("sungrow_powerstack_st255_2h",), ("tesla_megapack_2h", "sungrow_powerstack_st510_4h")])
def test_v2_exact_search_matches_brute_force_with_mixed_equipment(battery_keys):
    load = [12.0 if hour % 24 in range(7, 20) else 5.0 for hour in range(72)]
    wind = {
        "sd6": [3.0 + (hour % 5) * .1 for hour in range(72)],
        "northern_power_nps_100c_21": [32.0 + (hour % 7) for hour in range(72)],
    }
    pv = {PV: [18.0 if hour % 24 in range(8, 18) else 0.0 for hour in range(72)]}
    wind_meta = {"sd6": {"rated_power_kw": 5.2}, "northern_power_nps_100c_21": {"rated_power_kw": 100}}
    pv_meta = {PV: {"dc_capacity_kw": 24.75, "ac_capacity_kw": 25}}
    selection = TechnologySelection(
        wind_keys=tuple(wind), pv_keys=(PV,), battery_keys=battery_keys
    )
    outcome = optimize_planning_trace(
        load_kwh=load, target=.95, wind_profiles_kwh=wind, pv_profiles_kwh=pv,
        wind_metadata=wind_meta, pv_metadata=pv_meta, selection=selection,
        equipment_catalog_version=EquipmentCatalogVersion.PLANNER_V2,
        economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,
    )
    brute = _brute(load, wind, pv, selection, wind_meta, pv_meta, .95)
    assert outcome.optimizer_method == "exact_reduced_space"
    assert outcome.feasible and outcome.design is not None and brute is not None
    assert outcome.economics["net_present_cost_usd"] == pytest.approx(brute[0])
    assert (outcome.design.wind_key, outcome.design.wind_count, outcome.design.pv_key, outcome.design.pv_count, outcome.design.battery_key, outcome.design.battery_count) == brute[1:]
    assert outcome.theoretical_design_combinations > outcome.evaluated_portfolios
