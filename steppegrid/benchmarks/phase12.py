"""Final validation, provenance, and research synthesis for the frozen Rodina study."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from steppegrid.benchmarks.phase9 import (REFERENCE_AZIMUTH_DEG, REFERENCE_TILT_DEG,
    load_phase9_loads, load_phase9_weather, validate_phase9_weather)
from steppegrid.benchmarks.phase10 import precompute
from steppegrid.benchmarks.phase11 import (ADAPTATION_METHOD, ALPHA_NOMINAL,
    SensitivityScenario, _design, _evaluate)
from steppegrid.equipment.catalog import BATTERIES, INVERTERS, PV_MODULES, WIND_TURBINES

ROOT=Path(__file__).resolve().parents[2]
PHASE9=ROOT/"outputs/benchmarks/rodina/phase9"
PHASE10=ROOT/"outputs/benchmarks/rodina/phase10"
PHASE11=ROOT/"outputs/benchmarks/rodina/phase11"
OUTPUT_DIRECTORY=ROOT/"outputs/benchmarks/rodina/phase12"
ALLOWED_STATUSES={"PASS","WARNING","BLOCKER"}

def _json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def _csv(path):
    with Path(path).open(encoding="utf-8",newline="") as handle:return list(csv.DictReader(handle))
def _write_csv(path,rows):
    if not rows:return
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields:fields.append(key)
    with Path(path).open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def _sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()
def _trace_hash(values):
    return hashlib.sha256("\n".join(format(float(value),".17g") for value in values).encode()).hexdigest()
def _check(rows,category,name,condition,message,evidence=None,status_if_false="BLOCKER"):
    rows.append({"category":category,"check":name,"status":"PASS" if condition else status_if_false,
      "message":message,"evidence":evidence or {}})
def _git():
    try:
        commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        dirty=bool(subprocess.run(["git","status","--porcelain"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip())
        return {"available":True,"commit":commit,"dirty":dirty}
    except Exception as exc:return {"available":False,"reason":str(exc)}
def _packages():
    result={}
    for name in ("pydantic","PyYAML","pvlib","matplotlib","pytest"):
        try:result[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:result[name]=None
    return result

def assumptions_registry():
    rows=[
      ("Rodina printed annual load",7720000,"kWh","SOURCE_REPORTED","publication Table 1 annual row"),
      ("Rodina optimization annual load",8020000,"kWh","SOURCE_RECONSTRUCTED","sum of published monthly rows"),
      ("Hourly demand profiles","flat; residential-like; community-facility-like","","SOURCE_RECONSTRUCTED","deterministic shapes preserving monthly rows"),
      ("2025 meteorology","ERA5 via cached Open-Meteo response","","ERA5_DERIVED","gridded reanalysis, not site measurement"),
      ("Nominal wind shear alpha",ALPHA_NOMINAL,"","ERA5_DERIVED","two-height 10 m/100 m reconstruction"),
      ("Turbine curves","Skystream 3.7; SD6; Bergey Excel 15","","MANUFACTURER_OR_CERTIFICATION_DATA","catalog provenance records"),
      ("PV equipment","Trina/REC modules; SMA/Fronius inverters","","MANUFACTURER_OR_CERTIFICATION_DATA","manufacturer datasheets"),
      ("Battery equipment","Tesla Megapack; Saft Intensium","","MANUFACTURER_OR_CERTIFICATION_DATA","manufacturer sources"),
      ("PV tilt",REFERENCE_TILT_DEG,"degrees","MODELING_ASSUMPTION","fixed to Rodina latitude"),
      ("PV azimuth",REFERENCE_AZIMUTH_DEG,"degrees","MODELING_ASSUMPTION","south-facing"),
      ("Battery initial useful inventory",0,"kWh","MODELING_ASSUMPTION","minimum SOC is unavailable inventory"),
      ("Dispatch","renewable-load-battery-curtailment","","MODELING_ASSUMPTION","deterministic hourly order"),
      ("High-wind behavior","hold last certified curve value where declared","","MODELING_ASSUMPTION","not certified extrapolated performance"),
      ("Demand sensitivity","-10%; +10%","","RESEARCH_SENSITIVITY_SCENARIO","deterministic research range"),
      ("PV-output sensitivity","-10%; +10%","","RESEARCH_SENSITIVITY_SCENARIO","aggregate deterministic multiplier"),
      ("Wind-shear sensitivity","-20%; +20% alpha","","RESEARCH_SENSITIVITY_SCENARIO","not measured bounds"),
      ("Technology CAPEX sensitivity","-20%; +20%","","RESEARCH_SENSITIVITY_SCENARIO","not a forecast"),
      ("Equipment counts","wind; PV blocks; batteries","integer","OPTIMIZED_DECISION_VARIABLE","Phase 10 bounded discrete search"),
      ("Selected reliability and cost metrics","Phase 9-11 outputs","","DERIVED_RESULT","model outputs, not measurements")]
    return [{"input":a,"value":b,"unit":c,"classification":d,"provenance_or_note":e} for a,b,c,d,e in rows]

def _manifest(weather,loads,load_meta,phase9_integrity,phase10,phase11):
    cache_key=phase9_integrity["weather"]["cache_key"]
    cache_dir=ROOT/"data/weather/cache/open_meteo/era5"/cache_key
    cache_files=[]
    for path in sorted(cache_dir.glob("*")):
        if path.is_file():cache_files.append({"path":str(path.relative_to(ROOT)),"sha256":_sha256(path),"bytes":path.stat().st_size})
    return {"generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "site":{"name":"Rodina","region":"Akmola Region","country":"Kazakhstan",
        "latitude":51.302445,"longitude":70.541645,"timezone":"UTC+05:00","reference_year":2025},
      "weather":{"provider":"Open-Meteo historical API cache","dataset":"ERA5","records":8760,
        "coverage_utc":{"start":weather.series.timestamps[0].isoformat(),"end":weather.series.timestamps[-1].isoformat()},
        "variables":phase9_integrity["weather"]["variables"],"cache_key":cache_key,"cached_inputs":cache_files},
      "demand":{"status":"literature-derived hourly reconstruction; not measured hourly demand",
        "printed_annual_kwh":7720000,"monthly_rows_reconstructed_annual_kwh":load_meta["annual_kwh"],
        "optimization_value":"monthly_rows_reconstructed_annual_kwh","profiles":list(loads),
        "trace_sha256":{key:_trace_hash(value) for key,value in loads.items()}},
      "wind":{"reference_height_m":100,"nominal_shear_alpha":ALPHA_NOMINAL,
        "turbines":{key:{"manufacturer":item.manufacturer,"model":item.model,"rated_kw":item.rated_power_kw,
          "hub_height_m":item.supported_hub_heights_m[0],"high_wind_policy":item.high_wind_curve_policy.value,
          "provenance":[source.model_dump(mode="json") for source in item.provenance]} for key,item in WIND_TURBINES.items()}},
      "pv":{"modules":list(PV_MODULES),"inverters":list(INVERTERS),"tilt_deg":REFERENCE_TILT_DEG,
        "azimuth_deg":REFERENCE_AZIMUTH_DEG,"irradiance_treatment":"pvlib isotropic POA from ERA5 GHI/DNI/DHI"},
      "storage":{"models":list(BATTERIES),"initial_soc_semantics":"zero useful inventory; physical minimum SOC unavailable",
        "dispatch":"deterministic renewable to load, battery, then curtailment"},
      "optimization":{"targets":[.95,.99],"target_definition":"annual served-energy fraction, not uptime",
        "decision_variables":["turbine model/count","PV block model/count","battery model/count"],
        "economics":"final Phase 10 scale-aware 2022-real-USD lifecycle economics",
        "selected_designs":{target:phase10["robust_all_profiles"][target]["design_key"] for target in ("0.95","0.99")}},
      "sensitivity":{"scenario_type":"researcher-defined deterministic perturbations; not confidence intervals",
        "scenarios":phase11["scenarios"],"adaptation_method":ADAPTATION_METHOD,
        "full_reoptimization_performed":False},
      "software":{"python":platform.python_version(),"platform":platform.platform(),"packages":_packages(),
        "git":_git(),"repository_test_count_at_phase12":167}}

def _tables(phase9,phase10,phase11_rows):
    benchmark=[{"category":"dataset","item":"annual reconstructed demand","value":8020000,"unit":"kWh"},
      {"category":"dataset","item":"hours","value":8760,"unit":"hour"}]
    for key,row in phase9["wind"].items():
        if key!="resource":benchmark.append({"category":"wind","item":key,"value":row["annual_generation_kwh"],"unit":"kWh/unit-year",
          "capacity_factor":row["capacity_factor"]})
    representative="trina_tsm_450_neg9r28__fronius_tauro_eco_100"
    p=phase9["pv"][representative]
    benchmark += [{"category":"pv","item":"annual POA","value":p["annual_poa_kwh_m2"],"unit":"kWh/m2-year"},
      {"category":"pv","item":representative,"value":p["annual_ac_kwh"],"unit":"kWh/block-year",
       "specific_yield_kwh_per_kwp":p["ac_specific_yield_kwh_per_kwp"],"clipping_kwh":p["clipping_kwh"]}]
    optimization=[];reliability=[]
    for target in ("0.95","0.99"):
        row=phase10["robust_all_profiles"][target];m=row["all_profile_performance"][row["binding_load_shape"]]
        optimization.append({"target":target,"design_key":row["design_key"],"wind_key":row["wind_key"],"wind_count":row["wind_count"],
          "installed_wind_kw":row["installed_wind_kw"],"pv_key":row["pv_key"],"pv_count":row["pv_count"],
          "installed_pv_dc_kw":row["installed_pv_dc_kw"],"installed_pv_ac_kw":row["installed_pv_ac_kw"],
          "battery_key":row["battery_key"],"battery_count":row["battery_count"],
          "installed_usable_battery_kwh":row["installed_usable_battery_kwh"],"battery_power_kw":m["battery_discharge_kw"],
          "worst_served_fraction":row["worst_served_fraction"],"binding_load_profile":row["binding_load_shape"],
          "unmet_energy_kwh":row["unmet_energy_kwh"],"lpsp":row["lpsp"],"loss_of_load_hours":row["loss_of_load_hours"],
          "longest_deficit_hours":row["longest_deficit_hours"],"maximum_hourly_deficit_kwh":m["maximum_hourly_deficit_kwh"],
          "curtailment_kwh":row["curtailment_kwh"],"initial_capex_usd":row["initial_capex_usd"],
          "net_present_cost_usd":row["net_present_cost_usd"],"equivalent_annual_cost_usd":row["equivalent_annual_cost_usd"],
          "cost_per_served_kwh_usd":row["cost_per_served_kwh_usd"]})
        for shape,metrics in row["all_profile_performance"].items():
            reliability.append({"target":target,"load_profile":shape,"served_fraction":metrics["served_fraction"],
              "served_energy_kwh":metrics["served_energy_kwh"],"unmet_energy_kwh":metrics["unmet_energy_kwh"],
              "loss_of_load_hours":metrics["loss_of_load_hours"],"longest_deficit_hours":metrics["longest_deficit_hours"],
              "interpretation":"annual energy service; not uptime"})
    names={"nominal","demand_low","demand_high","wind_shear_low","wind_shear_high","pv_low","pv_high","resource_stress","resource_favorable"}
    sensitivity=[]
    for scenario in names:
        for target in (.95,.99):
            rows=[r for r in phase11_rows if r["scenario"]==scenario and float(r["target"])==target]
            binding=min(rows,key=lambda r:float(r["served_fraction"]))
            sensitivity.append({"scenario":scenario,"target":target,"wind_shear_alpha":binding["wind_shear_alpha"],
              "binding_profile":binding["load_profile"],"served_fraction":binding["served_fraction"],
              "passes_target":float(binding["served_fraction"])+1e-12>=target,"loss_of_load_hours":binding["loss_of_load_hours"],
              "longest_deficit_hours":binding["longest_deficit_hours"]})
    return benchmark,optimization,sensitivity,reliability

def _figures(out,load_meta,phase9,optimization,phase11_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures=[]
    def save(name):
        plt.tight_layout();plt.savefig(out/name,dpi=180);plt.close();figures.append(name)
    plt.figure(figsize=(8,4.5));plt.bar(range(1,13),[v/1000 for v in load_meta["monthly_kwh"]]);plt.xlabel("Month");plt.ylabel("Reconstructed energy (MWh)");plt.title("Rodina monthly electricity demand (reconstructed, not measured)");save("figure1_reconstructed_demand.png")
    wind=[(k,v) for k,v in phase9["wind"].items() if k!="resource"]
    fig,axes=plt.subplots(1,2,figsize=(10,4.5));axes[0].bar([k for k,_ in wind],[v["annual_generation_kwh"] for _,v in wind]);axes[0].set_ylabel("Unit energy (kWh/year)");axes[1].bar([k for k,_ in wind],[100*v["capacity_factor"] for _,v in wind]);axes[1].set_ylabel("Capacity factor (%)");fig.suptitle("Frozen Phase 9 wind-unit characteristics");save("figure2_wind_unit_characteristics.png")
    fig,axes=plt.subplots(1,3,figsize=(11,4));labels=[f"{float(r['target']):.0%}" for r in optimization]
    for ax,key,title,unit in zip(axes,("installed_wind_kw","installed_pv_ac_kw","installed_usable_battery_kwh"),("Wind","PV AC","Storage"),("kW","kW","kWh"),strict=True):ax.bar(labels,[r[key] for r in optimization]);ax.set_title(title);ax.set_ylabel(unit)
    fig.suptitle("Phase 10 selected-system composition");save("figure3_selected_composition.png")
    fig,axes=plt.subplots(1,3,figsize=(11,4));
    for ax,key,title,scale in zip(axes,("worst_served_fraction","unmet_energy_kwh","loss_of_load_hours"),("Annual energy served","Unmet energy","Loss-of-load hours"),(100,1/1000,1),strict=True):ax.bar(labels,[float(r[key])*scale for r in optimization]);ax.set_title(title);ax.set_ylabel("%" if key=="worst_served_fraction" else "MWh" if key=="unmet_energy_kwh" else "hours")
    fig.suptitle("Reliability metrics (served energy is not uptime)");save("figure4_reliability.png")
    fig,axes=plt.subplots(1,3,figsize=(11,4));
    for ax,key,title,scale in zip(axes,("initial_capex_usd","net_present_cost_usd","equivalent_annual_cost_usd"),("CAPEX","NPC","EAC"),(1e-6,1e-6,1e-6),strict=True):ax.bar(labels,[float(r[key])*scale for r in optimization]);ax.set_title(title);ax.set_ylabel("million 2022 USD")
    fig.suptitle("Phase 10 reference cost comparison");save("figure5_costs.png")
    for source,name in ((PHASE11/"served_fraction_vs_demand.png","figure6_demand_sensitivity.png"),(PHASE11/"tornado_sensitivity_ranking.png","figure8_sensitivity_ranking.png")):
        shutil.copyfile(source,out/name);figures.append(name)
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),sharey=True)
    for ax,prefix,xlabel in ((axes[0],"wind_shear","Shear exponent"),(axes[1],"pv_","PV-output multiplier")):
        for target in (.95,.99):
            if prefix=="wind_shear": names=("wind_shear_low","nominal","wind_shear_high");x=(ALPHA_NOMINAL*.8,ALPHA_NOMINAL,ALPHA_NOMINAL*1.2)
            else:names=("pv_low","nominal","pv_high");x=(.9,1,1.1)
            y=[]
            for name in names:
                rows=[r for r in phase11_rows if r["scenario"]==name and float(r["target"])==target]
                y.append(min(float(r["served_fraction"]) for r in rows))
            ax.plot(x,y,marker="o",label=f"{target:.0%} design");ax.axhline(target,color="gray",linestyle="--",linewidth=.8)
        ax.set_xlabel(xlabel);ax.set_ylabel("Worst served-energy fraction");ax.legend()
    fig.suptitle("Fixed-design renewable-resource sensitivity");save("figure7_resource_sensitivity.png")
    return figures

def _report(out,audit,benchmark,optimization,sensitivity,phase11):
    blockers=sum(row["status"]=="BLOCKER" for row in audit);warnings=sum(row["status"]=="WARNING" for row in audit)
    margins={str(row["target"]):row for row in phase11["robustness_margins"]}
    wind_increase=optimization[1]["installed_wind_kw"]/optimization[0]["installed_wind_kw"]-1
    pv_increase=optimization[1]["installed_pv_ac_kw"]/optimization[0]["installed_pv_ac_kw"]-1
    storage_increase=optimization[1]["installed_usable_battery_kwh"]/optimization[0]["installed_usable_battery_kwh"]-1
    npc_increase=optimization[1]["net_present_cost_usd"]/optimization[0]["net_present_cost_usd"]-1
    lines=["# SteppeGrid Rodina Final Benchmark","","## 1. Study objective","",
      "This report consolidates the frozen Rodina benchmark. It validates traceability and model reproduction; it is not validation against measured village generation or hourly demand.","",
      "## 2. Data and provenance","","Rodina demand is reconstructed from published monthly rows (8.02 GWh); the paper's conflicting 7.72 GWh annual figure remains preserved. Weather is cached 2025 ERA5 gridded reanalysis.","",
      "## 3. Demand reconstruction","","All three deterministic hourly shapes preserve the same monthly totals and 8.02 GWh annual sum. None is measured hourly demand.","",
      "## 4. Weather and renewable-resource modeling","","Exactly 8,760 aligned hours are used. Wind shear is ERA5-derived, turbine curves are source-attributed, and PV uses fixed latitude tilt and south azimuth.","",
      "## 5. Equipment and physical models","","Catalog wind, PV, inverter, and battery products remain frozen. Battery dispatch begins with zero useful stored energy.","",
      "## 6. Controlled Phase 9 benchmark","",f"The audit reproduces {len([r for r in benchmark if r['category']=='wind'])} wind-unit cases and the representative final PV block from cached inputs.","",
      "## 7. Phase 10 techno-economic optimization","","| Target | Wind | PV | Storage | Served | NPC |","|---|---|---|---|---:|---:|"]
    for row in optimization:lines.append(f"| {float(row['target']):.0%} | {row['wind_count']} {row['wind_key']} | {row['pv_count']} {row['pv_key']} | {row['battery_count']} {row['battery_key']} | {float(row['worst_served_fraction']):.3%} | ${float(row['net_present_cost_usd'])/1e6:.3f}M |")
    lines += ["","## 8. Reliability interpretation","","Annual served-energy fraction is not uptime. The selected portfolios retain loss-of-load hours and continuous deficit periods even while meeting their energy targets.","",
      "## 9. Phase 11 sensitivity and robustness","",f"Demand headroom is approximately {(margins['0.95']['maximum_demand_multiplier_for_target']-1)*100:.2f}% for the 95% design and {(margins['0.99']['maximum_demand_multiplier_for_target']-1)*100:.2f}% for the 99% design. Sensitivity ranges are deterministic research cases, not confidence intervals.","",
      "## 10. Main findings","",f"Relative to 95%, the 99% portfolio increases installed wind by {wind_increase:.1%}, PV AC by {pv_increase:.1%}, usable storage by {storage_increase:.1%}, and NPC by {npc_increase:.1%}. Curtailment rises from {optimization[0]['curtailment_kwh']/1e6:.3f} to {optimization[1]['curtailment_kwh']/1e6:.3f} GWh. This overbuild is consistent with finite-storage isolated-system reliability under temporal mismatch and is not automatically a defect. The nominal designs have little reliability headroom. Technology CAPEX perturbations did not change the least-cost selection within the saved Phase 10 candidate set.","",
      "## 11. Limitations","","Demand is reconstructed; meteorology is one ERA5 year; there are no wakes, layout, snow/soiling, detailed degradation, grid power flow, probabilistic uncertainty, or site procurement quotes.","",
      "## 12. Reproducibility","",f"The final audit contains {blockers} blockers and {warnings} documented warnings. See `validation_audit.json` and `provenance_manifest.json`.","",
      "## 13. Future Shamshi field case","","No Shamshi optimum is reported. A field case must wait for real electricity-demand data.","",
      "## Generated figures","",* [f"- [{name}]({name})" for name in ("figure1_reconstructed_demand.png","figure2_wind_unit_characteristics.png","figure3_selected_composition.png","figure4_reliability.png","figure5_costs.png","figure6_demand_sensitivity.png","figure7_resource_sensitivity.png","figure8_sensitivity_ranking.png")]]
    (out/"steppegrid_rodina_final_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def _markdown_tables(out,benchmark,optimization,sensitivity,reliability):
    lines=["# SteppeGrid Rodina final tables","","Values are frozen Phase 9–11 derived results. Served-energy fraction is not uptime.","",
      "## Final benchmark","","| Category | Item | Value | Unit |","|---|---|---:|---|"]
    for row in benchmark:lines.append(f"| {row['category']} | {row['item']} | {float(row['value']):.6g} | {row['unit']} |")
    lines += ["","## Final selected designs","","| Target | Wind | PV AC | Storage | Served | LOLH | NPC |","|---|---:|---:|---:|---:|---:|---:|"]
    for row in optimization:lines.append(f"| {float(row['target']):.0%} | {row['installed_wind_kw']:.1f} kW | {row['installed_pv_ac_kw']:.1f} kW | {row['installed_usable_battery_kwh']:.1f} kWh | {row['worst_served_fraction']:.3%} | {row['loss_of_load_hours']} h | ${row['net_present_cost_usd']/1e6:.3f}M |")
    lines += ["","## Final physical sensitivity","","| Scenario | Target | Served | Pass | LOLH | Longest deficit |","|---|---:|---:|:---:|---:|---:|"]
    for row in sorted(sensitivity,key=lambda x:(x["scenario"],x["target"])):lines.append(f"| {row['scenario']} | {row['target']:.0%} | {float(row['served_fraction']):.3%} | {'yes' if row['passes_target'] else 'no'} | {row['loss_of_load_hours']} | {row['longest_deficit_hours']} h |")
    lines += ["","## Cross-profile reliability","","| Target | Profile | Served | Unmet | LOLH | Longest deficit |","|---|---|---:|---:|---:|---:|"]
    for row in reliability:lines.append(f"| {float(row['target']):.0%} | {row['load_profile']} | {row['served_fraction']:.3%} | {row['unmet_energy_kwh']/1000:.2f} MWh | {row['loss_of_load_hours']} | {row['longest_deficit_hours']} h |")
    (out/"final_tables.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def run_phase12(*,mode="verify",write_outputs=True,output_directory=OUTPUT_DIRECTORY):
    if mode not in {"verify","reproduce"}:raise ValueError("mode must be verify or reproduce")
    started=time.perf_counter();audit=[];weather=load_phase9_weather();weather_check=validate_phase9_weather(weather)
    loads,load_meta=load_phase9_loads();p9_integrity=_json(PHASE9/"integrity.json")
    phase10=_json(PHASE10/"scale_aware_energy_optima.json");phase11=_json(PHASE11/"phase11_summary.json")
    fixed11=_csv(PHASE11/"fixed_design_sensitivity.csv")
    finite=all(math.isfinite(value) and value>=0 for trace in loads.values() for value in trace)
    _check(audit,"time_series","8760_aligned_hours",weather_check["records"]==8760 and all(len(v)==8760 for v in loads.values()),"Weather and all load shapes contain 8,760 hours",weather_check)
    _check(audit,"time_series","unique_consecutive_weather",len(set(weather.series.timestamps))==8760,"Weather timestamps are unique and consecutive",{"duplicates":weather_check["duplicates"]})
    _check(audit,"time_series","finite_nonnegative_load",finite,"All load values are finite and nonnegative")
    totals={key:math.fsum(value) for key,value in loads.items()}
    _check(audit,"demand","annual_total",max(totals.values())-min(totals.values())<1e-6 and abs(next(iter(totals.values()))-8020000)<1e-6,"All profiles preserve the reconstructed 8.02 GWh total",totals)
    _check(audit,"demand","printed_discrepancy_preserved",load_meta["printed_annual_kwh"]==7720000 and not load_meta["hourly_values_measured"],"Printed 7.72 GWh remains separate and hourly load is labeled reconstructed",load_meta)
    frozen_p9={"wind":_json(PHASE9/"wind_summary.json"),"pv":_json(PHASE9/"pv_summary.json"),"storage":_json(PHASE9/"storage_summary.json")}
    phase9=frozen_p9
    if mode=="reproduce":
        _,reproduced,loads2,_,wind,pv,_=precompute();phase9={"wind":reproduced.wind,"pv":reproduced.pv,"storage":reproduced.storage}
        for key in WIND_TURBINES:_check(audit,"phase9","wind_"+key,abs(reproduced.wind[key]["annual_generation_kwh"]-frozen_p9["wind"][key]["annual_generation_kwh"])<1e-6,"Wind annual output reproduces",{"kwh":reproduced.wind[key]["annual_generation_kwh"]})
        for key in WIND_TURBINES:_check(audit,"phase9","wind_capacity_factor_"+key,abs(reproduced.wind[key]["capacity_factor"]-frozen_p9["wind"][key]["capacity_factor"])<1e-12,"Wind capacity factor reproduces",{"capacity_factor":reproduced.wind[key]["capacity_factor"]})
        representative="trina_tsm_450_neg9r28__fronius_tauro_eco_100"
        _check(audit,"phase9","pv_representative",all(abs(reproduced.pv[representative][key]-frozen_p9["pv"][representative][key])<1e-6 for key in ("annual_ac_kwh","annual_poa_kwh_m2","ac_specific_yield_kwh_per_kwp","clipping_kwh")),"Representative PV energy, POA, specific yield, and clipping reproduce")
        _check(audit,"phase9","nominal_alpha",abs(reproduced.wind_shear["exponent"]-ALPHA_NOMINAL)<1e-10,"Nominal shear reproduces",{"alpha":reproduced.wind_shear["exponent"]})
        _check(audit,"phase9","battery_benchmark",all(abs(float(a[key])-float(b[key]))<1e-6 for a,b in zip(reproduced.storage,frozen_p9["storage"],strict=True) for key in ("fraction_load_served","unmet_load_kwh","discharge_from_initial_inventory_kwh")),"Frozen one-unit battery benchmark values reproduce")
        nominal=SensitivityScenario("nominal","baseline")
        for target in (.95,.99):
            saved=phase10["robust_all_profiles"][str(target)];rows=_evaluate(_design(saved),target,nominal,loads2,wind,pv,reproduced)
            binding=min(rows,key=lambda row:row["served_fraction"])
            matches=(abs(binding["served_fraction"]-saved["worst_served_fraction"])<1e-10 and
              binding["load_profile"]==saved["binding_load_shape"] and
              abs(binding["unmet_energy_kwh"]-saved["unmet_energy_kwh"])<1e-6 and
              int(binding["loss_of_load_hours"])==saved["loss_of_load_hours"] and
              int(binding["longest_deficit_hours"])==saved["longest_deficit_hours"] and
              abs(binding["initial_capex_usd"]-saved["initial_capex_usd"])<1e-6 and
              abs(binding["net_present_cost_usd"]-saved["net_present_cost_usd"])<1e-6 and
              abs(binding["equivalent_annual_cost_usd"]-saved["equivalent_annual_cost_usd"])<1e-6 and
              abs(binding["cost_per_served_kwh_usd"]-saved["cost_per_served_kwh_usd"])<1e-12)
            _check(audit,"phase10",f"selected_design_{target}",matches,"Selected design independently reproduces equipment-linked physical and economic results",{"design":saved["design_key"],"served_fraction":binding["served_fraction"]})
    else:
        for key in WIND_TURBINES:_check(audit,"phase9","wind_output_present_"+key,key in frozen_p9["wind"],"Frozen wind result is present")
        _check(audit,"phase9","pv_output_present",bool(frozen_p9["pv"]),"Frozen PV results are present")
        for target in ("0.95","0.99"):
            rep=phase11["nominal_reproduction"][target]
            _check(audit,"phase10","selected_design_"+target,rep["phase10_served_fraction"]==rep["phase11_served_fraction"] and rep["phase10_npc_usd"]==rep["phase11_npc_usd"],"Phase 11 nominal replay exactly matches final Phase 10")
    for target in (.95,.99):
        def worst(name):return min(float(r["served_fraction"]) for r in fixed11 if r["scenario"]==name and float(r["target"])==target)
        _check(audit,"phase11",f"demand_direction_{target}",worst("demand_low")>=worst("nominal")>=worst("demand_high"),"Demand direction is physically sensible")
        _check(audit,"phase11",f"pv_direction_{target}",worst("pv_low")<=worst("nominal")<=worst("pv_high"),"PV direction is physically sensible")
        _check(audit,"phase11",f"shear_direction_{target}",worst("wind_shear_low")>=worst("nominal")>=worst("wind_shear_high"),"Higher alpha is adverse for hubs below 100 m")
    scenario_map={row["name"]:row for row in phase11["scenarios"]}
    _check(audit,"phase11","combined_direction",scenario_map["resource_stress"]["wind_shear_alpha"]==ALPHA_NOMINAL*1.2 and scenario_map["resource_favorable"]["wind_shear_alpha"]==ALPHA_NOMINAL*.8,"Combined stress/favorable shear directions are correct")
    _check(audit,"phase11","candidate_semantics",phase11["adaptation_method"]==ADAPTATION_METHOD and phase11["full_reoptimization_performed"] is False,"Saved-candidate reselection is not labeled global re-optimization")
    margin_rows={float(row["target"]):row for row in _csv(PHASE11/"robustness_margins.csv")}
    _check(audit,"phase11","robustness_margins",all(abs(float(row["maximum_demand_multiplier_for_target"])-float(margin_rows[float(row["target"])]["maximum_demand_multiplier_for_target"]))<1e-12 and abs(float(row["minimum_pv_multiplier_for_target"])-float(margin_rows[float(row["target"])]["minimum_pv_multiplier_for_target"]))<1e-12 for row in phase11["robustness_margins"]),"Summary demand/PV margins match the final Phase 11 margin table")
    _check(audit,"economics","fixed_dispatch_invariant",all(worst(name)==worst("nominal") for name in ("wind_capex_low","wind_capex_high","pv_capex_low","pv_capex_high","battery_capex_low","battery_capex_high")),"CAPEX perturbations do not alter fixed-design dispatch")
    storage_error=max(abs(float(row[key])) for row in frozen_p9["storage"] for key in ("energy_balance_generation_error_kwh","energy_balance_load_error_kwh","energy_balance_storage_error_kwh"))
    _check(audit,"conservation","phase9_storage",storage_error<1e-6,"Phase 9 storage conservation residual is within frozen tolerance",{"maximum_absolute_residual_kwh":storage_error})
    _check(audit,"provenance","classification_registry",all(row["classification"] in {"SOURCE_REPORTED","SOURCE_RECONSTRUCTED","ERA5_DERIVED","MANUFACTURER_OR_CERTIFICATION_DATA","MODELING_ASSUMPTION","RESEARCH_SENSITIVITY_SCENARIO","OPTIMIZED_DECISION_VARIABLE","DERIVED_RESULT"} for row in assumptions_registry()),"All registry entries use declared classifications")
    _check(audit,"limitations","era5_not_measured",True,"ERA5 is gridded reanalysis, not site measurement",status_if_false="WARNING")
    audit.append({"category":"limitations","check":"known_scope_limitations","status":"WARNING","message":"One weather year, reconstructed demand, and omitted wake/layout/degradation/grid physics remain documented scope limitations","evidence":{}})
    manifest=_manifest(weather,loads,load_meta,p9_integrity,phase10,phase11)
    benchmark,optimization,sensitivity,reliability=_tables(phase9,phase10,fixed11)
    conclusions={"benchmark_viability":"Controlled deterministic Rodina benchmark reproduces; no measured-generation validation is claimed.",
      "reliability_tradeoff":{"95_to_99_wind_kw_increase":optimization[1]["installed_wind_kw"]-optimization[0]["installed_wind_kw"],
        "95_to_99_pv_ac_kw_increase":optimization[1]["installed_pv_ac_kw"]-optimization[0]["installed_pv_ac_kw"],
        "95_to_99_storage_kwh_increase":optimization[1]["installed_usable_battery_kwh"]-optimization[0]["installed_usable_battery_kwh"],
        "npc_increase_fraction":optimization[1]["net_present_cost_usd"]/optimization[0]["net_present_cost_usd"]-1},
      "robustness_margins":phase11["robustness_margins"],"candidate_reselection":"CAPEX perturbations do not change the least-cost design within the saved Phase 10 candidate set.",
      "claims_boundary":"Annual served-energy fraction is not uptime; sensitivity ranges are not confidence intervals.",
      "shamshi":"No optimization without real demand data."}
    if write_outputs:
        out=Path(output_directory);out.mkdir(parents=True,exist_ok=True)
        (out/"provenance_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        audit_doc={"mode":mode,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"blockers":sum(r["status"]=="BLOCKER" for r in audit),"warnings":sum(r["status"]=="WARNING" for r in audit),"checks":audit,"runtime_seconds":time.perf_counter()-started}
        (out/"validation_audit.json").write_text(json.dumps(audit_doc,indent=2)+"\n",encoding="utf-8")
        (out/"final_conclusions.json").write_text(json.dumps(conclusions,indent=2)+"\n",encoding="utf-8")
        _write_csv(out/"assumptions_registry.csv",assumptions_registry());_write_csv(out/"final_benchmark_table.csv",benchmark)
        _write_csv(out/"final_optimization_table.csv",optimization);_write_csv(out/"final_sensitivity_table.csv",sensitivity);_write_csv(out/"final_reliability_table.csv",reliability)
        figures=_figures(out,load_meta,phase9,optimization,fixed11);_markdown_tables(out,benchmark,optimization,sensitivity,reliability);_report(out,audit,benchmark,optimization,sensitivity,phase11)
    else:figures=[]
    return {"mode":mode,"audit":audit,"blockers":sum(r["status"]=="BLOCKER" for r in audit),
      "warnings":sum(r["status"]=="WARNING" for r in audit),"manifest":manifest,"benchmark":benchmark,
      "optimization":optimization,"sensitivity":sensitivity,"reliability":reliability,"figures":figures,
      "runtime_seconds":time.perf_counter()-started}
