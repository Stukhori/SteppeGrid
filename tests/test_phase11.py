import math

import pytest

from steppegrid.benchmarks.phase9 import benchmark_wind, load_phase9_weather
from steppegrid.benchmarks.phase11 import (ADAPTATION_METHOD, ALPHA_NOMINAL, SELECTION_SCOPE, SensitivityScenario,
    monotonic_threshold, scale_nonnegative, scenarios, select_least_cost)
from steppegrid.equipment.catalog import WIND_TURBINES
from steppegrid.optimization.core import dispatch
from steppegrid.optimization.economics import system_cost
from steppegrid.simulation.wind import commercial_turbine_output_kw


def test_scenario_catalog_is_one_factor_at_a_time_except_declared_combined_cases():
    catalog={scenario.name:scenario for scenario in scenarios()}
    assert catalog["nominal"] == SensitivityScenario("nominal", "baseline")
    assert {"demand_low","demand_high","wind_shear_low","wind_shear_high","pv_low","pv_high",
            "wind_capex_low","wind_capex_high","pv_capex_low","pv_capex_high",
            "battery_capex_low","battery_capex_high","resource_stress","resource_favorable"} <= catalog.keys()
    baseline=SensitivityScenario("x")
    fields=("demand_multiplier","wind_shear_alpha","pv_generation_multiplier","wind_capex_multiplier",
            "pv_capex_multiplier","battery_capex_multiplier")
    for scenario in catalog.values():
        if scenario.category == "one_factor":
            assert sum(getattr(scenario,key)!=getattr(baseline,key) for key in fields)==1
    assert catalog["wind_shear_low"].wind_shear_alpha == pytest.approx(.18540883984)
    assert catalog["wind_shear_high"].wind_shear_alpha == pytest.approx(.27811325976)
    assert catalog["resource_stress"].wind_shear_alpha == catalog["wind_shear_high"].wind_shear_alpha
    assert catalog["resource_favorable"].wind_shear_alpha == catalog["wind_shear_low"].wind_shear_alpha
    assert catalog["resource_stress"].demand_multiplier == 1.1
    assert catalog["resource_stress"].pv_generation_multiplier == .9
    assert catalog["resource_favorable"].demand_multiplier == .9
    assert catalog["resource_favorable"].pv_generation_multiplier == 1.1


def test_demand_and_pv_scaling_preserves_shape_and_declared_energy_ratio():
    nominal=[0.0,1.0,2.5,8.0]
    for multiplier in (.9,1.1):
        scaled=scale_nonnegative(nominal,multiplier)
        assert math.fsum(scaled)==pytest.approx(math.fsum(nominal)*multiplier)
        assert scaled==pytest.approx([value*multiplier for value in nominal])
        assert min(scaled)>=0


def test_nominal_economics_exact_and_capex_changes_are_isolated():
    kwargs=dict(wind_kw=100,pv_dc_kw=200,pv_ac_kw=180,battery_usable_kwh=300)
    nominal=system_cost(**kwargs)
    explicit=system_cost(**kwargs,wind_capex_multiplier=1,pv_capex_multiplier=1,battery_capex_multiplier=1)
    assert explicit==nominal
    wind_low=system_cost(**kwargs,wind_capex_multiplier=.8)
    pv_low=system_cost(**kwargs,pv_capex_multiplier=.8)
    no_wind=system_cost(**{**kwargs,"wind_kw":0})
    no_pv=system_cost(**{**kwargs,"pv_dc_kw":0,"pv_ac_kw":0})
    assert nominal["initial_capex_usd"]-wind_low["initial_capex_usd"] == pytest.approx(100*8425*.2)
    assert nominal["initial_capex_usd"]-pv_low["initial_capex_usd"] == pytest.approx(200*1990*.2)
    assert system_cost(**{**kwargs,"wind_kw":0},wind_capex_multiplier=.8)==no_wind
    assert system_cost(**{**kwargs,"pv_dc_kw":0,"pv_ac_kw":0},pv_capex_multiplier=.8)==no_pv
    assert nominal["economic_classes"]["pv"]==pv_low["economic_classes"]["pv"]


def test_threshold_search_on_synthetic_monotonic_cases():
    assert monotonic_threshold(lambda x:x>=1.2,.5,2)==pytest.approx(1.2,abs=2e-9)
    assert monotonic_threshold(lambda x:x<=1.2,.5,2,lowest=False)==pytest.approx(1.2,abs=2e-9)
    assert monotonic_threshold(lambda x:False,0,1) is None


def test_capex_multiplier_does_not_enter_physical_scenario_parameters():
    low=next(s for s in scenarios() if s.name=="battery_capex_low")
    assert low.demand_multiplier==low.pv_generation_multiplier==1
    assert low.wind_shear_alpha==ALPHA_NOMINAL
    assert ADAPTATION_METHOD=="saved_phase10_candidate_reselection"
    assert SELECTION_SCOPE=="least-cost feasible design among the saved Phase 10 candidate set"


def test_saved_candidate_reranking_matches_brute_force():
    rows=[{"design_key":"a","worst_served_fraction":.96,"npc":12},
          {"design_key":"b","worst_served_fraction":.94,"npc":1},
          {"design_key":"c","worst_served_fraction":.97,"npc":10}]
    selected=select_least_cost(rows,.95,lambda row:row["npc"])
    brute=min((row for row in rows if row["worst_served_fraction"]>=.95),key=lambda row:row["npc"])
    assert selected==brute==rows[2]


def test_nominal_shear_uses_actual_wind_model_path():
    weather=load_phase9_weather()
    metadata,traces=benchmark_wind(weather,shear_exponent=ALPHA_NOMINAL)
    for key,turbine in WIND_TURBINES.items():
        hub=turbine.supported_hub_heights_m[0]
        expected=[commercial_turbine_output_kw(value,turbine,hub,ALPHA_NOMINAL)
                  for value in weather.series.wind_speed_100m_m_s]
        assert traces[key]==pytest.approx(expected)
        assert math.fsum(traces[key])==pytest.approx(metadata[key]["annual_generation_kwh"])


def test_fixed_system_load_monotonicity_and_conservation():
    generation=[2,0,2,0]
    low=dispatch([.9]*4,generation,None,0)
    nominal=dispatch([1.0]*4,generation,None,0)
    high=dispatch([1.1]*4,generation,None,0)
    assert low["served_fraction"] >= nominal["served_fraction"] >= high["served_fraction"]
    for result in (low,nominal,high):
        assert max(abs(result[key]) for key in ("generation_balance_error_kwh","load_balance_error_kwh",
          "storage_balance_error_kwh")) < 1e-6
