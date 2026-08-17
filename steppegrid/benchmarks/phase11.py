"""Deterministic Phase 11 sensitivity layer over the frozen Phase 10 benchmark."""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from steppegrid.benchmarks.phase9 import benchmark_wind
from steppegrid.benchmarks.phase10 import precompute
from steppegrid.equipment.catalog import BATTERIES
from steppegrid.optimization.core import RenewablePortfolio, dispatch, scale_trace
from steppegrid.optimization.economics import system_cost

ALPHA_NOMINAL = 0.2317610498
OUTPUT_DIRECTORY = Path("outputs/benchmarks/rodina/phase11")
PHASE10_DIRECTORY = Path("outputs/benchmarks/rodina/phase10")
ADAPTATION_METHOD = "saved_phase10_candidate_reselection"
SELECTION_SCOPE = "least-cost feasible design among the saved Phase 10 candidate set"

@dataclass(frozen=True)
class SensitivityScenario:
    name: str
    category: str = "one_factor"
    varied_assumption: str = "none"
    demand_multiplier: float = 1.0
    wind_shear_alpha: float = ALPHA_NOMINAL
    pv_generation_multiplier: float = 1.0
    wind_capex_multiplier: float = 1.0
    pv_capex_multiplier: float = 1.0
    battery_capex_multiplier: float = 1.0

def scenarios(include_combined: bool = True) -> tuple[SensitivityScenario, ...]:
    rows = [SensitivityScenario("nominal", "baseline"),
        SensitivityScenario("demand_low", varied_assumption="demand_multiplier", demand_multiplier=.9),
        SensitivityScenario("demand_high", varied_assumption="demand_multiplier", demand_multiplier=1.1),
        SensitivityScenario("wind_shear_low", varied_assumption="wind_shear_alpha", wind_shear_alpha=ALPHA_NOMINAL*.8),
        SensitivityScenario("wind_shear_high", varied_assumption="wind_shear_alpha", wind_shear_alpha=ALPHA_NOMINAL*1.2),
        SensitivityScenario("pv_low", varied_assumption="pv_generation_multiplier", pv_generation_multiplier=.9),
        SensitivityScenario("pv_high", varied_assumption="pv_generation_multiplier", pv_generation_multiplier=1.1),
        SensitivityScenario("wind_capex_low", varied_assumption="wind_capex_multiplier", wind_capex_multiplier=.8),
        SensitivityScenario("wind_capex_high", varied_assumption="wind_capex_multiplier", wind_capex_multiplier=1.2),
        SensitivityScenario("pv_capex_low", varied_assumption="pv_capex_multiplier", pv_capex_multiplier=.8),
        SensitivityScenario("pv_capex_high", varied_assumption="pv_capex_multiplier", pv_capex_multiplier=1.2),
        SensitivityScenario("battery_capex_low", varied_assumption="battery_capex_multiplier", battery_capex_multiplier=.8),
        SensitivityScenario("battery_capex_high", varied_assumption="battery_capex_multiplier", battery_capex_multiplier=1.2)]
    if include_combined:
        rows += [SensitivityScenario("resource_stress", "combined", "physical_combination", 1.1, ALPHA_NOMINAL*1.2, .9),
                 SensitivityScenario("resource_favorable", "combined", "physical_combination", .9, ALPHA_NOMINAL*.8, 1.1)]
    return tuple(rows)

def scale_nonnegative(trace, multiplier):
    if multiplier < 0: raise ValueError("multiplier must be nonnegative")
    return [max(0.0, value * multiplier) for value in trace]

def _design(row):
    return {key: row[key] for key in ("wind_key","wind_count","pv_key","pv_count","battery_key","battery_count")}

def _evaluate(design, target, scenario, loads, wind, pv, phase9):
    portfolio=RenewablePortfolio(design["wind_key"] if design["wind_count"] else None,int(design["wind_count"]),
        design["pv_key"] if design["pv_count"] else None,int(design["pv_count"]))
    generation=scale_trace(portfolio,wind,pv)
    costs=_cost(design,scenario,phase9)
    installed_wind=int(design["wind_count"])*(phase9.wind[design["wind_key"]]["rated_power_kw"] if int(design["wind_count"]) else 0)
    installed_pv_dc=int(design["pv_count"])*(phase9.pv[design["pv_key"]]["dc_capacity_kw"] if int(design["pv_count"]) else 0)
    installed_pv_ac=int(design["pv_count"])*(phase9.pv[design["pv_key"]]["ac_capacity_kw"] if int(design["pv_count"]) else 0)
    installed_battery=int(design["battery_count"])*(BATTERIES[design["battery_key"]].usable_energy_capacity_kwh if int(design["battery_count"]) else 0)
    rows=[]
    wind_total=math.fsum(wind[design["wind_key"]])*int(design["wind_count"]) if int(design["wind_count"]) else 0
    pv_total=math.fsum(pv[design["pv_key"]])*int(design["pv_count"]) if int(design["pv_count"]) else 0
    for shape,nominal_load in loads.items():
        metrics=dispatch(scale_nonnegative(nominal_load,scenario.demand_multiplier),generation,
            BATTERIES[design["battery_key"]] if int(design["battery_count"]) else None,int(design["battery_count"]))
        residual=max(abs(metrics[k]) for k in ("generation_balance_error_kwh","load_balance_error_kwh","storage_balance_error_kwh"))
        rows.append({"scenario":scenario.name,"scenario_category":scenario.category,"varied_assumption":scenario.varied_assumption,
          "demand_multiplier":scenario.demand_multiplier,"wind_shear_alpha":scenario.wind_shear_alpha,
          "pv_generation_multiplier":scenario.pv_generation_multiplier,"wind_capex_multiplier":scenario.wind_capex_multiplier,
          "pv_capex_multiplier":scenario.pv_capex_multiplier,"battery_capex_multiplier":scenario.battery_capex_multiplier,
          "target":target,"design_key":f"w={portfolio.wind_key or 'none'}:{portfolio.wind_count}|pv={portfolio.pv_key or 'none'}:{portfolio.pv_count}|b={design['battery_key'] or 'none'}:{design['battery_count']}",
          **design,"installed_wind_kw":installed_wind,"installed_pv_dc_kw":installed_pv_dc,
          "installed_pv_ac_kw":installed_pv_ac,"installed_usable_battery_kwh":installed_battery,
          "load_profile":shape,"annual_load_kwh":metrics["annual_load_kwh"],"annual_raw_renewable_generation_kwh":metrics["renewable_generation_kwh"],
          "wind_generation_kwh":wind_total,"pv_generation_kwh":pv_total,"served_energy_kwh":metrics["served_energy_kwh"],
          "served_fraction":metrics["served_fraction"],"lpsp":metrics["lpsp"],"unmet_energy_kwh":metrics["unmet_energy_kwh"],
          "loss_of_load_hours":metrics["loss_of_load_hours"],"longest_deficit_hours":metrics["longest_deficit_hours"],
          "maximum_hourly_deficit_kwh":metrics["maximum_hourly_deficit_kwh"],"curtailed_energy_kwh":metrics["curtailment_kwh"],
          "battery_charge_kwh":metrics["battery_charge_input_kwh"],"battery_discharge_kwh":metrics["battery_discharge_delivered_kwh"],
          "ending_soc_kwh":metrics["ending_soc_kwh"],"energy_conservation_residual_kwh":residual,
          **costs,"cost_per_served_kwh_usd":costs["equivalent_annual_cost_usd"]/metrics["served_energy_kwh"],
          "meets_95_target":metrics["served_fraction"]+1e-12>=.95,"meets_99_target":metrics["served_fraction"]+1e-12>=.99,
          "served_fraction_margin":metrics["served_fraction"]-target,"design_basis":"fixed_nominal"})
    return rows

def _cost(d,s,phase9):
    return system_cost(wind_kw=int(d["wind_count"])*(phase9.wind[d["wind_key"]]["rated_power_kw"] if int(d["wind_count"]) else 0),
      pv_dc_kw=int(d["pv_count"])*(phase9.pv[d["pv_key"]]["dc_capacity_kw"] if int(d["pv_count"]) else 0),
      pv_ac_kw=int(d["pv_count"])*(phase9.pv[d["pv_key"]]["ac_capacity_kw"] if int(d["pv_count"]) else 0),
      battery_usable_kwh=int(d["battery_count"])*(BATTERIES[d["battery_key"]].usable_energy_capacity_kwh if int(d["battery_count"]) else 0),
      wind_capex_multiplier=s.wind_capex_multiplier,pv_capex_multiplier=s.pv_capex_multiplier,
      battery_capex_multiplier=s.battery_capex_multiplier)

def monotonic_threshold(feasible, low, high, *, lowest=True, iterations=30):
    """Find lowest feasible value, or highest feasible value when ``lowest`` is false."""
    if lowest:
        if not feasible(high): return None
        if feasible(low): return low
        for _ in range(iterations):
            mid=(low+high)/2
            if feasible(mid): high=mid
            else: low=mid
        return high
    if feasible(high): return high
    if not feasible(low): return None
    for _ in range(iterations):
        mid=(low+high)/2
        if feasible(mid): low=mid
        else: high=mid
    return low

def select_least_cost(candidates, target, cost_function):
    feasible=[row for row in candidates if float(row["worst_served_fraction"])+1e-12>=target]
    return min(feasible,key=lambda row:(cost_function(row),row["design_key"])) if feasible else None

def _write_csv(path, rows):
    if not rows: return
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def _read_csv(path):
    with Path(path).open(encoding="utf-8",newline="") as handle:
        return list(csv.DictReader(handle))

def _write_plots(out, fixed, ranking):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return 0
    definitions=(("demand",("demand_low","nominal","demand_high"),(.9,1,1.1),"Demand multiplier"),
      ("wind_shear",("wind_shear_low","nominal","wind_shear_high"),(ALPHA_NOMINAL*.8,ALPHA_NOMINAL,ALPHA_NOMINAL*1.2),"Wind-shear exponent"),
      ("pv_output",("pv_low","nominal","pv_high"),(.9,1,1.1),"PV-output multiplier"))
    for filename,names,xvalues,xlabel in definitions:
        fig,ax=plt.subplots(figsize=(7,4.5))
        for target in (.95,.99):
            y=[min(r["served_fraction"] for r in fixed if r["target"]==target and r["scenario"]==name) for name in names]
            ax.plot(xvalues,y,marker="o",label=f"{target:.0%} design")
            ax.axhline(target,linestyle="--",linewidth=.8,color="gray")
        ax.set(title=f"Fixed-design reliability vs {xlabel.lower()}",xlabel=xlabel,ylabel="Worst served-energy fraction")
        ax.legend();fig.tight_layout();fig.savefig(out/f"served_fraction_vs_{filename}.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),sharey=True)
    for ax,target in zip(axes,(.95,.99),strict=True):
        rows=sorted((r for r in ranking if r["target"]==target and r["output"]=="fixed_design_worst_served_fraction"),key=lambda r:r["normalized_sensitivity_score"])
        ax.barh([r["assumption"].replace("_"," ") for r in rows],[r["normalized_sensitivity_score"] for r in rows])
        ax.set(title=f"{target:.0%} fixed design",xlabel="Served-fraction range / input range")
    fig.suptitle("Deterministic sensitivity ranking (declared ranges only)");fig.tight_layout()
    fig.savefig(out/"tornado_sensitivity_ranking.png",dpi=160);plt.close(fig)
    return 4

def run_phase11(*, output_directory=OUTPUT_DIRECTORY, write_outputs=True):
    started=time.perf_counter(); weather,phase9,loads,_,nominal_wind,nominal_pv,pre_seconds=precompute()
    wind_by_alpha={ALPHA_NOMINAL:nominal_wind}
    for alpha in (ALPHA_NOMINAL*.8,ALPHA_NOMINAL*1.2):
        wind_by_alpha[alpha]=benchmark_wind(weather,shear_exponent=alpha)[1]
    def wind_for(alpha):
        if alpha not in wind_by_alpha: wind_by_alpha[alpha]=benchmark_wind(weather,shear_exponent=alpha)[1]
        return wind_by_alpha[alpha]
    all_final=json.loads((PHASE10_DIRECTORY/"scale_aware_energy_optima.json").read_text(encoding="utf-8"))
    final=all_final["robust_all_profiles"]
    selected={float(target):_design(row) for target,row in final.items()}
    fixed=[]; scenario_list=scenarios()
    fixed_start=time.perf_counter()
    for scenario in scenario_list:
        wind=wind_by_alpha[scenario.wind_shear_alpha]
        pv={key:scale_nonnegative(trace,scenario.pv_generation_multiplier) for key,trace in nominal_pv.items()}
        for target,design in selected.items(): fixed += _evaluate(design,target,scenario,loads,wind,pv,phase9)
    fixed_seconds=time.perf_counter()-fixed_start
    margins=[]
    for target,design in selected.items():
        def worst(dm=1.0,pvm=1.0,alpha=ALPHA_NOMINAL):
            s=SensitivityScenario("threshold",demand_multiplier=dm,pv_generation_multiplier=pvm,wind_shear_alpha=alpha)
            rows=_evaluate(design,target,s,loads,wind_for(alpha),
                           {k:scale_nonnegative(v,pvm) for k,v in nominal_pv.items()},phase9)
            return min(row["served_fraction"] for row in rows)
        demand_limit=monotonic_threshold(lambda x:worst(dm=x)+1e-12>=target,.5,2.0,lowest=False)
        pv_limit=monotonic_threshold(lambda x:worst(pvm=x)+1e-12>=target,0.0,1.5)
        sampled=[(alpha,worst(alpha=alpha)) for alpha in (ALPHA_NOMINAL*.8,ALPHA_NOMINAL,ALPHA_NOMINAL*1.2)]
        increasing=all(sampled[i][1] <= sampled[i+1][1]+1e-10 for i in range(2))
        decreasing=all(sampled[i][1]+1e-10 >= sampled[i+1][1] for i in range(2))
        direction="increasing" if increasing else "decreasing" if decreasing else "non_monotonic"
        wind_limit=(monotonic_threshold(lambda x:worst(alpha=x)+1e-12>=target,ALPHA_NOMINAL*.8,ALPHA_NOMINAL*1.2)
                    if increasing else ALPHA_NOMINAL*.8 if decreasing and sampled[0][1]+1e-12>=target else None)
        wind_maximum=(monotonic_threshold(lambda x:worst(alpha=x)+1e-12>=target,ALPHA_NOMINAL*.8,ALPHA_NOMINAL*1.2,lowest=False)
                      if decreasing else ALPHA_NOMINAL*1.2 if increasing and sampled[2][1]+1e-12>=target else None)
        margins.append({"target":target,"design_key":next(r["design_key"] for r in fixed if r["target"]==target),
          "maximum_demand_multiplier_for_target":demand_limit,"minimum_pv_multiplier_for_target":pv_limit,
          "minimum_wind_shear_for_target":wind_limit,"wind_threshold_monotonic":increasing or decreasing,
          "maximum_wind_shear_for_target":wind_maximum,
          "wind_performance_direction_with_alpha":direction,
          "wind_tested_low_served_fraction":sampled[0][1],"wind_tested_nominal_served_fraction":sampled[1][1],
          "wind_tested_high_served_fraction":sampled[2][1]})
    with (PHASE10_DIRECTORY/"physical_feasible_candidates.csv").open(encoding="utf-8",newline="") as handle:
        candidates=[row for row in csv.DictReader(handle) if row["mode"]=="robust_all_profiles"]
    for row in candidates:
        for key in ("wind_count","pv_count","battery_count"): row[key]=int(row[key])
        row["target"]=float(row["target"]);row["worst_served_fraction"]=float(row["worst_served_fraction"])
    unique_candidates={row["design_key"]:row for row in candidates}
    adapted=[]; candidate_status=[];rerankings=0;physical_replays=0
    economic=[s for s in scenario_list if "capex" in s.varied_assumption]
    for scenario in economic:
        for target in selected:
            winner=select_least_cost(unique_candidates.values(),target,
                lambda row:_cost(row,scenario,phase9)["net_present_cost_usd"])
            evaluated=_evaluate(_design(winner),target,scenario,loads,nominal_wind,nominal_pv,phase9)
            for row in evaluated: row["design_basis"]="saved_phase10_candidate_economic_reselection"
            adapted += evaluated;rerankings+=1
            candidate_status.append({"scenario":scenario.name,"target":target,"trigger":"economic perturbation may change ranking",
              "method":f"{SELECTION_SCOPE} (economic reranking)","status":"feasible","design_key":winner["design_key"]})
    failed={(row["scenario"],row["target"]) for row in fixed if row["served_fraction"]+1e-12<row["target"]
            and row["scenario"] not in {s.name for s in economic}}
    physical_start=time.perf_counter()
    for scenario_name,target in sorted(failed):
        scenario=next(s for s in scenario_list if s.name==scenario_name)
        wind=wind_by_alpha[scenario.wind_shear_alpha]
        pv={k:scale_nonnegative(v,scenario.pv_generation_multiplier) for k,v in nominal_pv.items()}
        feasible=[]
        for candidate in unique_candidates.values():
            rows=_evaluate(_design(candidate),target,scenario,loads,wind,pv,phase9);physical_replays+=len(rows)
            if min(r["served_fraction"] for r in rows)+1e-12>=target:
                feasible.append((_cost(candidate,scenario,phase9)["net_present_cost_usd"],candidate["design_key"],rows))
        if feasible:
            chosen=min(feasible,key=lambda item:(item[0],item[1]))[2]
            for row in chosen: row["design_basis"]="saved_phase10_candidate_reselection"
            adapted += chosen
            candidate_status.append({"scenario":scenario_name,"target":target,"trigger":"fixed nominal design violates target",
              "method":f"{SELECTION_SCOPE} (physical replay)","status":"feasible_saved_candidate",
              "design_key":chosen[0]["design_key"]})
        else:
            candidate_status.append({"scenario":scenario_name,"target":target,"trigger":"fixed nominal design violates target",
              "method":f"{SELECTION_SCOPE} (physical replay)","status":"no_feasible_saved_candidate",
              "design_key":""})
    physical_seconds=time.perf_counter()-physical_start
    load_shape=[]
    for scenario in scenario_list:
        for target in selected:
            subset=[r for r in fixed if r["scenario"]==scenario.name and r["target"]==target]
            binding=min(subset,key=lambda r:r["served_fraction"])
            best=max(subset,key=lambda r:r["served_fraction"])
            load_shape.append({"scenario":scenario.name,"target":target,"binding_profile":binding["load_profile"],
              "worst_served_fraction":binding["served_fraction"],"best_profile":best["load_profile"],
              "best_served_fraction":best["served_fraction"],"best_worst_served_fraction_difference":best["served_fraction"]-binding["served_fraction"],
              "lolh_range_hours":max(r["loss_of_load_hours"] for r in subset)-min(r["loss_of_load_hours"] for r in subset),
              "longest_deficit_range_hours":max(r["longest_deficit_hours"] for r in subset)-min(r["longest_deficit_hours"] for r in subset)})
    ranking=[]
    for target in selected:
        nominal=min(r["served_fraction"] for r in fixed if r["target"]==target and r["scenario"]=="nominal")
        for assumption,pair,fraction in (("demand_multiplier",("demand_low","demand_high"),.2),("wind_shear_alpha",("wind_shear_low","wind_shear_high"),.4),("pv_generation_multiplier",("pv_low","pv_high"),.2)):
            values=[min(r["served_fraction"] for r in fixed if r["target"]==target and r["scenario"]==name) for name in pair]
            ranking.append({"target":target,"output":"fixed_design_worst_served_fraction","assumption":assumption,
              "low_value_output":values[0],"high_value_output":values[1],"nominal_output":nominal,
              "normalized_sensitivity_score":abs(values[1]-values[0])/fraction})
    ranking.sort(key=lambda r:(r["target"],-r["normalized_sensitivity_score"]))
    for target in selected:
        for assumption,pair in (("wind_capex_multiplier",("wind_capex_low","wind_capex_high")),
          ("pv_capex_multiplier",("pv_capex_low","pv_capex_high")),
          ("battery_capex_multiplier",("battery_capex_low","battery_capex_high"))):
            values=[]
            for name in pair:
                values.append(next(r["net_present_cost_usd"] for r in adapted if r["scenario"]==name and r["target"]==target))
            ranking.append({"target":target,"output":"saved_candidate_least_cost_npc_usd","assumption":assumption,
              "low_value_output":values[0],"high_value_output":values[1],"nominal_output":final[str(target)]["net_present_cost_usd"],
              "normalized_sensitivity_score":abs(values[1]-values[0])/.4})
    ranking.sort(key=lambda r:(r["target"],r["output"],-r["normalized_sensitivity_score"]))
    stats={"fixed_design_scenario_profile_evaluations":len(fixed),"fixed_design_portfolio_scenario_evaluations":len(scenario_list)*2,
      "reused_nominal_unit_traces":len(nominal_wind)+len(nominal_pv),"new_wind_unit_traces":(len(wind_by_alpha)-1)*len(nominal_wind),
      "economics_only_rerankings":rerankings,"actual_phase10_full_reoptimizations":0,
      "selective_saved_candidate_dispatches":physical_replays,"trace_precomputation_seconds":pre_seconds,
      "fixed_design_seconds":fixed_seconds,"candidate_reselection_seconds":physical_seconds,"total_seconds":time.perf_counter()-started}
    summary={"purpose":"deterministic research sensitivity analysis; bounds are not confidence intervals or probabilities",
      "adaptation_method":ADAPTATION_METHOD,"full_reoptimization_performed":False,
      "scenarios":[asdict(s) for s in scenario_list],"statistics":stats,"robustness_margins":margins,
      "candidate_reselection_status":candidate_status,
      "load_shape_robustness_cost_premium":{str(target):(final[str(target)]["net_present_cost_usd"]-
        min(all_final[shape][str(target)]["net_present_cost_usd"] for shape in loads))/
        min(all_final[shape][str(target)]["net_present_cost_usd"] for shape in loads) for target in selected},
      "single_profile_comparison_provenance":{"label":"saved Phase 10 single-profile candidate-set comparison",
        "source":"outputs/benchmarks/rodina/phase10/scale_aware_energy_optima.json",
        "single_profile_modes":list(loads),"robust_mode":"robust_all_profiles","comparison_metric":"net_present_cost_usd"},
      "nominal_reproduction":{str(t):{"phase10_served_fraction":final[str(t)]["worst_served_fraction"],
        "phase11_served_fraction":min(r["served_fraction"] for r in fixed if r["target"]==t and r["scenario"]=="nominal"),
        "phase10_initial_capex_usd":final[str(t)]["initial_capex_usd"],
        "phase11_initial_capex_usd":next(r["initial_capex_usd"] for r in fixed if r["target"]==t and r["scenario"]=="nominal"),
        "phase10_npc_usd":final[str(t)]["net_present_cost_usd"],
        "phase11_npc_usd":next(r["net_present_cost_usd"] for r in fixed if r["target"]==t and r["scenario"]=="nominal")}
        for t in selected}}
    if write_outputs:
        out=Path(output_directory);out.mkdir(parents=True,exist_ok=True)
        _write_csv(out/"fixed_design_sensitivity.csv",fixed);_write_csv(out/"candidate_reselection_sensitivity.csv",adapted)
        _write_csv(out/"candidate_reselection_status.csv",candidate_status)
        _write_csv(out/"robustness_margins.csv",margins);_write_csv(out/"load_shape_robustness.csv",load_shape)
        _write_csv(out/"sensitivity_ranking.csv",ranking)
        stats["figures_written"]=_write_plots(out,fixed,ranking)
        (out/"phase11_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return {"fixed":fixed,"candidate_reselection":adapted,"margins":margins,"load_shape":load_shape,"ranking":ranking,"summary":summary}

def update_combined_scenarios(*, output_directory=OUTPUT_DIRECTORY):
    """Incrementally replace only the two combined physical scenarios in saved Phase 11 outputs."""
    started=time.perf_counter();out=Path(output_directory)
    weather,phase9,loads,_,nominal_wind,nominal_pv,pre_seconds=precompute()
    combined=[scenario for scenario in scenarios() if scenario.category=="combined"]
    wind_by_alpha={scenario.wind_shear_alpha:benchmark_wind(weather,shear_exponent=scenario.wind_shear_alpha)[1]
                   for scenario in combined}
    all_final=json.loads((PHASE10_DIRECTORY/"scale_aware_energy_optima.json").read_text(encoding="utf-8"))
    final=all_final["robust_all_profiles"]
    selected={float(target):_design(row) for target,row in final.items()}
    fixed_start=time.perf_counter();new_fixed=[]
    for scenario in combined:
        pv={key:scale_nonnegative(trace,scenario.pv_generation_multiplier) for key,trace in nominal_pv.items()}
        for target,design in selected.items():
            new_fixed += _evaluate(design,target,scenario,loads,wind_by_alpha[scenario.wind_shear_alpha],pv,phase9)
    fixed_seconds=time.perf_counter()-fixed_start
    old_fixed=[row for row in _read_csv(out/"fixed_design_sensitivity.csv")
               if row["scenario"] not in {scenario.name for scenario in combined}]
    order={scenario.name:index for index,scenario in enumerate(scenarios())}
    fixed=sorted(old_fixed+new_fixed,key=lambda row:(order[row["scenario"]],float(row["target"]),row["load_profile"]))

    candidates=_read_csv(PHASE10_DIRECTORY/"physical_feasible_candidates.csv")
    candidates=[row for row in candidates if row["mode"]=="robust_all_profiles"]
    for row in candidates:
        for key in ("wind_count","pv_count","battery_count"): row[key]=int(row[key])
        row["target"]=float(row["target"]);row["worst_served_fraction"]=float(row["worst_served_fraction"])
    unique_candidates={row["design_key"]:row for row in candidates}
    prior_adaptation=out/"candidate_reselection_sensitivity.csv"
    adapted=[row for row in _read_csv(prior_adaptation) if row["scenario"] not in {scenario.name for scenario in combined}]
    for row in adapted:
        if row.get("design_basis")=="saved_phase10_candidate_economic_reselection":
            row["design_basis"]="saved_phase10_candidate_economic_reselection"
        else: row["design_basis"]="saved_phase10_candidate_reselection"
    prior_status=out/"candidate_reselection_status.csv"
    candidate_status=[row for row in _read_csv(prior_status) if row["scenario"] not in {scenario.name for scenario in combined}]
    for row in candidate_status:
        suffix="economic reranking" if row["trigger"]=="economic perturbation may change ranking" else "physical replay"
        row["method"]=f"{SELECTION_SCOPE} ({suffix})"
    physical_start=time.perf_counter();physical_replays=0
    for scenario in combined:
        scenario_fixed=[row for row in new_fixed if row["scenario"]==scenario.name]
        for target in selected:
            target_fixed=[row for row in scenario_fixed if row["target"]==target]
            if min(row["served_fraction"] for row in target_fixed)+1e-12>=target: continue
            pv={key:scale_nonnegative(trace,scenario.pv_generation_multiplier) for key,trace in nominal_pv.items()}
            feasible=[]
            for candidate in unique_candidates.values():
                rows=_evaluate(_design(candidate),target,scenario,loads,wind_by_alpha[scenario.wind_shear_alpha],pv,phase9)
                physical_replays+=len(rows)
                if min(row["served_fraction"] for row in rows)+1e-12>=target:
                    feasible.append((_cost(candidate,scenario,phase9)["net_present_cost_usd"],candidate["design_key"],rows))
            if feasible:
                chosen=min(feasible,key=lambda item:(item[0],item[1]))[2]
                for row in chosen: row["design_basis"]="saved_phase10_candidate_reselection"
                adapted += chosen
                candidate_status.append({"scenario":scenario.name,"target":target,
                  "trigger":"fixed nominal design violates target",
                  "method":f"{SELECTION_SCOPE} (physical replay)",
                  "status":"feasible_saved_candidate","design_key":chosen[0]["design_key"]})
            else:
                candidate_status.append({"scenario":scenario.name,"target":target,
                  "trigger":"fixed nominal design violates target",
                  "method":f"{SELECTION_SCOPE} (physical replay)",
                  "status":"no_feasible_saved_candidate","design_key":""})
    physical_seconds=time.perf_counter()-physical_start
    adapted.sort(key=lambda row:(order[row["scenario"]],float(row["target"]),row["load_profile"]))
    candidate_status.sort(key=lambda row:(order[row["scenario"]],float(row["target"])))

    old_shape=[row for row in _read_csv(out/"load_shape_robustness.csv")
               if row["scenario"] not in {scenario.name for scenario in combined}]
    new_shape=[]
    for scenario in combined:
        for target in selected:
            subset=[row for row in new_fixed if row["scenario"]==scenario.name and row["target"]==target]
            binding=min(subset,key=lambda row:row["served_fraction"]);best=max(subset,key=lambda row:row["served_fraction"])
            new_shape.append({"scenario":scenario.name,"target":target,"binding_profile":binding["load_profile"],
              "worst_served_fraction":binding["served_fraction"],"best_profile":best["load_profile"],
              "best_served_fraction":best["served_fraction"],
              "best_worst_served_fraction_difference":best["served_fraction"]-binding["served_fraction"],
              "lolh_range_hours":max(row["loss_of_load_hours"] for row in subset)-min(row["loss_of_load_hours"] for row in subset),
              "longest_deficit_range_hours":max(row["longest_deficit_hours"] for row in subset)-min(row["longest_deficit_hours"] for row in subset)})
    load_shape=sorted(old_shape+new_shape,key=lambda row:(order[row["scenario"]],float(row["target"])))
    ranking=_read_csv(out/"sensitivity_ranking.csv")
    for row in ranking:
        if row["output"]=="reranked_optimal_npc_usd": row["output"]="saved_candidate_least_cost_npc_usd"
    summary=json.loads((out/"phase11_summary.json").read_text(encoding="utf-8"))
    summary.update(adaptation_method=ADAPTATION_METHOD,full_reoptimization_performed=False,
      scenarios=[asdict(scenario) for scenario in scenarios()],candidate_reselection_status=candidate_status,
      single_profile_comparison_provenance={"label":"saved Phase 10 single-profile candidate-set comparison",
        "source":"outputs/benchmarks/rodina/phase10/scale_aware_energy_optima.json",
        "single_profile_modes":list(loads),"robust_mode":"robust_all_profiles","comparison_metric":"net_present_cost_usd"})
    summary["statistics"]={"update_scope":"combined_scenarios_only",
      "fixed_design_scenario_profile_evaluations":len(new_fixed),
      "fixed_design_portfolio_scenario_evaluations":len(combined)*len(selected),
      "reused_nominal_unit_traces":len(nominal_wind)+len(nominal_pv),
      "new_wind_unit_traces":len(combined)*len(nominal_wind),"economics_only_rerankings":0,
      "actual_phase10_full_reoptimizations":0,"selective_saved_candidate_dispatches":physical_replays,
      "trace_precomputation_seconds":pre_seconds,"fixed_design_seconds":fixed_seconds,
      "candidate_reselection_seconds":physical_seconds,"total_seconds":time.perf_counter()-started,
      "figures_written":0}
    _write_csv(out/"fixed_design_sensitivity.csv",fixed)
    _write_csv(out/"candidate_reselection_sensitivity.csv",adapted)
    _write_csv(out/"candidate_reselection_status.csv",candidate_status)
    _write_csv(out/"load_shape_robustness.csv",load_shape);_write_csv(out/"sensitivity_ranking.csv",ranking)
    (out/"phase11_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return {"fixed":new_fixed,"candidate_reselection":[row for row in adapted if row["scenario"] in {s.name for s in combined}],
      "summary":summary}
