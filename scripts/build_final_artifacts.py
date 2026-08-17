"""Build public v1.0 tables and figures from registered data and saved results."""
from __future__ import annotations
import csv
from pathlib import Path
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from steppegrid.app.product import FEATURED_SITE_ID, latest_result, site_rows, weather_summary
from steppegrid.app.services import PlanningService
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]; TABLES=ROOT/"outputs/final/tables"; FIGURES=ROOT/"outputs/final/figures"

def write_csv(name, rows):
    path=TABLES/name; rows=list(rows); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]) if rows else ["status"]); writer.writeheader(); writer.writerows(rows or [{"status":"No saved comparable results"}])

def save_bar(name,title,labels,values,ylabel,featured=None):
    colors=["#2878D8" if label==featured else "#1F6B5B" for label in labels]
    fig,ax=plt.subplots(figsize=(10,5.5)); ax.bar(labels,values,color=colors); ax.set_title(title,loc="left",weight="bold"); ax.set_ylabel(ylabel); ax.spines[["top","right"]].set_visible(False); ax.tick_params(axis="x",rotation=25); fig.tight_layout(); fig.savefig(FIGURES/name,dpi=180); plt.close(fig)

def save_map(sites):
    fig,ax=plt.subplots(figsize=(10,5.5))
    for site in sites:
        color="#2878D8" if site.site_id==FEATURED_SITE_ID else "#1F6B5B"
        ax.scatter(site.longitude,site.latitude,s=90,color=color)
        ax.annotate(("MY VILLAGE — " if site.site_id==FEATURED_SITE_ID else "")+site.name,(site.longitude,site.latitude),xytext=(5,5),textcoords="offset points",fontsize=8)
    ax.set(title="SteppeGrid Kazakhstan sites",xlabel="Longitude",ylabel="Latitude"); ax.spines[["top","right"]].set_visible(False); fig.tight_layout(); fig.savefig(FIGURES/"01_kazakhstan_sites_map.png",dpi=180); plt.close(fig)

def save_workflow():
    labels=["Weather + demand","Wind + solar","Battery dispatch","Reliability","Optimization","Economics"]
    fig,ax=plt.subplots(figsize=(12,2.8)); ax.axis("off")
    for i,label in enumerate(labels):
        ax.text(i,0,label,ha="center",va="center",bbox={"boxstyle":"round,pad=.5","facecolor":"#EDF2EE","edgecolor":"#1F6B5B"})
        if i<len(labels)-1: ax.annotate("",xy=(i+.72,0),xytext=(i+.28,0),arrowprops={"arrowstyle":"->","color":"#1F6B5B"})
    ax.set_xlim(-.7,len(labels)-.3); ax.set_ylim(-1,1); fig.tight_layout(); fig.savefig(FIGURES/"02_steppegrid_workflow.png",dpi=180); plt.close(fig)

def save_shamshi_dispatch():
    path=ROOT/"outputs/phase17/standardized_runs/shamshi_kaldayakova/95/dispatch.csv"
    rows=list(csv.DictReader(path.open(encoding="utf-8")))[:168]; x=range(len(rows))
    fig,ax=plt.subplots(figsize=(11,5.5)); ax.plot(x,[float(r["demand_kwh"]) for r in rows],label="Demand",color="#17211D"); ax.plot(x,[float(r["wind_generation_kwh"])+float(r["pv_generation_kwh"]) for r in rows],label="Renewables",color="#2878D8"); ax.set(title="MY VILLAGE — Shamshi first-week dispatch",xlabel="Hour",ylabel="Energy (kWh)"); ax.legend(); ax.spines[["top","right"]].set_visible(False); fig.tight_layout(); fig.savefig(FIGURES/"10_shamshi_dispatch.png",dpi=180); plt.close(fig)

def main():
    TABLES.mkdir(parents=True,exist_ok=True); FIGURES.mkdir(parents=True,exist_ok=True)
    registry=SiteRegistry(); sites=registry.list_sites(); overview=site_rows(registry)
    public_sites=[{k:v for k,v in row.items() if k not in {"site_id","lat","lon","featured_site"}} for row in overview]
    write_csv("site_summary.csv",public_sites)
    api=PlanningService(); designs=[api.design(.95),api.design(.99)]
    phase17=list(csv.DictReader((ROOT/"outputs/phase17/optimization_results.csv").open(encoding="utf-8")))
    write_csv("results_95.csv",[r for r in phase17 if float(r["target"])==.95]); write_csv("results_99.csv",[r for r in phase17 if float(r["target"])==.99])
    write_csv("economics.csv",[{k:r[k] for k in ("site","target","capex_usd","npc_usd","eac_usd","cost_per_served_kwh_usd")} for r in phase17])
    write_csv("reliability.csv",[{k:r[k] for k in ("site","target","served_fraction","unmet_energy_kwh","loss_of_load_hours","longest_deficit_hours")} for r in phase17])
    normalized=[]
    for site in sites:
        result=latest_result(site.site_id,.95)
        if not result: continue
        demand=site.demand_datasets[0].annual_energy_kwh
        normalized.append({"site":site.name,"target":.95,"npc_per_annual_kwh":result["economics"]["net_present_cost_usd"]/demand,"wind_kw_per_annual_mwh":result["design"]["wind_capacity_kw"]/(demand/1000),"pv_kwac_per_annual_mwh":result["design"]["pv_ac_capacity_kw"]/(demand/1000),"storage_kwh_per_annual_mwh":result["design"]["battery_usable_capacity_kwh"]/(demand/1000)})
    write_csv("normalized_comparison.csv",normalized)
    escalation=list(csv.DictReader((ROOT/"outputs/phase17/reliability_escalation.csv").open(encoding="utf-8")))
    write_csv("reliability_escalation.csv",escalation)
    resources=list(csv.DictReader((ROOT/"outputs/phase17/site_resource_metrics.csv").open(encoding="utf-8")))
    proxy_res=[r for r in resources if r["cohort"]=="primary_proxy"]; proxy_norm=[r for r in normalized if r["site"] in {x["site"] for x in proxy_res}]
    findings=[
        {"metric":"Highest modeled solar yield","site":max(proxy_res,key=lambda r:float(r["pv_specific_yield_kwh_per_kwp"]))["site"]},
        {"metric":"Highest representative wind capacity factor","site":max(proxy_res,key=lambda r:float(r["wind_capacity_factor"]))["site"]},
        {"metric":"Lowest normalized 95% NPC","site":min(proxy_norm,key=lambda r:float(r["npc_per_annual_kwh"]))["site"]},
        {"metric":"Largest 95% to 99% NPC increase","site":max([r for r in escalation if r["site"] in {x["site"] for x in proxy_res}],key=lambda r:float(r["delta_NPC_percent"]))["site"]},
    ]
    write_csv("key_findings.csv",findings)
    save_map(sites); save_workflow()
    save_bar("03_rodina_95_vs_99.png","Rodina Benchmark 95% vs 99%",["95% NPC","99% NPC"],[r["net_present_cost_usd"]/1e6 for r in designs],"NPC (million USD)")
    copies={"01_pv_yield.png":"04_cross_site_solar_resource.png","02_wind_cf.png":"05_cross_site_wind_resource.png","03_wind_intensity_95.png":"06_normalized_95_system_composition.png","06_normalized_npc.png":"07_normalized_npc.png","08_npc_escalation.png":"08_cost_escalation.png"}
    for source,destination in copies.items(): shutil.copyfile(ROOT/"outputs/phase17/figures"/source,FIGURES/destination)
    shamshi=latest_result(FEATURED_SITE_ID,.95); d=shamshi["design"]
    save_bar("09_shamshi_system.png","MY VILLAGE — Shamshi selected system",["Wind kW","PV AC kW","Storage kWh"],[d["wind_capacity_kw"],d["pv_ac_capacity_kw"],d["battery_usable_capacity_kwh"]],"Selected capacity",featured="Wind kW")
    save_shamshi_dispatch()
    print(f"Wrote {len(list(FIGURES.glob('*.png')))} figures and {len(list(TABLES.glob('*.csv')))} tables")
if __name__=="__main__": main()
