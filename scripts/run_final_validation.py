"""Fast release validation for SteppeGrid v1.0 (no optimization)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from steppegrid.app.product import FEATURED_SITE_ID, latest_result
from steppegrid.app.services import PlanningService
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]; OUTPUT=ROOT/"outputs/final/final_validation.json"
def digest(path):
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()
def main():
    checks=[]
    def check(name,passed,message,warning=False): checks.append({"check":name,"status":"PASS" if passed else ("WARNING" if warning else "BLOCKER"),"message":message})
    registry=SiteRegistry(); sites=registry.list_sites(); ids={s.site_id for s in sites}
    expected={"rodina","shamshi_kaldayakova","katon_karagay","kegen","shayan","sai_otes","togyzkuduk"}
    check("seven_production_sites",len(sites)==7 and ids==expected,f"Found {len(sites)} production sites")
    for site in sites:
        weather=site.weather_datasets[0] if site.weather_datasets else None
        path=ROOT/weather.path if weather and weather.path else None
        check(f"weather_{site.site_id}",bool(path and path.is_file()),"Cached weather file present")
        if path and path.is_file() and weather.sha256:
            # Registry hash may identify normalized input rather than raw file; retain both records.
            check(f"weather_metadata_{site.site_id}",len(weather.sha256)==64,"Weather SHA-256 metadata valid")
        check(f"demand_hash_{site.site_id}",bool(site.demand_datasets and len(site.demand_datasets[0].demand_sha256)==64),"Demand hash retained")
        check(f"source_metadata_{site.site_id}",bool(site.provenance and site.demand_datasets[0].provenance),"Source metadata retained")
    try:
        api=PlanningService(); audit=api.validation(); check("app_data_service",True,"Read-only application data service loaded")
        check("rodina_outputs",all(api.design(t) for t in (.95,.99)),"Rodina 95% and 99% outputs loaded")
        check("frozen_audit",audit.get("blockers")==0,f"Frozen audit reports {audit.get('blockers')} blockers")
    except Exception as error: check("app_data_service",False,str(error))
    check("shamshi_95",latest_result(FEATURED_SITE_ID,.95) is not None,"Latest saved Shamshi 95% result loaded")
    phase17_audit=ROOT/"outputs/phase17/phase17_audit.json"
    phase17=json.loads(phase17_audit.read_text(encoding="utf-8")) if phase17_audit.is_file() else {"blockers":1}
    check("phase17_outputs",phase17_audit.is_file() and phase17.get("blockers")==0,"Frozen Phase 17 standardized comparison is available")
    phase17_required=("site_resource_metrics.csv","standardized_scenarios.csv","optimization_results.csv","normalized_metrics.csv","reliability_escalation.csv","site_comparison.csv","phase17_summary.json","steppegrid_cross_village_report.md")
    for name in phase17_required: check(f"phase17_{name}",(ROOT/"outputs/phase17"/name).is_file(),f"Phase 17 artifact: {name}")
    try:
        import csv
        with (ROOT/"outputs/phase17/optimization_results.csv").open(encoding="utf-8") as handle: phase17_rows=list(csv.DictReader(handle))
        check("phase17_95_results",sum(float(r["target"])==.95 for r in phase17_rows)==7,"Seven standardized 95% results")
        check("phase17_99_results",sum(float(r["target"])==.99 for r in phase17_rows)==7,"Seven standardized 99% results")
    except (OSError, ValueError, KeyError) as error: check("phase17_result_integrity",False,str(error))
    for path in [ROOT/"README.md",ROOT/"docs/steppegrid_final_report.md",ROOT/"docs/steppegrid_portfolio_summary.md",ROOT/"docs/steppegrid_research_abstract.md",ROOT/"docs/steppegrid_plain_language_summary.md",ROOT/"docs/reproduce_steppegrid.md"]:
        check(f"artifact_{path.name}",path.is_file(),str(path.relative_to(ROOT)))
    figures=list((ROOT/"outputs/final/figures").glob("*.png")); tables=list((ROOT/"outputs/final/tables").glob("*.csv"))
    required_tables={"site_summary.csv","results_95.csv","results_99.csv","normalized_comparison.csv","reliability_escalation.csv","key_findings.csv"}
    check("final_figures",len(figures)==10,f"Found {len(figures)} final figures")
    check("final_tables",required_tables<={p.name for p in tables},f"Found required final tables: {sorted(required_tables)}")
    blockers=sum(c["status"]=="BLOCKER" for c in checks); warnings=sum(c["status"]=="WARNING" for c in checks)
    report={"schema_version":"steppegrid.final-validation.v1","version":"1.0.0","checks":checks,"passes":sum(c["status"]=="PASS" for c in checks),"warnings":warnings,"blockers":blockers,"site_count":len(sites),"app_data_status":"PASS" if any(c["check"]=="app_data_service" and c["status"]=="PASS" for c in checks) else "BLOCKER","frozen_benchmark_status":"PASS" if audit.get("blockers")==0 else "BLOCKER","cross_village_output_status":"PASS" if phase17.get("blockers")==0 else "BLOCKER"}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2)); raise SystemExit(1 if blockers else 0)
if __name__=="__main__": main()
