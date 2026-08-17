"""Efficient staged discrete sizing for the frozen Rodina Phase 9 traces."""

from __future__ import annotations
import csv, json, math, time
from pathlib import Path

from steppegrid.benchmarks.phase9 import load_phase9_loads, load_phase9_weather, run_phase9
from steppegrid.equipment.catalog import BATTERIES
from steppegrid.optimization.core import (DispatchCache, RenewablePortfolio,
    annual_energy_sufficient, minimum_battery_count, pareto_cost_reliability,
    physically_nondominated, scale_trace)
from steppegrid.optimization.economics import (BATTERY, FINANCIAL, PV, UTILITY_PV, WIND,
    system_cost)

OUTPUT_DIRECTORY = Path("outputs/benchmarks/rodina/phase10")
TARGETS = (0.95, 0.99)
WIND_ENERGY_SHARES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
ANNUAL_ENERGY_BOUND_MULTIPLIER = 3.0
INITIAL_BATTERY_MAX = 4

def precompute():
    started=time.perf_counter(); weather=load_phase9_weather()
    phase9=run_phase9(weather=weather,write_outputs=False); loads,load_meta=load_phase9_loads()
    wind={k:v for k,v in phase9.wind_profiles_kwh.items()}; pv={k:v for k,v in phase9.pv_profiles_kwh.items()}
    return weather,phase9,loads,load_meta,wind,pv,time.perf_counter()-started

def bounds(load_kwh,wind,pv):
    target=ANNUAL_ENERGY_BOUND_MULTIPLIER*load_kwh
    return ({k:math.ceil(target/math.fsum(v)) for k,v in wind.items()},
            {k:math.ceil(target/math.fsum(v)) for k,v in pv.items()})

def theoretical_energy_pruned(load_kwh,wind,pv,wbounds,pbounds):
    threshold=.95*load_kwh; removed=0
    for wkey,wtrace in wind.items():
      wy=math.fsum(wtrace)
      for pkey,ptrace in pv.items():
       py=math.fsum(ptrace)
       for wc in range(wbounds[wkey]+1):
        minimum=max(0,math.ceil((threshold-wc*wy)/py-1e-12))
        removed+=min(minimum,pbounds[pkey]+1)*9
    return removed

def _portfolio(wkey,pkey,wcount,pcount):
    return RenewablePortfolio(wkey if wcount else None,wcount,pkey if pcount else None,pcount)

def _scaled(base,s,wmax,pmax):
    wc=min(wmax,math.ceil(base.wind_count*s)) if base.wind_count else 0
    pc=min(pmax,math.ceil(base.pv_count*s)) if base.pv_count else 0
    return _portfolio(base.wind_key,base.pv_key,wc,pc)

def _ensure_trace(portfolio,trace_cache,wind,pv):
    if portfolio.key not in trace_cache: trace_cache[portfolio.key]=scale_trace(portfolio,wind,pv)

def _minimum_scale(base,wmax,pmax,shapes,target,battery_key,battery_max,dispatch_cache,
                   trace_cache,wind,pv,stats):
    annual_load=next(iter(dispatch_cache.loads.values()))
    load_total=math.fsum(annual_load)
    def feasible(scale):
        portfolio=_scaled(base,scale,wmax,pmax); _ensure_trace(portfolio,trace_cache,wind,pv)
        generation=math.fsum(trace_cache[portfolio.key])
        if not annual_energy_sufficient(generation,load_total,target):
            stats["annual_energy_pruned"]+=1; return False,portfolio
        if battery_key is None:
            rows={shape:dispatch_cache.get(portfolio,shape,None,0) for shape in shapes}
            return min(v["served_fraction"] for v in rows.values())+1e-12>=target,portfolio
        count, _=minimum_battery_count(dispatch_cache,portfolio,shapes,battery_key,target,battery_max)
        return count is not None,portfolio
    low=0.0; high=1.0; ok,portfolio=feasible(high)
    max_scale=max(wmax/base.wind_count if base.wind_count else math.inf,
                  pmax/base.pv_count if base.pv_count else math.inf)
    if base.wind_count==0: max_scale=pmax/base.pv_count
    if base.pv_count==0: max_scale=wmax/base.wind_count
    while not ok and high<max_scale:
        low=high; high=min(max_scale,high*1.5); ok,portfolio=feasible(high)
    if not ok:return None
    for _ in range(14):
        middle=(low+high)/2; candidate=_scaled(base,middle,wmax,pmax)
        if candidate.key==portfolio.key: high=middle; continue
        middle_ok,middle_portfolio=feasible(middle)
        if middle_ok: high=middle; portfolio=middle_portfolio
        else: low=middle
    return portfolio

def _cost(row,phase9):
    d=row["design"]; wind_kw=d["wind_count"]*(phase9.wind[d["wind_key"]]["rated_power_kw"] if d["wind_key"] else 0)
    pv_dc=d["pv_count"]*(phase9.pv[d["pv_key"]]["dc_capacity_kw"] if d["pv_key"] else 0)
    pv_ac=d["pv_count"]*(phase9.pv[d["pv_key"]]["ac_capacity_kw"] if d["pv_key"] else 0)
    battery_kwh=d["battery_count"]*(BATTERIES[d["battery_key"]].usable_energy_capacity_kwh if d["battery_key"] else 0)
    costs=system_cost(wind_kw=wind_kw,pv_dc_kw=pv_dc,pv_ac_kw=pv_ac,battery_usable_kwh=battery_kwh)
    row.update(installed_wind_kw=wind_kw,installed_pv_dc_kw=pv_dc,
        installed_pv_ac_kw=pv_ac,installed_usable_battery_kwh=battery_kwh,**costs)
    row["cost_per_served_kwh_usd"]=row["equivalent_annual_cost_usd"]/row["worst_served_energy_kwh"]
    return row

def run_phase10(*,write_outputs=True,output_directory=OUTPUT_DIRECTORY):
    total_start=time.perf_counter(); weather,phase9,loads,load_meta,wind,pv,trace_seconds=precompute()
    wbounds,pbounds=bounds(load_meta["annual_kwh"],wind,pv); trace_cache={}; stats={"annual_energy_pruned":0}
    cache=DispatchCache(loads,trace_cache,BATTERIES); candidate_start=time.perf_counter(); raw={};economic_seconds=0.0
    modes={shape:(shape,) for shape in loads}; modes["robust_all_profiles"]=tuple(loads)
    for mode,shapes in modes.items():
      for target in TARGETS:
       for wkey in wind:
        for pkey in pv:
         for share in WIND_ENERGY_SHARES:
          wc=math.ceil(target*load_meta["annual_kwh"]*share/math.fsum(wind[wkey])) if share else 0
          pc=math.ceil(target*load_meta["annual_kwh"]*(1-share)/math.fsum(pv[pkey])) if share<1 else 0
          if wc>wbounds[wkey] or pc>pbounds[pkey]:continue
          base=_portfolio(wkey,pkey,wc,pc)
          for battery_key,bmax in ((None,0),*((key,INITIAL_BATTERY_MAX) for key in BATTERIES)):
           portfolio=_minimum_scale(base,wbounds[wkey],pbounds[pkey],shapes,target,battery_key,bmax,
              cache,trace_cache,wind,pv,stats)
           if portfolio is None:continue
           _ensure_trace(portfolio,trace_cache,wind,pv)
           if battery_key is None:count=0
           else:
            count,_=minimum_battery_count(cache,portfolio,shapes,battery_key,target,bmax)
            if count is None:continue
           performance={shape:cache.get(portfolio,shape,battery_key,count) for shape in loads}
           binding=min(shapes,key=lambda x:performance[x]["served_fraction"])
           design={"wind_key":portfolio.wind_key,"wind_count":portfolio.wind_count,
                   "pv_key":portfolio.pv_key,"pv_count":portfolio.pv_count,
                   "battery_key":battery_key if count else None,"battery_count":count}
           key=f"{portfolio.key}|b={design['battery_key'] or 'none'}:{count}"
           row={"design_key":key,"design":design,"optimization_mode":mode,"target":target,
                "binding_load_shape":binding,"worst_served_fraction":performance[binding]["served_fraction"],
                "average_served_fraction":sum(performance[s]["served_fraction"] for s in shapes)/len(shapes),
                "worst_served_energy_kwh":performance[binding]["served_energy_kwh"],"performance":performance}
           economic_start=time.perf_counter();raw[(mode,target,key)]=_cost(row,phase9)
           economic_seconds+=time.perf_counter()-economic_start
    def choose_optima():
      selected={}; current=list(raw.values())
      for mode in modes:
       selected[mode]={}
       for target in TARGETS:
        feasible=[r for r in current if r["optimization_mode"]==mode and r["target"]==target and r["worst_served_fraction"]+1e-12>=target]
        selected[mode][str(target)]=min(feasible,key=lambda r:(r["net_present_cost_usd"],r["design_key"])) if feasible else None
      return selected
    def selective_region(mode,target,seed,battery_max,pv_multiplier):
      nonlocal economic_seconds
      shapes=modes[mode];wkey=seed["design"]["wind_key"];pkey=seed["design"]["pv_key"]
      selective_pmax=math.ceil(pv_multiplier*load_meta["annual_kwh"]/math.fsum(pv[pkey]))
      for share in WIND_ENERGY_SHARES:
       wc=math.ceil(target*load_meta["annual_kwh"]*share/math.fsum(wind[wkey])) if share else 0
       pc=math.ceil(target*load_meta["annual_kwh"]*(1-share)/math.fsum(pv[pkey])) if share<1 else 0
       if wc>wbounds[wkey] or pc>selective_pmax:continue
       base=_portfolio(wkey,pkey,wc,pc)
       for battery_key in BATTERIES:
        portfolio=_minimum_scale(base,wbounds[wkey],selective_pmax,shapes,target,battery_key,battery_max,
          cache,trace_cache,wind,pv,stats)
        if portfolio is None:continue
        count,_=minimum_battery_count(cache,portfolio,shapes,battery_key,target,battery_max)
        if count is None:continue
        performance={shape:cache.get(portfolio,shape,battery_key,count) for shape in loads}
        binding=min(shapes,key=lambda x:performance[x]["served_fraction"])
        design={"wind_key":portfolio.wind_key,"wind_count":portfolio.wind_count,"pv_key":portfolio.pv_key,
          "pv_count":portfolio.pv_count,"battery_key":battery_key if count else None,"battery_count":count}
        key=f"{portfolio.key}|b={design['battery_key'] or 'none'}:{count}"
        row={"design_key":key,"design":design,"optimization_mode":mode,"target":target,
          "binding_load_shape":binding,"worst_served_fraction":performance[binding]["served_fraction"],
          "average_served_fraction":sum(performance[s]["served_fraction"] for s in shapes)/len(shapes),
          "worst_served_energy_kwh":performance[binding]["served_energy_kwh"],"performance":performance}
        economic_start=time.perf_counter();raw[(mode,target,key)]=_cost(row,phase9)
        economic_seconds+=time.perf_counter()-economic_start
    preliminary=choose_optima(); expanded=[]
    for mode,targets in preliminary.items():
     for target_text,seed in targets.items():
      if seed and (seed["design"]["battery_count"]==INITIAL_BATTERY_MAX or
                   seed["design"]["pv_count"]==pbounds[seed["design"]["pv_key"]]):
       selective_region(mode,float(target_text),seed,6,4.0);expanded.append({"mode":mode,"target":float(target_text),"battery_max":6,"pv_energy_bound_multiplier":4.0})
    after_six=choose_optima()
    for mode,targets in after_six.items():
     for target_text,seed in targets.items():
      if seed and seed["design"]["battery_count"]==6:
       selective_region(mode,float(target_text),seed,8,4.0);expanded.append({"mode":mode,"target":float(target_text),"battery_max":8,"pv_energy_bound_multiplier":4.0})
    candidate_seconds=time.perf_counter()-candidate_start; rows=list(raw.values());optima=choose_optima()
    robust_start=time.perf_counter()
    physical_front=physically_nondominated(rows)
    frontier=pareto_cost_reliability([r for r in rows if r["optimization_mode"]=="robust_all_profiles"])
    robust_seconds=time.perf_counter()-robust_start
    theoretical=sum((wbounds[w]+1)*(pbounds[p]+1)*9 for w in wind for p in pv)
    theoretical_pruned=theoretical_energy_pruned(load_meta["annual_kwh"],wind,pv,wbounds,pbounds)
    result={"configuration":{"targets":list(TARGETS),"fixed_shear":phase9.wind_shear["exponent"],
      "fixed_hub_heights_m":{k:phase9.wind[k]["hub_height_m"] for k in wind},"fixed_tilt_deg":51.302445,
      "fixed_azimuth_deg":180,"annual_energy_bound_multiplier":ANNUAL_ENERGY_BOUND_MULTIPLIER,
      "wind_count_bounds":wbounds,"pv_count_bounds":pbounds,"initial_battery_count_bounds":[0,4],
      "wind_energy_share_rays":list(WIND_ENERGY_SHARES),"search_method":"adaptive monotonic ray bracketing and bisection"},
      "statistics":{"theoretical_candidate_combinations":theoretical,
       "candidate_combinations_removed_by_annual_energy_rule":theoretical_pruned,
       "annual_energy_pruned_during_adaptive_search":stats["annual_energy_pruned"],
       "unique_renewable_portfolios":len(trace_cache),"no_storage_simulations":cache.no_storage_simulations,
       "battery_simulations":cache.simulations-cache.no_storage_simulations,"dispatch_cache_hits":cache.hits,
       "battery_evaluations_avoided_by_cache":cache.hits,
       "battery_evaluations_avoided_by_ordered_search":cache.ordered_evaluations_avoided,
       "boundary_expansions":expanded,"physical_feasible_candidates":len(rows),"physical_nondominated_candidates":len(physical_front),
       "cost_reliability_pareto_points":len(frontier),
       "trace_precomputation_seconds":trace_seconds,"physical_search_seconds":candidate_seconds,
       "candidate_generation_and_orchestration_seconds":max(0.0,candidate_seconds-cache.no_storage_seconds-cache.battery_seconds-economic_seconds),
       "no_storage_screening_seconds":cache.no_storage_seconds,"battery_dispatch_seconds":cache.battery_seconds,
       "robust_and_pareto_evaluation_seconds":robust_seconds,"economic_evaluation_seconds":economic_seconds,
       "total_seconds":time.perf_counter()-total_start},"optima":optima,"pareto_front":frontier,
      "economic_assumptions":{"financial":FINANCIAL.model_dump(mode="json"),"wind":WIND.model_dump(mode="json"),
      "pv_commercial":PV.model_dump(mode="json"),"pv_utility_scale":UTILITY_PV.model_dump(mode="json"),
      "battery":BATTERY.model_dump(mode="json")},
      "phase9_integrity":{"hours":phase9.weather_integrity["records"],"timezone":phase9.load_integrity["timezone"],
       "annual_load_kwh":phase9.load_integrity["annual_kwh"]}}
    if write_outputs:write_outputs_phase10(result,rows,physical_front,output_directory)
    return result

def write_outputs_phase10(result,rows,physical_front,directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    for name,value in (("optimization_config.json",result["configuration"]),("physical_search_statistics.json",result["statistics"]),
      ("economic_assumptions.json",result["economic_assumptions"]),("profile_specific_optima.json",{k:v for k,v in result["optima"].items() if k!="robust_all_profiles"}),
      ("robust_optima.json",result["optima"]["robust_all_profiles"])):
      (out/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    def scalar(row):
      d=row["design"];m=row["performance"][row["binding_load_shape"]];return {"mode":row["optimization_mode"],"target":row["target"],"design_key":row["design_key"],**d,
       "worst_served_fraction":row["worst_served_fraction"],"binding_load_shape":row["binding_load_shape"],
       "renewable_generation_kwh":m["renewable_generation_kwh"],"served_energy_kwh":m["served_energy_kwh"],
       "unmet_energy_kwh":m["unmet_energy_kwh"],"loss_of_load_hours":m["loss_of_load_hours"],
       "longest_deficit_hours":m["longest_deficit_hours"],"curtailment_kwh":m["curtailment_kwh"],
       "battery_throughput_kwh":m["battery_throughput_kwh"],"initial_capex_usd":row["initial_capex_usd"],
       "net_present_cost_usd":row["net_present_cost_usd"]}
    for name,data in (("physical_feasible_candidates.csv",rows),("physical_nondominated_candidates.csv",physical_front),
                      ("pareto_front.csv",result["pareto_front"])):
      values=[scalar(r) for r in data]
      with (out/name).open("w",newline="",encoding="utf-8") as f:
       writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    cross=[]
    for mode,targets in result["optima"].items():
     for target,row in targets.items():
      if row:
       for shape,metrics in row["performance"].items():cross.append({"mode":mode,"target":target,"design_key":row["design_key"],
        "evaluation_shape":shape,"served_fraction":metrics["served_fraction"],"unmet_energy_kwh":metrics["unmet_energy_kwh"],
        "loss_of_load_hours":metrics["loss_of_load_hours"]})
    with (out/"cross_profile_validation.csv").open("w",newline="",encoding="utf-8") as f:
     writer=csv.DictWriter(f,fieldnames=list(cross[0]));writer.writeheader();writer.writerows(cross)
