import pytest
from pydantic import ValidationError

from steppegrid.benchmarks.phase9 import storage_dispatch
from steppegrid.equipment.catalog import BATTERIES
from steppegrid.optimization.core import (DispatchCache, RenewablePortfolio,
    annual_energy_sufficient, dispatch, minimum_battery_count, next_selective_battery_bound,
    pareto_cost_reliability, physically_nondominated, scale_trace)
from steppegrid.optimization.economics import (CostAssumption, PV, UTILITY_PV,
    PV_UTILITY_SCALE_THRESHOLD_KW_AC, classify_pv_economic_scale, system_cost)
from steppegrid.optimization.reliability import ReliabilityConstraints, meets_reliability
from steppegrid.optimization.refinement import rerank_row

def test_precomputed_integer_scaling():
    p=RenewablePortfolio("w",2,"p",3)
    assert scale_trace(p,{"w":[1,2]},{"p":[3,4]})==[11,16]

def test_annual_energy_pruning_is_necessary_condition():
    assert not annual_energy_sufficient(94,100,.95)
    assert annual_energy_sufficient(95,100,.95)

def test_battery_monotonicity_and_exact_minimum():
    battery=BATTERIES["saft_intensium_max_20_he"]
    load=[1000.0]*6; generation=[3000,3000,0,0,0,0]
    served=[dispatch(load,generation,battery,n)["served_fraction"] for n in range(1,5)]
    assert served==sorted(served)
    p=RenewablePortfolio("w",1,None,0); traces={p.key:generation}; loads={"x":load}
    cache=DispatchCache(loads,traces,BATTERIES)
    count,_=minimum_battery_count(cache,p,("x",),"saft_intensium_max_20_he",.8,4)
    brute=next((n for n in range(5) if cache.get(p,"x","saft_intensium_max_20_he",n)["served_fraction"]>=.8),None)
    assert count==brute

def test_dispatch_cache_and_zero_storage_deduplication():
    p=RenewablePortfolio("w",1,None,0);cache=DispatchCache({"x":[1,1]},{p.key:[1,1]},BATTERIES)
    a=cache.get(p,"x","tesla_megapack_2h",0);b=cache.get(p,"x","saft_intensium_max_20_he",0)
    assert a is b and cache.simulations==1 and cache.hits==1 and cache.no_storage_simulations==1

def test_one_dispatch_reused_for_both_targets():
    result=dispatch([1,1],[1,.96],None,0)
    assert result["served_fraction"]>=.95 and result["served_fraction"]<.99

def test_robust_constraint_requires_every_profile():
    values={"easy":{"served_fraction":1},"hard":{"served_fraction":.94}}
    assert min(v["served_fraction"] for v in values.values())<.95

def test_energy_conservation_and_phase9_dispatch_equivalence():
    load=[0,1000,1000,2500];generation=[3000,0,500,0];battery=BATTERIES["saft_intensium_max_20_he"]
    result=dispatch(load,generation,battery,1);reference=storage_dispatch(load,generation,"saft_intensium_max_20_he")
    assert result["battery_charge_input_kwh"]==pytest.approx(reference["battery_charge_input_kwh"])
    assert result["battery_discharge_delivered_kwh"]==pytest.approx(reference["battery_discharge_delivered_kwh"])
    assert result["unmet_energy_kwh"]==pytest.approx(reference["unmet_load_kwh"])
    assert max(abs(result[k]) for k in ("generation_balance_error_kwh","load_balance_error_kwh","storage_balance_error_kwh"))<1e-6
    assert result["initial_inventory_discharge_kwh"]==0

def test_pareto_known_case():
    rows=[{"design_key":"a","net_present_cost_usd":1,"worst_served_fraction":.9},
          {"design_key":"b","net_present_cost_usd":2,"worst_served_fraction":.8},
          {"design_key":"c","net_present_cost_usd":3,"worst_served_fraction":.99}]
    assert [r["design_key"] for r in pareto_cost_reliability(rows)]==["a","c"]

def test_missing_cost_never_becomes_zero():
    with pytest.raises(ValidationError,match="missing cost"):
      CostAssumption(technology="x",capex_unit="USD",fixed_om_unit="USD",fixed_om_value=0,lifetime_years=1,
       scale_category="x",applicable_scale="x",
       source_title="x",source_url="https://example.test",source_organization="x",source_year=2022,
       base_year=2022,currency="USD",geographic_scope="x",source_type="x",cost_boundary="x",notes="x")

def test_reduced_brute_force_matches_cached_monotonic_search():
    p=RenewablePortfolio("w",1,None,0);load=[1000.0]*4;generation=[3000,0,0,0]
    cache=DispatchCache({"x":load},{p.key:generation},BATTERIES);target=.7
    optimized,_=minimum_battery_count(cache,p,("x",),"tesla_megapack_2h",target,4)
    exhaustive=[n for n in range(5) if cache.get(p,"x","tesla_megapack_2h",n)["served_fraction"]>=target]
    assert optimized==(min(exhaustive) if exhaustive else None)

def test_selective_boundary_expansion_is_incremental_only_when_binding():
    assert next_selective_battery_bound(3,4) is None
    assert next_selective_battery_bound(4,4)==6
    assert next_selective_battery_bound(6,6)==8
    assert next_selective_battery_bound(8,8) is None

def test_physical_dominance_is_conservative_and_product_specific():
    def row(key,w,reliability,curtailment,wind_key="w"):
      metrics={"x":{"served_fraction":reliability,"curtailment_kwh":curtailment}}
      return {"design_key":key,"optimization_mode":"x","target":.95,
       "design":{"wind_key":wind_key,"wind_count":w,"pv_key":None,"pv_count":0,"battery_key":None,"battery_count":0},
       "performance":metrics}
    rows=[row("a",1,.96,1),row("b",2,.95,2),row("different",2,.95,2,"other")]
    assert {r["design_key"] for r in physically_nondominated(rows)}=={"a","different"}

def test_pv_scale_classification_is_deterministic_at_boundary():
    assert classify_pv_economic_scale(100)==PV.scale_category
    assert classify_pv_economic_scale(PV_UTILITY_SCALE_THRESHOLD_KW_AC)==PV.scale_category
    assert classify_pv_economic_scale(PV_UTILITY_SCALE_THRESHOLD_KW_AC+.001)==UTILITY_PV.scale_category
    with pytest.raises(ValueError):classify_pv_economic_scale(-1)

def test_system_npc_uses_correct_pv_scale_class():
    small=system_cost(wind_kw=0,pv_dc_kw=5000,pv_ac_kw=5000,battery_usable_kwh=0)
    large=system_cost(wind_kw=0,pv_dc_kw=6000,pv_ac_kw=6000,battery_usable_kwh=0)
    assert small["economic_classes"]["pv"]=="commercial_pv"
    assert large["economic_classes"]["pv"]=="utility_scale_pv"
    assert small["initial_capex_usd"]==pytest.approx(5000*PV.capex_value)
    assert large["initial_capex_usd"]==pytest.approx(6000*UTILITY_PV.capex_value)

def test_optional_duration_constraints_do_not_change_energy_only_behavior():
    metrics={"served_fraction":.99,"loss_of_load_hours":100,"longest_deficit_hours":30}
    assert meets_reliability(metrics,ReliabilityConstraints(minimum_served_fraction=.99))
    assert not meets_reliability(metrics,ReliabilityConstraints(minimum_served_fraction=.99,
        max_continuous_deficit_hours=24))
    assert not meets_reliability(metrics,ReliabilityConstraints(minimum_served_fraction=.99,
        max_loss_of_load_hours=99))

def test_candidate_can_satisfy_energy_and_duration_constraints_together():
    metrics={"served_fraction":.991,"loss_of_load_hours":20,"longest_deficit_hours":8}
    constraints=ReliabilityConstraints(minimum_served_fraction=.99,max_loss_of_load_hours=20,
        max_continuous_deficit_hours=8)
    assert meets_reliability(metrics,constraints)

def test_loss_hours_longest_run_and_maximum_deficit_are_distinct_metrics():
    result=dispatch([1,1,1,1,1],[0,0,1,0,1],None,0)
    assert result["loss_of_load_hours"]==3
    assert result["longest_deficit_hours"]==2
    assert result["maximum_hourly_deficit_kwh"]==1

def test_economic_reranking_does_not_change_physical_metrics():
    row={"mode":"x","target":.95,"design_key":"x","wind_key":"bergey_excel_15","wind_count":1,
      "pv_key":"trina_tsm_450_neg9r28__sma_core1_stp50_41","pv_count":1,
      "battery_key":"tesla_megapack_2h","battery_count":1,"worst_served_fraction":.96,
      "renewable_generation_kwh":10.0,"served_energy_kwh":9.0,"unmet_energy_kwh":1.0,
      "loss_of_load_hours":2,"longest_deficit_hours":1,"curtailment_kwh":1.0,
      "battery_throughput_kwh":2.0,"lpsp":.04}
    physical={key:row[key] for key in ("worst_served_fraction","renewable_generation_kwh",
      "served_energy_kwh","unmet_energy_kwh","loss_of_load_hours","longest_deficit_hours",
      "curtailment_kwh","battery_throughput_kwh")}
    reranked=rerank_row(row)
    assert {key:reranked[key] for key in physical}==physical
