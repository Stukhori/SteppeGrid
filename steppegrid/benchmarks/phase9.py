"""Controlled Rodina technology benchmark (Phase 9; no optimization)."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
from pathlib import Path
from statistics import correlation, fmean

import pandas as pd
import pvlib

from steppegrid.benchmarks.paired import (
    RODINA_TIMEZONE_OFFSET, load_rodina_site_config, local_year_interval,
)
from steppegrid.benchmarks.reconstruction import VALID_SHAPES, reconstruct_hourly_load
from steppegrid.benchmarks.source import load_monthly_benchmark
from steppegrid.benchmarks.wind_shear import (
    GENERIC_SHEAR_EXPONENT, estimate_two_height_shear, reconstruct_10m_diagnostics,
)
from steppegrid.equipment.catalog import BATTERIES, INVERTERS, PV_MODULES, WIND_TURBINES
from steppegrid.equipment.models import CutOutBehavior
from steppegrid.simulation.battery import BatteryState
from steppegrid.simulation.models import BatteryConfig, WeatherDataset
from steppegrid.simulation.pv import STC_CELL_TEMPERATURE_C, STC_IRRADIANCE_W_M2
from steppegrid.simulation.wind import DEFAULT_WIND_SHEAR_EXPONENT, commercial_turbine_output_kw, wind_speed_at_hub_height
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider, REQUESTED_VARIABLES

REFERENCE_TILT_DEG = 51.302445
REFERENCE_AZIMUTH_DEG = 180.0
HYBRID_WIND_SHARE = 0.5
HYBRID_PV_SHARE = 0.5
OUTPUT_DIRECTORY = Path("outputs/benchmarks/rodina/phase9")
STORAGE_WIND_KEY = "skystream_3_7"
STORAGE_PV_KEY = "trina_tsm_450_neg9r28__sma_core1_stp50_41"


@dataclass(frozen=True)
class Phase9Run:
    weather_integrity: dict
    load_integrity: dict
    wind: dict[str, dict]
    wind_profiles_kwh: dict[str, list[float]]
    wind_generic_reference: dict[str, dict]
    wind_shear: dict
    pv: dict[str, dict]
    pv_profiles_kwh: dict[str, list[float]]
    coincidence: list[dict]
    complementarity: list[dict]
    storage: list[dict]


def load_phase9_weather(*, cache_root: str | Path = "data/weather/cache") -> WeatherDataset:
    config = load_rodina_site_config()
    interval = local_year_interval(2025, RODINA_TIMEZONE_OFFSET)
    return OpenMeteoHistoricalWeatherProvider(cache_root=cache_root).get_hourly_weather(
        config.site, interval.utc_start, interval.utc_end
    )


def validate_phase9_weather(weather: WeatherDataset) -> dict:
    config = load_rodina_site_config()
    interval = local_year_interval(2025, RODINA_TIMEZONE_OFFSET)
    series = weather.series
    arrays = {
        "temperature_c": series.temperature_c,
        "wind_speed_10m_m_s": series.wind_speed_m_s,
        "ghi_w_m2": series.solar_irradiance_w_m2,
        "wind_speed_100m_m_s": series.wind_speed_100m_m_s,
        "dni_w_m2": series.direct_normal_irradiance_w_m2,
        "dhi_w_m2": series.diffuse_radiation_w_m2,
    }
    if series.timestamps != [interval.utc_start + timedelta(hours=i) for i in range(8760)]:
        raise ValueError("Phase 9 weather does not cover the exact Rodina local-year UTC interval")
    if any(values is None or len(values) != 8760 for values in arrays.values()):
        raise ValueError("Phase 9 requires six complete 8,760-value weather arrays")
    if any(not math.isfinite(v) for values in arrays.values() for v in values):
        raise ValueError("Phase 9 weather contains non-finite values")
    if not set(REQUESTED_VARIABLES).issubset(weather.provenance.variables_requested):
        raise ValueError("weather provenance does not include every Phase 9 variable")
    return {
        "records": 8760, "duplicates": 0, "timezone": "UTC weather / UTC+05:00 load",
        "reference_year": 2025, "latitude": config.site.latitude,
        "longitude": config.site.longitude, "variables": list(REQUESTED_VARIABLES),
        "cache_key": weather.provenance.cache_key,
    }


def load_phase9_loads() -> tuple[dict[str, list[float]], dict]:
    source = load_monthly_benchmark()
    loads: dict[str, list[float]] = {}
    monthly = None
    for shape in VALID_SHAPES:
        result = reconstruct_hourly_load(source, variant="published_monthly_rows", shape=shape,
            reference_year=2025, timezone_offset=RODINA_TIMEZONE_OFFSET)
        loads[shape] = result.dataset.total_load_kwh
        totals = [row.reconstructed_kwh for row in result.validation]
        if monthly is None:
            monthly = totals
        elif any(abs(a-b) > 1e-6 for a,b in zip(monthly, totals, strict=True)):
            raise ValueError("Rodina reconstructed shapes do not preserve identical monthly totals")
    annual = math.fsum(loads[VALID_SHAPES[0]])
    return loads, {"records_per_shape": 8760, "timezone": RODINA_TIMEZONE_OFFSET,
        "annual_kwh": annual, "monthly_kwh": monthly,
        "printed_annual_kwh": source.provenance.published_annual_load_kwh,
        "hourly_values_measured": False, "shapes": list(VALID_SHAPES)}


def _monthly(timestamps, values):
    return [math.fsum(v for t,v in zip(timestamps, values, strict=True) if t.month == month)
            for month in range(1,13)]


def benchmark_wind(weather: WeatherDataset, *, shear_exponent: float) -> tuple[dict[str,dict],dict[str,list[float]]]:
    series = weather.series
    timestamps = [t.astimezone(timezone(timedelta(hours=5))) for t in series.timestamps]
    results, profiles = {}, {}
    for key, turbine in WIND_TURBINES.items():
        hub = turbine.supported_hub_heights_m[0]
        hub_speeds = [wind_speed_at_hub_height(v,hub,shear_exponent=shear_exponent) for v in series.wind_speed_100m_m_s]
        power = [commercial_turbine_output_kw(v,turbine,hub,shear_exponent) for v in series.wind_speed_100m_m_s]
        annual = math.fsum(power)
        final_speed = turbine.power_curve[-1].wind_speed_m_s
        above = sum(v > final_speed for v in hub_speeds)
        cutout = sum(turbine.cut_out_behavior == CutOutBehavior.SPEED_THRESHOLD and
                     v > turbine.cut_out_wind_speed_m_s for v in hub_speeds)
        monthly = _monthly(timestamps,power)
        results[key] = {"manufacturer":turbine.manufacturer,"model":turbine.model,
            "rated_power_kw":turbine.rated_power_kw,"hub_height_m":hub,
            "shear_exponent":shear_exponent,"annual_generation_kwh":annual,
            "specific_yield_kwh_per_rated_kw":annual/turbine.rated_power_kw,
            "capacity_factor":annual/(turbine.rated_power_kw*8760),
            "mean_power_kw":fmean(power),"maximum_power_kw":max(power),
            "zero_generation_hours":sum(v <= 0 for v in power),
            "below_cut_in_hours":sum(v < turbine.cut_in_wind_speed_m_s for v in hub_speeds),
            "inside_certified_curve_hours":sum(turbine.power_curve[0].wind_speed_m_s <= v <= final_speed for v in hub_speeds),
            "above_certified_curve_hours":above,"high_wind_policy_hours":above-cutout,
            "documented_cut_out_hours":cutout,"mean_hub_wind_speed_m_s":fmean(hub_speeds),
            "monthly_generation_kwh":monthly,
            "monthly_capacity_factor":[e/(turbine.rated_power_kw*d*24) for e,d in zip(monthly,(31,28,31,30,31,30,31,31,30,31,30,31),strict=True)],
            "high_wind_curve_policy":turbine.high_wind_curve_policy.value}
        profiles[key]=power
    results["resource"]={"mean_wind_speed_100m_m_s":fmean(series.wind_speed_100m_m_s),
        "monthly_mean_wind_speed_100m_m_s":[fmean(v for t,v in zip(timestamps,series.wind_speed_100m_m_s,strict=True) if t.month==m) for m in range(1,13)]}
    return results,profiles


def _poa(weather: WeatherDataset) -> list[float]:
    series=weather.series
    times=pd.DatetimeIndex([t-timedelta(minutes=30) for t in series.timestamps])
    pos=pvlib.solarposition.get_solarposition(times,REFERENCE_TILT_DEG,70.541645)
    ghi=pd.Series(series.solar_irradiance_w_m2,index=times)
    dni=pd.Series(series.direct_normal_irradiance_w_m2,index=times)
    dhi=pd.Series(series.diffuse_radiation_w_m2,index=times)
    poa=pvlib.irradiance.get_total_irradiance(REFERENCE_TILT_DEG,REFERENCE_AZIMUTH_DEG,
        pos.apparent_zenith,pos.azimuth,dni,ghi,dhi,model="isotropic")
    return [max(0,float(v)) for v in poa["poa_global"]]


def benchmark_pv(weather: WeatherDataset) -> tuple[dict[str,dict],dict[str,list[float]]]:
    timestamps=[t.astimezone(timezone(timedelta(hours=5))) for t in weather.series.timestamps]
    poa=_poa(weather); results={}; profiles={}
    for module_key,module in PV_MODULES.items():
        cell=[ta+(module.noct_c-20)/800*g for ta,g in zip(weather.series.temperature_c,poa,strict=True)]
        for inverter_key,inverter in INVERTERS.items():
            count=math.floor(inverter.rated_ac_power_kw/module.rated_power_kw)
            dc_capacity=count*module.rated_power_kw
            dc=[max(0,dc_capacity*g/STC_IRRADIANCE_W_M2*max(0,1+module.temperature_coefficient_pmax_per_c*(tc-STC_CELL_TEMPERATURE_C))) for g,tc in zip(poa,cell,strict=True)]
            converted=[v*inverter.constant_conversion_efficiency for v in dc]
            ac=[min(v,inverter.rated_ac_power_kw) for v in converted]
            losses=[d-c for d,c in zip(dc,converted,strict=True)]
            clipping=[max(0,c-a) for c,a in zip(converted,ac,strict=True)]
            key=f"{module_key}__{inverter_key}"
            annual_dc,annual_ac=math.fsum(dc),math.fsum(ac)
            results[key]={"module":module.model,"inverter":inverter.model,"module_count":count,
                "dc_capacity_kw":dc_capacity,"ac_capacity_kw":inverter.rated_ac_power_kw,
                "dc_ac_ratio":dc_capacity/inverter.rated_ac_power_kw,"tilt_deg":REFERENCE_TILT_DEG,
                "azimuth_deg":REFERENCE_AZIMUTH_DEG,"annual_poa_kwh_m2":math.fsum(poa)/1000,
                "annual_dc_kwh":annual_dc,"annual_ac_kwh":annual_ac,
                "dc_specific_yield_kwh_per_kwp":annual_dc/dc_capacity,
                "ac_specific_yield_kwh_per_kwp":annual_ac/dc_capacity,
                "ac_capacity_factor":annual_ac/(inverter.rated_ac_power_kw*8760),
                "inverter_conversion_loss_kwh":math.fsum(losses),"clipping_kwh":math.fsum(clipping),
                "constant_efficiency":inverter.constant_conversion_efficiency,
                "constant_efficiency_metric":inverter.constant_efficiency_metric,
                "monthly_ac_kwh":_monthly(timestamps,ac),
                "monthly_specific_yield_kwh_per_kwp":[v/dc_capacity for v in _monthly(timestamps,ac)]}
            profiles[key]=ac
    return results,profiles


def normalize_to_annual_energy(profile:list[float],target_kwh:float)->list[float]:
    total=math.fsum(profile)
    if total<=0: raise ValueError("cannot normalize zero generation")
    return [v*target_kwh/total for v in profile]


def coincidence_metrics(load, generation, timestamps, *, shape, resource, category):
    direct=[min(g,l) for g,l in zip(generation,load,strict=True)]
    surplus=[max(g-l,0) for g,l in zip(generation,load,strict=True)]
    unmet=[max(l-g,0) for g,l in zip(generation,load,strict=True)]
    annual_load=math.fsum(load)
    fully=sum(g>=l for g,l in zip(generation,load,strict=True))
    partially=sum(0<g<l for g,l in zip(generation,load,strict=True))
    zero=sum(g<=0 for g in generation)
    monthly_load=_monthly(timestamps,load); monthly_direct=_monthly(timestamps,direct)
    return {"benchmark":"annual-energy-normalized coincidence benchmark",
        "analytical_normalization_only":True,"load_shape":shape,"category":category,
        "resource":resource,"annual_load_kwh":annual_load,"annual_generation_kwh":math.fsum(generation),
        "direct_kwh":math.fsum(direct),"direct_load_fraction":math.fsum(direct)/annual_load,
        "surplus_kwh":math.fsum(surplus),"unmet_kwh":math.fsum(unmet),
        "fully_served_hours":fully,"fully_served_hour_fraction":fully/len(load),
        "partially_served_hours":partially,"partially_served_hour_fraction":partially/len(load),
        "zero_generation_hours":zero,"zero_generation_hour_fraction":zero/len(load),
        "monthly_direct_kwh":monthly_direct,
        "monthly_direct_load_fraction":[d/l if l else 0 for d,l in zip(monthly_direct,monthly_load,strict=True)],
        "monthly_surplus_kwh":_monthly(timestamps,surplus),
        "monthly_unmet_kwh":_monthly(timestamps,unmet)}


def _pearson(a,b):
    return None if len(set(a))<2 or len(set(b))<2 else correlation(a,b)


def build_coincidence(loads,wind_profiles,pv_profiles,timestamps):
    rows=[]; complementarity=[]
    for shape,load in loads.items():
        annual=math.fsum(load)
        for key,profile in wind_profiles.items():
            rows.append(coincidence_metrics(load,normalize_to_annual_energy(profile,annual),timestamps,shape=shape,resource=key,category="wind"))
        for key,profile in pv_profiles.items():
            rows.append(coincidence_metrics(load,normalize_to_annual_energy(profile,annual),timestamps,shape=shape,resource=key,category="pv"))
        for wkey,w in wind_profiles.items():
            wn=normalize_to_annual_energy(w,annual*HYBRID_WIND_SHARE)
            for pkey,p in pv_profiles.items():
                pn=normalize_to_annual_energy(p,annual*HYBRID_PV_SHARE)
                hybrid=[a+b for a,b in zip(wn,pn,strict=True)]
                rows.append(coincidence_metrics(load,hybrid,timestamps,shape=shape,resource=f"{wkey}__{pkey}",category="hybrid_50_50"))
                if shape==VALID_SHAPES[0]:
                    complementarity.append({"wind":wkey,"pv":pkey,"pearson_correlation":_pearson(w,p),
                        "both_low_hours":sum(a<=.01*max(w) and b<=.01*max(p) for a,b in zip(w,p,strict=True)),
                        "at_least_one_producing_hours":sum(a>0 or b>0 for a,b in zip(w,p,strict=True)),
                        "monthly_wind_share":[x/(x+y) if x+y else None for x,y in zip(_monthly(timestamps,wn),_monthly(timestamps,pn),strict=True)]})
    return rows,complementarity


def storage_dispatch(load,generation,battery_key):
    spec=BATTERIES[battery_key]; efficiency=math.sqrt(spec.round_trip_efficiency)
    minimum=spec.nominal_energy_capacity_kwh*spec.minimum_soc_fraction
    cfg=BatteryConfig(capacity_kwh=spec.nominal_energy_capacity_kwh,initial_soc_kwh=minimum,
        minimum_soc_kwh=minimum,maximum_charge_kw=spec.maximum_charge_power_kw,
        maximum_discharge_kw=spec.maximum_discharge_power_kw,charging_efficiency=efficiency,
        discharging_efficiency=efficiency)
    state=BatteryState(cfg); direct=charge=discharge=loss=curtail=unmet=initial_discharge=sim_discharge=0.0
    fully=0
    for l,g in zip(load,generation,strict=True):
        d=min(l,g); surplus=g-d; deficit=l-d
        c=state.charge(surplus); out=state.discharge(deficit)
        u=deficit-out.bus_energy_kwh
        direct+=d; charge+=c.bus_energy_kwh; discharge+=out.bus_energy_kwh
        loss+=c.loss_kwh+out.loss_kwh; curtail+=surplus-c.bus_energy_kwh; unmet+=u
        initial_discharge+=out.from_initial_inventory_kwh; sim_discharge+=out.from_simulation_charge_kwh
        fully+=u<=1e-9
    throughput=charge+discharge
    return {"battery":battery_key,"battery_count":1,"annual_load_kwh":math.fsum(load),
        "renewable_generation_kwh":math.fsum(generation),"direct_renewable_to_load_kwh":direct,
        "battery_charge_input_kwh":charge,"battery_discharge_delivered_kwh":discharge,
        "battery_conversion_loss_kwh":loss,"curtailment_kwh":curtail,"unmet_load_kwh":unmet,
        "served_load_kwh":math.fsum(load)-unmet,"renewable_fraction":(direct+sim_discharge)/math.fsum(load),
        "starting_soc_kwh":minimum,"ending_soc_kwh":state.soc_kwh,
        "initial_stored_inventory_kwh":minimum,"discharge_from_initial_inventory_kwh":initial_discharge,
        "discharge_from_simulation_charge_kwh":sim_discharge,"throughput_kwh":throughput,
        "throughput_per_usable_kwh":throughput/spec.usable_energy_capacity_kwh,
        "discharge_per_usable_kwh":discharge/spec.usable_energy_capacity_kwh,
        "loss_per_throughput":loss/throughput if throughput else 0,"equivalent_full_cycles":discharge/spec.usable_energy_capacity_kwh,
        "fraction_load_served":1-unmet/math.fsum(load),"fully_served_hours":fully,
        "fully_served_hour_fraction":fully/len(load),
        "energy_balance_generation_error_kwh":math.fsum(generation)-direct-charge-curtail,
        "energy_balance_load_error_kwh":math.fsum(load)-direct-discharge-unmet,
        "energy_balance_storage_error_kwh":state.soc_kwh-minimum-(charge-discharge-loss)}


def benchmark_storage(loads,wind_profiles,pv_profiles,timestamps):
    rows=[]
    for shape,load in loads.items():
        annual=math.fsum(load)
        wind=normalize_to_annual_energy(wind_profiles[STORAGE_WIND_KEY],annual*.5)
        pv=normalize_to_annual_energy(pv_profiles[STORAGE_PV_KEY],annual*.5)
        hybrid=[a+b for a,b in zip(wind,pv,strict=True)]
        base=coincidence_metrics(load,hybrid,timestamps,shape=shape,resource="fixed_storage_hybrid",category="hybrid_50_50")
        for key in BATTERIES:
            row=storage_dispatch(load,hybrid,key); row.update(load_shape=shape,
                baseline_unmet_kwh=base["unmet_kwh"],unmet_improvement_kwh=base["unmet_kwh"]-row["unmet_load_kwh"],
                baseline_direct_load_fraction=base["direct_load_fraction"])
            rows.append(row)
    return rows


def run_phase9(*,weather=None,write_outputs=True,output_directory=OUTPUT_DIRECTORY):
    weather=weather or load_phase9_weather(); weather_integrity=validate_phase9_weather(weather)
    loads,load_integrity=load_phase9_loads()
    local_timestamps=[t.astimezone(timezone(timedelta(hours=5))) for t in weather.series.timestamps]
    shear=estimate_two_height_shear(weather.series.wind_speed_m_s,weather.series.wind_speed_100m_m_s,
        timestamps=local_timestamps)
    wind,wind_profiles=benchmark_wind(weather,shear_exponent=shear.exponent)
    wind_generic,_=benchmark_wind(weather,shear_exponent=GENERIC_SHEAR_EXPONENT)
    wind_shear=shear.to_dict()
    wind_shear["derived_reconstruction"]=reconstruct_10m_diagnostics(weather.series.wind_speed_m_s,
        weather.series.wind_speed_100m_m_s,shear.exponent)
    wind_shear["generic_one_seventh_reconstruction"]=reconstruct_10m_diagnostics(weather.series.wind_speed_m_s,
        weather.series.wind_speed_100m_m_s,GENERIC_SHEAR_EXPONENT)
    pv,pv_profiles=benchmark_pv(weather)
    timestamps=[t.astimezone(timezone(timedelta(hours=5))) for t in weather.series.timestamps]
    coincidence,complementarity=build_coincidence(loads,wind_profiles,pv_profiles,timestamps)
    storage=benchmark_storage(loads,wind_profiles,pv_profiles,timestamps)
    run=Phase9Run(weather_integrity,load_integrity,wind,wind_profiles,wind_generic,wind_shear,pv,pv_profiles,coincidence,complementarity,storage)
    if write_outputs: write_phase9_outputs(run,output_directory)
    return run


def write_phase9_outputs(run,output_directory):
    out=Path(output_directory); out.mkdir(parents=True,exist_ok=True)
    def dump(name,value):
        (out/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    dump("integrity.json",{"weather":run.weather_integrity,"load":run.load_integrity})
    dump("wind_summary.json",run.wind); dump("pv_summary.json",run.pv)
    dump("wind_generic_one_seventh_reference.json",run.wind_generic_reference)
    dump("wind_shear_diagnostics.json",run.wind_shear)
    dump("coincidence_summary.json",run.coincidence); dump("complementarity_summary.json",run.complementarity)
    dump("storage_summary.json",run.storage)
    for name,rows in (("coincidence_summary.csv",run.coincidence),("storage_summary.csv",run.storage)):
        scalar=[{k:v for k,v in row.items() if not isinstance(v,list)} for row in rows]
        with (out/name).open("w",newline="",encoding="utf-8") as h:
            writer=csv.DictWriter(h,fieldnames=list(scalar[0])); writer.writeheader(); writer.writerows(scalar)
