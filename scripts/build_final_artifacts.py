"""Build public v1.0 tables and figures from registered data and saved results."""
from __future__ import annotations
import csv
from pathlib import Path
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

def main():
    TABLES.mkdir(parents=True,exist_ok=True); FIGURES.mkdir(parents=True,exist_ok=True)
    registry=SiteRegistry(); sites=registry.list_sites(); overview=site_rows(registry)
    write_csv("village_overview.csv",[{k:v for k,v in row.items() if k not in {"site_id","lat","lon","featured_site"}} for row in overview])
    api=PlanningService(); designs=[api.design(.95),api.design(.99)]
    phase17=list(csv.DictReader((ROOT/"outputs/phase17/optimization_results.csv").open(encoding="utf-8")))
    write_csv("system_results_95.csv",[r for r in phase17 if float(r["target"])==.95]); write_csv("system_results_99.csv",[r for r in phase17 if float(r["target"])==.99])
    write_csv("economics.csv",[{k:r[k] for k in ("site","target","capex_usd","npc_usd","eac_usd","cost_per_served_kwh_usd")} for r in phase17])
    write_csv("reliability.csv",[{k:r[k] for k in ("site","target","served_fraction","unmet_energy_kwh","loss_of_load_hours","longest_deficit_hours")} for r in phase17])
    normalized=[]
    for site in sites:
        result=latest_result(site.site_id,.95)
        if not result: continue
        demand=site.demand_datasets[0].annual_energy_kwh
        normalized.append({"site":site.name,"target":.95,"npc_per_annual_kwh":result["economics"]["net_present_cost_usd"]/demand,"wind_kw_per_annual_mwh":result["design"]["wind_capacity_kw"]/(demand/1000),"pv_kwac_per_annual_mwh":result["design"]["pv_ac_capacity_kw"]/(demand/1000),"storage_kwh_per_annual_mwh":result["design"]["battery_usable_capacity_kwh"]/(demand/1000)})
    write_csv("normalized_comparisons.csv",normalized)
    names=[s.name for s in sites]; demands=[s.demand_datasets[0].annual_energy_kwh/1e6 for s in sites]
    save_bar("01_kazakhstan_village_demand.png","Seven Kazakhstan villages",names,demands,"Annual demand (GWh/year)","Shamshi Kaldayakova")
    wind=[weather_summary(s)["mean_wind_100m_m_s"] for s in sites]; solar=[weather_summary(s)["annual_solar_kwh_m2"] for s in sites]
    save_bar("02_cross_village_wind_resource.png","Modeled wind resource",names,wind,"Mean cached wind speed (m/s)","Shamshi Kaldayakova")
    save_bar("03_cross_village_solar_resource.png","Modeled solar resource",names,solar,"Annual irradiation (kWh/m²)","Shamshi Kaldayakova")
    save_bar("04_rodina_system_composition.png","Rodina selected capacity",["95% wind","95% PV AC","99% wind","99% PV AC"],[designs[0]["installed_wind_kw"],designs[0]["installed_pv_ac_kw"],designs[1]["installed_wind_kw"],designs[1]["installed_pv_ac_kw"]],"Capacity (kW)")
    save_bar("05_rodina_npc.png","Rodina reliability–cost tradeoff",["95%","99%"],[r["net_present_cost_usd"]/1e6 for r in designs],"NPC (million USD)")
    save_bar("06_rodina_reliability.png","Rodina annual energy served",["95% design","99% design"],[100*r["worst_served_fraction"] for r in designs],"Annual energy served (%)")
    shamshi=latest_result(FEATURED_SITE_ID,.95); d=shamshi["design"]
    save_bar("07_shamshi_system.png","MY VILLAGE — Shamshi selected system",["Wind kW","PV AC kW","Storage kWh"],[d["wind_capacity_kw"],d["pv_ac_capacity_kw"],d["battery_usable_capacity_kwh"]],"Selected capacity",featured="Wind kW")
    p=shamshi["metrics"]; save_bar("08_shamshi_energy_balance.png","Shamshi annual energy balance",["Served","Unmet","Curtailment"],[p["served_energy_kwh"]/1000,p["unmet_energy_kwh"]/1000,p["curtailment_kwh"]/1000],"Energy (MWh)")
    save_bar("09_95_to_99_cost_escalation.png","Cost escalation from 95% to 99%",["NPC increase"],[100*(designs[1]["net_present_cost_usd"]/designs[0]["net_present_cost_usd"]-1)],"Increase (%)")
    print(f"Wrote {len(list(FIGURES.glob('*.png')))} figures and {len(list(TABLES.glob('*.csv')))} tables")
if __name__=="__main__": main()
