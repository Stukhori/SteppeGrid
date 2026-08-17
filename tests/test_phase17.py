from __future__ import annotations
import csv, json, math
from pathlib import Path
import pytest
from scripts.run_phase17 import COMPARATIVE_WIND_KEYS, PROXY_IDS, SITE_IDS, TARGETS, scenario
from steppegrid.sites import SiteRegistry

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"outputs/phase17"
def rows(name):
    with (OUT/name).open(encoding="utf-8") as h: return list(csv.DictReader(h))
def test_standardized_scenarios_are_complete_and_isolated():
    data=rows("standardized_scenarios.csv"); assert len(data)==14
    assert {(r["site_id"],float(r["target"])) for r in data}==set((s,t) for s in SITE_IDS for t in TARGETS)
    assert len({r["scenario_hash"] for r in data})==14
    assert all(r["catalog"]=="PLANNER_V2" and r["economics"]=="PLANNER_SCALE_AWARE_ECONOMICS_V2" for r in data)
def test_provenance_cohorts_remain_distinct():
    registry=SiteRegistry(); assert len(PROXY_IDS)==5
    assert all(registry.get_site(s).demand_datasets[0].classification.value=="PROXY_DERIVED" for s in PROXY_IDS)
    assert registry.get_site("rodina").demand_datasets[0].classification.value=="SOURCE_RECONSTRUCTED"
    assert registry.get_site("shamshi_kaldayakova").demand_datasets[0].classification.value=="SYNTHETIC_ESTIMATE"
def test_common_resource_configuration_and_ranges():
    data=rows("site_resource_metrics.csv"); assert len(data)==7
    assert len({r["representative_wind_key"] for r in data})==1; assert len({r["representative_pv_key"] for r in data})==1
    assert all(int(r["weather_hours"])==8760 and 0<=float(r["wind_capacity_factor"])<=1 and float(r["pv_specific_yield_kwh_per_kwp"])>=0 for r in data)
def test_normalization_formulas():
    for r in rows("optimization_results.csv"):
        annual=float(r["annual_demand_kwh"]); gwh=annual/1e6
        assert float(r["wind_MW_per_GWh"])==pytest.approx(float(r["wind_capacity_kw"])/1000/gwh)
        assert float(r["pv_MWac_per_GWh"])==pytest.approx(float(r["pv_ac_capacity_kw"])/1000/gwh)
        assert float(r["pv_MWdc_per_GWh"])==pytest.approx(float(r["pv_dc_capacity_kw"])/1000/gwh)
        assert float(r["battery_MWh_per_GWh"])==pytest.approx(float(r["battery_usable_capacity_kwh"])/1000/gwh)
        assert float(r["battery_MW_per_GWh"])==pytest.approx(float(r["battery_power_kw"])/1000/gwh)
        assert float(r["NPC_per_annual_kWh_demand"])==pytest.approx(float(r["npc_usd"])/annual)
        assert float(r["curtailment_fraction"])==pytest.approx(float(r["curtailment_kwh"])/float(r["raw_generation_kwh"]))
        assert float(r["raw_generation_load_ratio"])==pytest.approx(float(r["raw_generation_kwh"])/annual)
        assert float(r["wind_share_raw_generation"])+float(r["pv_share_raw_generation"])==pytest.approx(1)
        assert abs(float(r["energy_conservation_residual_kwh"]))<1e-6
def test_zero_denominator_escalation_is_semantic():
    for r in rows("reliability_escalation.csv"):
        if r["delta_wind_capacity_percent"]=="": assert r["wind_entered_at_99"] in {"True","False"}
        if r["delta_pv_capacity_percent"]=="": assert r["pv_entered_at_99"] in {"True","False"}
def test_batch_scenarios_use_identical_technology_set():
    registry=SiteRegistry(); selections=[scenario(registry,s,t).technologies for s in SITE_IDS for t in TARGETS]
    assert all(x.wind_keys==COMPARATIVE_WIND_KEYS for x in selections); assert len({x.model_dump_json() for x in selections})==1
def test_phase17_audit_and_frozen_benchmark():
    audit=json.loads((OUT/"phase17_audit.json").read_text()); assert audit["blockers"]==0
    frozen=json.loads((ROOT/"outputs/benchmarks/rodina/phase12/validation_audit.json").read_text()); assert frozen["blockers"]==0
