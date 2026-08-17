"""Cheap scale-aware economic reranking and reliability sensitivity of saved Phase 10 candidates."""

from __future__ import annotations
import csv, json, math, time
from pathlib import Path

from steppegrid.benchmarks.phase10 import precompute
from steppegrid.equipment.catalog import BATTERIES, INVERTERS, PV_MODULES, WIND_TURBINES
from steppegrid.optimization.core import RenewablePortfolio, dispatch, pareto_cost_reliability, scale_trace
from steppegrid.optimization.economics import (BATTERY, FINANCIAL, PV, UTILITY_PV, WIND,
    PV_UTILITY_SCALE_THRESHOLD_KW_AC, system_cost)
from steppegrid.optimization.reliability import ReliabilityConstraints, meets_reliability

ILLUSTRATIVE_MAX_CONTINUOUS_DEFICIT_HOURS = 24

def _typed(row):
    result=dict(row)
    for key in ("wind_count","pv_count","battery_count","loss_of_load_hours","longest_deficit_hours"):
        result[key]=int(row[key])
    for key in ("target","worst_served_fraction","renewable_generation_kwh","served_energy_kwh",
                "unmet_energy_kwh","curtailment_kwh","battery_throughput_kwh"):
        result[key]=float(row[key])
    result["lpsp"]=1-result["worst_served_fraction"]
    return result

def _capacities(row):
    wind_kw=row["wind_count"]*(WIND_TURBINES[row["wind_key"]].rated_power_kw if row["wind_key"] else 0)
    if row["pv_key"]:
        module_key,inverter_key=row["pv_key"].rsplit("__",1)
        module=PV_MODULES[module_key];inverter=INVERTERS[inverter_key]
        block_dc=math.floor(inverter.rated_ac_power_kw/module.rated_power_kw)*module.rated_power_kw
        pv_dc=row["pv_count"]*block_dc;pv_ac=row["pv_count"]*inverter.rated_ac_power_kw
    else:pv_dc=pv_ac=0.0
    battery_kwh=row["battery_count"]*(BATTERIES[row["battery_key"]].usable_energy_capacity_kwh if row["battery_key"] else 0)
    return wind_kw,pv_dc,pv_ac,battery_kwh

def rerank_row(row):
    original_physics={key:row[key] for key in ("worst_served_fraction","renewable_generation_kwh",
      "served_energy_kwh","unmet_energy_kwh","loss_of_load_hours","longest_deficit_hours",
      "curtailment_kwh","battery_throughput_kwh")}
    wind_kw,pv_dc,pv_ac,battery_kwh=_capacities(row)
    costs=system_cost(wind_kw=wind_kw,pv_dc_kw=pv_dc,pv_ac_kw=pv_ac,battery_usable_kwh=battery_kwh)
    result={**row,**costs,"installed_wind_kw":wind_kw,"installed_pv_dc_kw":pv_dc,
      "installed_pv_ac_kw":pv_ac,"installed_usable_battery_kwh":battery_kwh}
    result["cost_per_served_kwh_usd"]=result["equivalent_annual_cost_usd"]/result["served_energy_kwh"]
    assert original_physics=={key:result[key] for key in original_physics}
    return result

def _constraint_for(row,continuous_limit=None):
    return ReliabilityConstraints(minimum_served_fraction=row["target"],
        max_continuous_deficit_hours=continuous_limit)

def _row_metrics(row):
    return {"served_fraction":row["worst_served_fraction"],"loss_of_load_hours":row["loss_of_load_hours"],
            "longest_deficit_hours":row["longest_deficit_hours"]}

def _choose(rows,continuous_limit=None,robust_performance=None):
    selected={}
    for mode in sorted({row["mode"] for row in rows}):
      selected[mode]={}
      for target in sorted({row["target"] for row in rows}):
       feasible=[]
       for row in rows:
        if row["mode"]!=mode:continue
        if mode=="robust_all_profiles" and continuous_limit is not None:
            performance=robust_performance[row["design_key"]]
            ok=all(meets_reliability(metrics,ReliabilityConstraints(minimum_served_fraction=target,
                max_continuous_deficit_hours=continuous_limit)) for metrics in performance.values())
        else:ok=meets_reliability(_row_metrics(row),ReliabilityConstraints(
            minimum_served_fraction=target,max_continuous_deficit_hours=continuous_limit))
        if ok:feasible.append(row)
       if feasible:
        winner=min(feasible,key=lambda r:(r["net_present_cost_usd"],r["design_key"]))
        winner={**winner,"classification_target":target}
       else:winner=None
       selected[mode][str(target)]=winner
    return selected

def _physical_replay(rows,selected_sets,*,include_all_robust=True,existing=None):
    _,_,loads,_,wind,pv,_=precompute();simulation_count=0;cache={};robust={}
    needed=({row["design_key"]:row for row in rows if row["mode"]=="robust_all_profiles"}
            if include_all_robust else {})
    for selections in selected_sets:
      for targets in selections.values():
       for row in targets.values():
        if row:needed[row["design_key"]]=row
    for key,row in needed.items():
      if existing and key in existing:
       robust[key]=existing[key];continue
      portfolio=RenewablePortfolio(row["wind_key"] or None,row["wind_count"],row["pv_key"] or None,row["pv_count"])
      generation=scale_trace(portfolio,wind,pv);performance={}
      for shape,load in loads.items():
       cache_key=(key,shape)
       if cache_key not in cache:
        battery=BATTERIES[row["battery_key"]] if row["battery_key"] else None
        cache[cache_key]=dispatch(load,generation,battery,row["battery_count"]);simulation_count+=1
       performance[shape]=cache[cache_key]
      robust[key]=performance
    return robust,simulation_count

def _attach_performance(selected,performance):
    for targets in selected.values():
      for row in targets.values():
       if row and row["design_key"] in performance:
        row["all_profile_performance"]=performance[row["design_key"]]

def run_refinement(input_directory="outputs/benchmarks/rodina/phase10",write_outputs=True):
    started=time.perf_counter();root=Path(input_directory)
    with (root/"physical_feasible_candidates.csv").open(encoding="utf-8") as handle:
        original=[_typed(row) for row in csv.DictReader(handle)]
    rows=[rerank_row(row) for row in original]
    energy_only=_choose(rows)
    robust_performance,replays=_physical_replay(rows,())
    resilience=_choose(rows,ILLUSTRATIVE_MAX_CONTINUOUS_DEFICIT_HOURS,robust_performance)
    # Attach all-profile metrics for every final selected design; replay cache already includes robust rows.
    selected_performance,extra_replays=_physical_replay(rows,(energy_only,resilience),
        include_all_robust=False,existing=robust_performance)
    selected_performance={**robust_performance,**selected_performance}
    _attach_performance(energy_only,selected_performance);_attach_performance(resilience,selected_performance)
    robust_rows=[row for row in rows if row["mode"]=="robust_all_profiles"]
    frontier=pareto_cost_reliability(robust_rows)
    result={"energy_only_optima":energy_only,"resilience_constraint":{
      "max_continuous_deficit_hours":ILLUSTRATIVE_MAX_CONTINUOUS_DEFICIT_HOURS,
      "status":"illustrative research planning constraint; not a regulatory standard"},
      "resilience_constrained_optima":resilience,"pareto_front":frontier,
      "statistics":{"physical_candidates_reused":len(rows),"new_candidate_searches":0,
       "physical_replay_simulations":replays+extra_replays,
       "physical_candidate_set_unchanged":True,"runtime_seconds":time.perf_counter()-started},
      "economic_assumptions":{"financial":FINANCIAL.model_dump(mode="json"),
       "wind":WIND.model_dump(mode="json"),"commercial_pv":PV.model_dump(mode="json"),
       "utility_scale_pv":UTILITY_PV.model_dump(mode="json"),"battery":BATTERY.model_dump(mode="json"),
       "pv_scale_threshold_kw_ac":PV_UTILITY_SCALE_THRESHOLD_KW_AC}}
    if write_outputs:write_refinement_outputs(result,rows,root)
    return result

def write_refinement_outputs(result,rows,root):
    for name,value in (("scale_aware_economic_assumptions.json",result["economic_assumptions"]),
      ("scale_aware_energy_optima.json",result["energy_only_optima"]),
      ("resilience_sensitivity.json",{"constraint":result["resilience_constraint"],
        "optima":result["resilience_constrained_optima"],"statistics":result["statistics"]})):
      (root/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    fields=["mode","target","design_key","wind_key","wind_count","pv_key","pv_count","battery_key","battery_count",
      "worst_served_fraction","loss_of_load_hours","longest_deficit_hours","renewable_generation_kwh","served_energy_kwh",
      "unmet_energy_kwh","curtailment_kwh","economic_classes","reference_capex_basis","initial_capex_usd",
      "net_present_cost_usd","equivalent_annual_cost_usd","cost_per_served_kwh_usd"]
    for name,data in (("scale_aware_candidates.csv",rows),("scale_aware_pareto_front.csv",result["pareto_front"])):
      with (root/name).open("w",newline="",encoding="utf-8") as handle:
       writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
       for row in data:
        writer.writerow({key:(json.dumps(row[key],sort_keys=True) if isinstance(row.get(key),dict) else row.get(key)) for key in fields})
