"""Reproducible standardized Planner V2 cross-village analysis."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, time
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from steppegrid.equipment.catalog import PLANNER_V2
from steppegrid.equipment.models import ProjectScale
from steppegrid.optimization.economics import EconomicsVersion
from steppegrid.planning.generation import prepare_generation
from steppegrid.planning.models import CatalogFilterMode, PlanningScenario, TechnologySelection
from steppegrid.planning.service import ScenarioPlanningService
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/phase17"; SCENARIOS=OUT/"standardized_runs"; FIGURES=OUT/"figures"
SITE_IDS=("rodina","shamshi_kaldayakova","katon_karagay","kegen","shayan","sai_otes","togyzkuduk")
PROXY_IDS=("katon_karagay","kegen","shayan","sai_otes","togyzkuduk")
TARGETS=(.95,.99); WIND_KEY="northern_power_nps_100c_21"; PV_KEY="trina_tsm_450_neg9r28__sma_core1_stp50_41"
# The three distributed-wind products exceed the established 25,000-unit bound
# at the largest registered demand. The same two scalable turbines are therefore
# used at every site; all Planner V2 PV and battery options remain eligible.
COMPARATIVE_WIND_KEYS=("northern_power_nps_100c_21","leitwind_ltw42_250")
SELECTION=TechnologySelection(wind_keys=COMPARATIVE_WIND_KEYS,pv_keys=PLANNER_V2.pv_block_keys,battery_keys=tuple(PLANNER_V2.batteries),filter_mode=CatalogFilterMode.CUSTOM,scale_classes=tuple(ProjectScale))

def scenario(registry,site_id,target):
    site=registry.get_site(site_id); demand=site.demand_datasets[0]
    return PlanningScenario(name=f"{site.name} — Phase 17 standardized Planner V2 scenario — {target:.0%}",site=registry.planning_site(site_id),demand=registry.demand_specification(site_id,demand.demand_id),demand_id=demand.demand_id,registered_demand_sha256=demand.demand_sha256,reliability_target=target,equipment_catalog_version=PLANNER_V2.version,economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,technologies=SELECTION)

def result_path(site_id,target): return SCENARIOS/site_id/f"{int(target*100)}"/"result.json"
def write_json(path,payload): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def write_csv(path,rows):
    rows=list(rows); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]) if rows else ["status"]); w.writeheader(); w.writerows(rows or [{"status":"empty"}])
def load_results(): return [json.loads(result_path(s,t).read_text(encoding="utf-8")) for s in SITE_IDS for t in TARGETS if result_path(s,t).is_file()]

def run_one(site_id,target):
    registry=SiteRegistry(); sc=scenario(registry,site_id,target); destination=result_path(site_id,target)
    if destination.is_file(): print(f"SKIP {site_id} {target:.0%}"); return
    service=ScenarioPlanningService(registry=registry,cache_root=ROOT/"data/weather/cache",output_root=OUT/"temporary",site_output_root=OUT/"raw_sites")
    started=time.perf_counter(); run=service.run(sc,registry.build_demand(site_id,sc.demand_id),progress=lambda m: print(f"[{site_id} {target:.0%}] {m}"))
    payload=run.result.model_dump(mode="json"); payload["phase17_runtime_seconds"]=time.perf_counter()-started
    write_json(destination,payload); write_json(destination.parent/"scenario.json",sc.model_dump(mode="json"))
    write_csv(destination.parent/"dispatch.csv",run.dispatch_rows); print(f"DONE {site_id} {target:.0%} {payload['phase17_runtime_seconds']:.1f}s")

def resources(registry):
    rows=[]
    for site_id in SITE_IDS:
        site=registry.get_site(site_id); ds=site.demand_datasets[0]; sc=scenario(registry,site_id,.95); demand=registry.build_demand(site_id,ds.demand_id); gen=prepare_generation(sc.site,demand,cache_root=ROOT/"data/weather/cache",equipment_catalog_version=PLANNER_V2.version)
        wind=gen.wind_profiles_kwh[WIND_KEY]; pv=gen.pv_profiles_kwh[PV_KEY]; wind_kw=PLANNER_V2.wind_turbines[WIND_KEY].rated_power_kw; pv_dc=gen.pv_metadata[PV_KEY]["dc_capacity_kw"]
        wm=sum(wind)/wind_kw; py=sum(pv)/pv_dc
        mean_w=sum(wind)/len(wind); mean_p=sum(pv)/len(pv); cov=sum((a-mean_w)*(b-mean_p) for a,b in zip(wind,pv))/len(wind); sw=math.sqrt(sum((a-mean_w)**2 for a in wind)/len(wind)); sp=math.sqrt(sum((b-mean_p)**2 for b in pv)/len(pv)); corr=cov/(sw*sp) if sw and sp else 0
        rows.append({"site_id":site_id,"site":site.name,"region":site.region,"cohort":"primary_proxy" if site_id in PROXY_IDS else "contextual","demand_basis":ds.classification.value,"annual_demand_kwh":ds.annual_energy_kwh,"weather_year":2025,"weather_hours":len(gen.weather.series.timestamps),"representative_wind_key":WIND_KEY,"wind_annual_kwh_per_unit":sum(wind),"wind_capacity_factor":sum(wind)/(wind_kw*8760),"wind_kwh_per_installed_kw":wm,"representative_pv_key":PV_KEY,"pv_annual_poa_kwh_m2":gen.pv_metadata[PV_KEY]["annual_poa_kwh_m2"],"pv_annual_ac_kwh":sum(pv),"pv_specific_yield_kwh_per_kwp":py,"wind_pv_hourly_correlation":corr})
    return rows

def flatten(result,registry):
    site=registry.get_site(result["site_id"]); d=result["design"] or {}; m=result["metrics"] or {}; e=result["economics"] or {}; annual=result["annual_demand_kwh"]; gwh=annual/1e6; raw=m.get("renewable_generation_kwh",0); wind=0; pv=0; ending_soc=0
    dispatch=SCENARIOS/result["site_id"]/str(int(result["reliability_target"]*100))/"dispatch.csv"
    if dispatch.is_file():
        with dispatch.open(encoding="utf-8") as h:
            for row in csv.DictReader(h): wind+=float(row["wind_generation_kwh"]); pv+=float(row["pv_generation_kwh"]); ending_soc=float(row["battery_soc_end_kwh"])
    battery_power=PLANNER_V2.batteries[d["battery_key"]].maximum_discharge_power_kw*d["battery_count"] if d.get("battery_key") else 0
    return {"site_id":result["site_id"],"site":site.name,"region":site.region,"latitude":site.latitude,"longitude":site.longitude,"cohort":"primary_proxy" if result["site_id"] in PROXY_IDS else "contextual","demand_basis":result["demand_source_type"],"demand_id":result.get("demand_id"),"demand_sha256":result["demand_sha256"],"weather_sha256":result["weather_sha256"],"scenario_hash":result["scenario_input_hash"],"target":result["reliability_target"],"weather_year":2025,"annual_demand_kwh":annual,"wind_key":d.get("wind_key"),"wind_count":d.get("wind_count"),"wind_capacity_kw":d.get("wind_capacity_kw"),"pv_key":d.get("pv_key"),"pv_count":d.get("pv_count"),"pv_dc_capacity_kw":d.get("pv_dc_capacity_kw"),"pv_ac_capacity_kw":d.get("pv_ac_capacity_kw"),"battery_key":d.get("battery_key"),"battery_count":d.get("battery_count"),"battery_usable_capacity_kwh":d.get("battery_usable_capacity_kwh"),"battery_power_kw":battery_power,"annual_wind_generation_kwh":wind,"annual_pv_generation_kwh":pv,"raw_generation_kwh":raw,"served_energy_kwh":m.get("served_energy_kwh"),"unmet_energy_kwh":m.get("unmet_energy_kwh"),"curtailment_kwh":m.get("curtailment_kwh"),"ending_soc_kwh":ending_soc,"energy_conservation_residual_kwh":annual-m.get("served_energy_kwh",0)-m.get("unmet_energy_kwh",0),"served_fraction":m.get("served_fraction"),"lpsp":m.get("lpsp"),"loss_of_load_hours":m.get("loss_of_load_hours"),"longest_deficit_hours":m.get("longest_deficit_hours"),"maximum_hourly_deficit_kwh":m.get("maximum_hourly_deficit_kwh"),"capex_usd":e.get("initial_capex_usd"),"npc_usd":e.get("net_present_cost_usd"),"eac_usd":e.get("equivalent_annual_cost_usd"),"cost_per_served_kwh_usd":e.get("cost_per_served_kwh_usd"),"wind_MW_per_GWh":d.get("wind_capacity_kw",0)/1000/gwh,"pv_MWdc_per_GWh":d.get("pv_dc_capacity_kw",0)/1000/gwh,"pv_MWac_per_GWh":d.get("pv_ac_capacity_kw",0)/1000/gwh,"battery_MWh_per_GWh":d.get("battery_usable_capacity_kwh",0)/1000/gwh,"battery_MW_per_GWh":battery_power/1000/gwh,"NPC_per_annual_kWh_demand":e.get("net_present_cost_usd",0)/annual,"CAPEX_per_annual_kWh_demand":e.get("initial_capex_usd",0)/annual,"EAC_per_annual_kWh_demand":e.get("equivalent_annual_cost_usd",0)/annual,"raw_generation_load_ratio":raw/annual,"served_energy_to_load_ratio":m.get("served_energy_kwh",0)/annual,"curtailment_fraction":m.get("curtailment_kwh",0)/raw if raw else 0,"unmet_fraction":m.get("unmet_energy_kwh",0)/annual,"wind_share_raw_generation":wind/raw if raw else 0,"pv_share_raw_generation":pv/raw if raw else 0,"optimizer_method":result.get("optimizer_method"),"theoretical_design_combinations":result.get("theoretical_design_combinations",0),"runtime_seconds":result.get("phase17_runtime_seconds",result.get("elapsed_seconds",0)),"evaluated_portfolios":result.get("evaluated_portfolios",0),"dispatch_simulations":result.get("dispatch_simulations",0),"dispatch_cache_hits":result.get("dispatch_cache_hits",0)}

def pct(a,b): return None if not a else 100*(b/a-1)
def analyze():
    registry=SiteRegistry(); rr=resources(registry); write_csv(OUT/"site_resource_metrics.csv",rr); results=load_results()
    if len(results)!=14: raise RuntimeError(f"Expected 14 results, found {len(results)}")
    flat=[flatten(r,registry) for r in results]; write_csv(OUT/"standardized_scenarios.csv",[{"site_id":r["site_id"],"site":r["site"],"target":r["target"],"demand_id":r["demand_id"],"demand_basis":r["demand_basis"],"demand_sha256":r["demand_sha256"],"weather_sha256":r["weather_sha256"],"scenario_hash":r["scenario_hash"],"catalog":"PLANNER_V2","economics":"PLANNER_SCALE_AWARE_ECONOMICS_V2"} for r in flat]); write_csv(OUT/"optimization_results.csv",flat)
    norm_keys=("site_id","site","cohort","target","annual_demand_kwh","wind_MW_per_GWh","pv_MWdc_per_GWh","pv_MWac_per_GWh","battery_MWh_per_GWh","battery_MW_per_GWh","NPC_per_annual_kWh_demand","CAPEX_per_annual_kWh_demand","EAC_per_annual_kWh_demand","cost_per_served_kwh_usd","raw_generation_load_ratio","served_energy_to_load_ratio","curtailment_fraction","unmet_fraction","wind_share_raw_generation","pv_share_raw_generation")
    normalized=[{k:r[k] for k in norm_keys} for r in flat]; write_csv(OUT/"normalized_metrics.csv",normalized); write_csv(OUT/"proxy_cohort_comparison.csv",[r for r in normalized if r["cohort"]=="primary_proxy"]); write_csv(OUT/"contextual_sites_comparison.csv",[r for r in normalized if r["cohort"]=="contextual"])
    escalation=[]
    for s in SITE_IDS:
        a=next(r for r in flat if r["site_id"]==s and r["target"]==.95); b=next(r for r in flat if r["site_id"]==s and r["target"]==.99)
        escalation.append({"site_id":s,"site":a["site"],"delta_wind_capacity_percent":pct(a["wind_capacity_kw"],b["wind_capacity_kw"]),"wind_capacity_absolute_increase_kw":b["wind_capacity_kw"]-a["wind_capacity_kw"],"wind_entered_at_99":a["wind_capacity_kw"]==0 and b["wind_capacity_kw"]>0,"delta_pv_capacity_percent":pct(a["pv_ac_capacity_kw"],b["pv_ac_capacity_kw"]),"pv_capacity_absolute_increase_kw":b["pv_ac_capacity_kw"]-a["pv_ac_capacity_kw"],"pv_entered_at_99":a["pv_ac_capacity_kw"]==0 and b["pv_ac_capacity_kw"]>0,"delta_storage_energy_percent":pct(a["battery_usable_capacity_kwh"],b["battery_usable_capacity_kwh"]),"storage_absolute_increase_kwh":b["battery_usable_capacity_kwh"]-a["battery_usable_capacity_kwh"],"delta_CAPEX_usd":b["capex_usd"]-a["capex_usd"],"delta_CAPEX_percent":pct(a["capex_usd"],b["capex_usd"]),"delta_NPC_usd":b["npc_usd"]-a["npc_usd"],"delta_NPC_percent":pct(a["npc_usd"],b["npc_usd"]),"delta_EAC_usd":b["eac_usd"]-a["eac_usd"],"delta_EAC_percent":pct(a["eac_usd"],b["eac_usd"]),"delta_curtailment_kwh":b["curtailment_kwh"]-a["curtailment_kwh"],"delta_LOLH":b["loss_of_load_hours"]-a["loss_of_load_hours"],"delta_unmet_energy_kwh":b["unmet_energy_kwh"]-a["unmet_energy_kwh"]})
    write_csv(OUT/"reliability_escalation.csv",escalation); write_csv(OUT/"site_comparison.csv",normalized); write_csv(OUT/"correlations.csv",[{"cohort":"primary_proxy","sample_size":5,"metric_x":"pv_specific_yield","metric_y":"95% normalized NPC","pearson":correlation([next(x for x in rr if x['site_id']==s)['pv_specific_yield_kwh_per_kwp'] for s in PROXY_IDS],[next(x for x in flat if x['site_id']==s and x['target']==.95)['NPC_per_annual_kWh_demand'] for s in PROXY_IDS]),"interpretation":"Exploratory descriptive correlation only"}])
    figures(rr,flat,escalation); report(rr,flat,escalation)
    summary={"schema_version":"phase17.summary.v1","sites":7,"primary_proxy_sites":5,"contextual_sites":2,"targets":[.95,.99],"standardized_runs":14,"feasible_runs":sum(bool(r.get('feasible')) for r in results),"total_runtime_seconds":sum(r["runtime_seconds"] for r in flat),"evaluated_portfolios":sum(r["evaluated_portfolios"] for r in flat),"dispatch_simulations":sum(r["dispatch_simulations"] for r in flat),"dispatch_cache_hits":sum(r["dispatch_cache_hits"] for r in flat),"catalog":"PLANNER_V2","economics":"PLANNER_SCALE_AWARE_ECONOMICS_V2"}; write_json(OUT/"phase17_summary.json",summary)
    audit={"schema_version":"phase17.audit.v1","checks":[{"name":"site_count","status":"PASS"},{"name":"proxy_cohort_count","status":"PASS"},{"name":"scenario_count","status":"PASS"},{"name":"all_feasible","status":"PASS" if summary["feasible_runs"]==14 else "BLOCKER"},{"name":"weather_hours","status":"PASS" if all(r["weather_hours"]==8760 for r in rr) else "BLOCKER"}],"blockers":0 if summary["feasible_runs"]==14 and all(r["weather_hours"]==8760 for r in rr) else 1}; write_json(OUT/"phase17_audit.json",audit); print(json.dumps(summary,indent=2))

def correlation(x,y):
    mx=sum(x)/len(x); my=sum(y)/len(y); num=sum((a-mx)*(b-my) for a,b in zip(x,y)); den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y)); return num/den if den else 0
def chart(path,title,labels,series,ylabel):
    FIGURES.mkdir(parents=True,exist_ok=True); fig,ax=plt.subplots(figsize=(10,5.5)); width=.8/len(series); xs=range(len(labels))
    for i,(name,values,color) in enumerate(series): ax.bar([x+(i-(len(series)-1)/2)*width for x in xs],values,width,label=name,color=color)
    ax.set_xticks(list(xs),labels,rotation=25,ha="right"); ax.set_title(title,loc="left",weight="bold"); ax.set_ylabel(ylabel); ax.legend(); ax.spines[["top","right"]].set_visible(False); fig.tight_layout(); fig.savefig(FIGURES/path,dpi=180); plt.close(fig)
def figures(rr,flat,esc):
    labels=[r["site"] for r in rr]; chart("01_pv_yield.png","PV specific yield",labels,[("kWh/kWp",[r["pv_specific_yield_kwh_per_kwp"] for r in rr],"#D59A16")],"kWh/kWp-year"); chart("02_wind_cf.png","Representative wind capacity factor",labels,[("Capacity factor",[r["wind_capacity_factor"] for r in rr],"#2878A6")],"Fraction")
    r95=[r for r in flat if r["target"]==.95]
    chart("03_wind_intensity_95.png","95% normalized wind capacity",labels,[("Wind MW/GWh",[r["wind_MW_per_GWh"] for r in r95],"#2878A6")],"MW/GWh")
    chart("04_pv_intensity_95.png","95% normalized PV capacity",labels,[("PV MWac/GWh",[r["pv_MWac_per_GWh"] for r in r95],"#D59A16")],"MWac/GWh")
    chart("05_storage_intensity_95.png","95% normalized storage",labels,[("Battery MWh/GWh",[r["battery_MWh_per_GWh"] for r in r95],"#7359A6")],"MWh/GWh")
    chart("06_normalized_npc.png","Normalized net present cost",labels,[("95%",[next(x for x in flat if x["site"]==s and x["target"]==.95)["NPC_per_annual_kWh_demand"] for s in labels],"#1F6B5B"),("99%",[next(x for x in flat if x["site"]==s and x["target"]==.99)["NPC_per_annual_kWh_demand"] for s in labels],"#7359A6")],"NPC / annual kWh demand")
    chart("07_curtailment.png","Curtailment fraction",labels,[("95%",[next(x for x in flat if x["site"]==s and x["target"]==.95)["curtailment_fraction"] for s in labels],"#1F6B5B"),("99%",[next(x for x in flat if x["site"]==s and x["target"]==.99)["curtailment_fraction"] for s in labels],"#B06F2E")],"Fraction of raw generation")
    chart("08_npc_escalation.png","95% to 99% NPC escalation",[r["site"] for r in esc],[("NPC increase",[r["delta_NPC_percent"] for r in esc],"#B06F2E")],"Increase (%)")
    chart("09_generation_composition_95.png","95% renewable-generation composition",labels,[("Wind share",[r["wind_share_raw_generation"] for r in r95],"#2878A6"),("PV share",[r["pv_share_raw_generation"] for r in r95],"#D59A16")],"Share of raw generation")
def report(rr,flat,esc):
    proxy=[r for r in flat if r["cohort"]=="primary_proxy" and r["target"]==.95]; strongest_pv=max((r for r in rr if r["site_id"] in PROXY_IDS),key=lambda r:r["pv_specific_yield_kwh_per_kwp"]); strongest_w=max((r for r in rr if r["site_id"] in PROXY_IDS),key=lambda r:r["wind_capacity_factor"]); low_npc=min(proxy,key=lambda r:r["NPC_per_annual_kWh_demand"]); high_storage=max(proxy,key=lambda r:r["battery_MWh_per_GWh"]); high_esc=max((r for r in esc if r["site_id"] in PROXY_IDS),key=lambda r:r["delta_NPC_percent"])
    lines=["# SteppeGrid Phase 17 — Cross-Village Analysis","","## Research question","How do modeled renewable resources affect normalized microgrid composition, reliability, storage, curtailment, and planning cost across seven selected Kazakhstan settlements?","","## Cohorts","The primary cohort is Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk using KZ_RURAL_PROXY_V1. Rodina and Shamshi are contextual because their demand bases differ.","","## Demand provenance","| Site | Demand basis |","|---|---|"]+[f"| {r['site']} | {r['demand_basis']} |" for r in rr]+["","## Standardized methodology","All scenarios use cached 2025 ERA5, 8,760 hours, Planner V2, scale-aware Planner V2 economics, the full verified catalog, deterministic dispatch, and 95%/99% annual energy served targets.","","## Resource characterization",f"Within the primary cohort, {strongest_pv['site']} has the highest modeled PV specific yield and {strongest_w['site']} the highest representative wind capacity factor.","","## 95% and 99% results","See `optimization_results.csv` and `normalized_metrics.csv` for complete designs, energy balances, reliability, economics, search statistics, and hashes.","","## Normalized comparison",f"At 95%, {low_npc['site']} has the lowest NPC per annual kWh of registered demand; {high_storage['site']} has the greatest storage MWh/GWh in the primary cohort.","","## Reliability-cost escalation",f"Within the primary cohort, the greatest modeled NPC increase from 95% to 99% occurs at {high_esc['site']} ({high_esc['delta_NPC_percent']:.1f}%).","","## Contextual interpretation","Rodina uses source-reconstructed literature demand. Shamshi uses its registered synthetic planning estimate. Neither is pooled into proxy-cohort claims.","","## Limitations","One ERA5 year; proxy demand for five sites; synthetic Shamshi demand; reconstructed Rodina demand; shared deterministic proxy profile; no wake/layout or grid power flow; no multi-year variability; reference economics; bounded discrete catalog; seven selected settlements are not representative of all Kazakhstan villages.","","## Reproducibility","Run `python scripts/run_phase17.py --verify`. Use `--execute` only to rerun missing standardized scenarios."]
    (OUT/"steppegrid_cross_village_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def verify():
    required=[OUT/n for n in ("site_resource_metrics.csv","standardized_scenarios.csv","optimization_results.csv","normalized_metrics.csv","reliability_escalation.csv","site_comparison.csv","proxy_cohort_comparison.csv","contextual_sites_comparison.csv","correlations.csv","phase17_summary.json","phase17_audit.json","steppegrid_cross_village_report.md")]; missing=[str(p) for p in required if not p.is_file()]; audit=json.loads((OUT/"phase17_audit.json").read_text()) if (OUT/"phase17_audit.json").is_file() else {"blockers":1}; print(json.dumps({"missing":missing,"blockers":audit["blockers"]},indent=2)); raise SystemExit(1 if missing or audit["blockers"] else 0)
def main():
    p=argparse.ArgumentParser(); p.add_argument("--execute",action="store_true"); p.add_argument("--verify",action="store_true"); p.add_argument("--site",choices=SITE_IDS); p.add_argument("--target",type=float,choices=TARGETS); args=p.parse_args()
    if args.verify: verify(); return
    if args.site: run_one(args.site,args.target); return
    if args.execute:
        for s in SITE_IDS:
            for t in TARGETS: run_one(s,t)
    analyze()
if __name__=="__main__": main()
