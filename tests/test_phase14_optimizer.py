import math

import pytest

from steppegrid.optimization.core import RenewablePortfolio, dispatch, scale_trace
from steppegrid.optimization.economics import system_cost
from steppegrid.planning.models import TechnologySelection
from steppegrid.planning.optimizer import SearchLimits, optimize_planning_trace

PV_KEY = "trina_tsm_450_neg9r28__sma_core1_stp50_41"
WIND_META = {"sd6": {"rated_power_kw": 5.2}}
PV_META = {PV_KEY: {"dc_capacity_kw": 49.95, "ac_capacity_kw": 50.0}}


def _brute(load, wind, pv, selection, target):
    annual = math.fsum(load)
    wind_bounds = {key: math.ceil(3 * annual / math.fsum(trace)) for key, trace in wind.items()}
    pv_bounds = {key: math.ceil(3 * annual / math.fsum(trace)) for key, trace in pv.items()}
    pairs = (
        [(w, p) for w in selection.wind_keys for p in selection.pv_keys]
        if selection.wind_keys and selection.pv_keys
        else [(w, None) for w in selection.wind_keys]
        if selection.wind_keys
        else [(None, p) for p in selection.pv_keys]
    )
    candidates = []
    for wind_key, pv_key in pairs:
        for wind_count in range(wind_bounds.get(wind_key, 0) + 1):
            for pv_count in range(pv_bounds.get(pv_key, 0) + 1):
                if wind_count + pv_count == 0:
                    continue
                portfolio = RenewablePortfolio(
                    wind_key if wind_count else None, wind_count,
                    pv_key if pv_count else None, pv_count,
                )
                metrics = dispatch(load, scale_trace(portfolio, wind, pv), None, 0)
                if metrics["served_fraction"] + 1e-12 < target:
                    continue
                costs = system_cost(
                    wind_kw=wind_count * (5.2 if wind_key else 0),
                    pv_dc_kw=pv_count * (49.95 if pv_key else 0),
                    pv_ac_kw=pv_count * (50 if pv_key else 0),
                    battery_usable_kwh=0,
                )
                candidates.append((
                    costs["net_present_cost_usd"],
                    wind_key if wind_count else None, wind_count,
                    pv_key if pv_count else None, pv_count,
                ))
    return min(candidates)


@pytest.mark.parametrize(
    "wind,pv,selection",
    [
        ({"sd6": [0.6] * 8760}, {}, TechnologySelection(wind_keys=("sd6",))),
        ({}, {PV_KEY: [0.5 if index % 2 else 1.5 for index in range(8760)]}, TechnologySelection(pv_keys=(PV_KEY,))),
        (
            {"sd6": [0.4] * 8760},
            {PV_KEY: [0.2 if index % 2 else 1.8 for index in range(8760)]},
            TechnologySelection(wind_keys=("sd6",), pv_keys=(PV_KEY,)),
        ),
    ],
)
def test_generalized_exact_reduced_search_matches_brute_force(wind, pv, selection):
    load = [1.0] * 8760
    outcome = optimize_planning_trace(
        load_kwh=load, target=0.95,
        wind_profiles_kwh=wind, pv_profiles_kwh=pv,
        wind_metadata=WIND_META, pv_metadata=PV_META,
        selection=selection,
    )
    brute = _brute(load, wind, pv, selection, 0.95)
    assert outcome.optimizer_method == "exact_reduced_space"
    assert outcome.feasible
    assert outcome.design is not None
    assert outcome.economics["net_present_cost_usd"] == pytest.approx(brute[0])
    assert (outcome.design.wind_key, outcome.design.wind_count, outcome.design.pv_key, outcome.design.pv_count) == brute[1:]
    assert outcome.metrics["served_fraction"] >= 0.95


def test_phase10_staged_path_matches_brute_force_for_reduced_monotonic_ray():
    load = [1.0] * 8760
    wind = {"sd6": [0.6] * 8760}
    selection = TechnologySelection(wind_keys=("sd6",))
    outcome = optimize_planning_trace(
        load_kwh=load, target=0.99, wind_profiles_kwh=wind, pv_profiles_kwh={},
        wind_metadata=WIND_META, pv_metadata={}, selection=selection,
        limits=SearchLimits(exact_renewable_portfolio_limit=0),
    )
    brute = _brute(load, wind, {}, selection, 0.99)
    assert outcome.optimizer_method == "phase10_staged_generalized"
    assert outcome.economics["net_present_cost_usd"] == pytest.approx(brute[0])
    assert outcome.design.wind_count == brute[2]


def test_search_rejects_unsupported_equipment_scale():
    with pytest.raises(ValueError, match="equipment-count search bound"):
        optimize_planning_trace(
            load_kwh=[1.0] * 8760, target=0.95,
            wind_profiles_kwh={"sd6": [1e-9] * 8760}, pv_profiles_kwh={},
            wind_metadata=WIND_META, pv_metadata={},
            selection=TechnologySelection(wind_keys=("sd6",)),
        )
