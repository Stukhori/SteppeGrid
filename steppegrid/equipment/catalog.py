"""Phase 8 catalog. Values are transcribed from the cited primary/certification sources."""

from datetime import date

from steppegrid.equipment.models import (BatterySystemSpec, CutOutBehavior,
    EquipmentProvenance, HighWindCurvePolicy, InverterSpec, PVModuleSpec,
    SourceType, WindTurbineSpec)
from steppegrid.simulation.models import PowerCurvePoint

ACCESSED = date(2026, 8, 16)

def _source(mfr, model, title, url, kind, org, parameters, notes=None):
    return EquipmentProvenance(manufacturer=mfr, product_model=model, source_title=title,
        source_url=url, source_type=kind, source_organization=org,
        parameters_supported=tuple(parameters), accessed_on=ACCESSED, notes=notes)

def _curve(rows):
    return tuple(PowerCurvePoint(wind_speed_m_s=v, electrical_output_kw=max(0, p)) for v, p in rows)

_SWCC = SourceType.CERTIFICATION_REPORT
_skysource = _source("Wind Resource, LLC", "Skystream 3.7", "ICC-SWCC Summary Report SWCC-10-20",
    "https://smallwindcertification.org/wp-content/uploads/2023/04/Summary-Report-10-20-20230412.pdf",
    _SWCC, "Small Wind Certification Council", ("rated_power_kw","rotor_diameter_m","power_curve"),
    "Negative measured parasitic values below generation onset are retained in the report but bounded to zero in this catalog's generation curve.")
_sdsource = _source("SD Wind Energy, Ltd.", "SD6", "ICC-SWCC Summary Report SWCC-11-04",
    "https://smallwindcertification.org/wp-content/uploads/2021/04/SWCC-11-04-Summary-Report-2020.pdf",
    _SWCC, "Small Wind Certification Council", ("rated_power_kw","supported_hub_heights_m","power_curve"))
_bergesource = _source("Bergey Windpower Company", "Excel 15", "ICC-SWCC Summary Report SWCC-16-05",
    "https://smallwindcertification.org/wp-content/uploads/2022/04/SWCC-16-05-Summary-Report-20220406.pdf",
    _SWCC, "Small Wind Certification Council", ("rated_power_kw","rotor_diameter_m","supported_hub_heights_m","power_curve"))
_sdmanufacturer = _source("SD Wind Energy, Ltd.", "SD6", "SD6 Product Leaflet",
    "https://sd-windenergy.com/files/4017/1155/4933/SD6__Product_Leaflet.pdf",
    SourceType.MANUFACTURER_DATASHEET, "SD Wind Energy, Ltd.",
    ("cut_in_wind_speed_m_s", "cut_out_behavior", "supported_hub_heights_m", "rotor_diameter_m"),
    "Manufacturer states 'Cut Out Speed: None - Continuous Operation'.")
_bergemanufacturer = _source("Bergey Windpower Company", "Excel 15", "Excel 15 Product Specifications",
    "https://www.bergey.com/products/grid-tied-turbines/excel-15/",
    SourceType.MANUFACTURER_PRODUCT_PAGE, "Bergey Windpower Company",
    ("cut_in_wind_speed_m_s", "cut_out_behavior", "rotor_diameter_m"),
    "Manufacturer states 'Cut-Out Wind Speed: None'.")
_skymanufacturer = _source("Southwest Windpower, Inc.", "Skystream 3.7", "Skystream 3.7 Owner's Manual",
    "https://shop.solardirect.com/pdf/wind-power/skystream-manual.pdf",
    SourceType.MANUFACTURER_MANUAL, "Southwest Windpower, Inc.",
    ("cut_in_wind_speed_m_s", "rotor_diameter_m"),
    "Manufacturer-authored archival manual; it states 3.5 m/s cut-in and electronic stall regulation, but does not establish a cut-out threshold or explicitly state continuous operation.")

WIND_TURBINES = {
 "skystream_3_7": WindTurbineSpec(manufacturer="Wind Resource, LLC", model="Skystream 3.7", rated_power_kw=2.1, maximum_curve_output_kw=2.425,
  rotor_diameter_m=3.72, supported_hub_heights_m=(10.7,), cut_in_wind_speed_m_s=3.5,
  cut_out_behavior=CutOutBehavior.UNKNOWN, high_wind_curve_policy=HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE,
  power_curve=_curve([(3,0.003),(3.51,.034),(4.03,.084),(4.46,.132),(5,.203),(5.49,.285),(6,.391),(6.5,.510),(6.99,.643),(7.49,.799),(7.99,.968),(8.5,1.146),(8.99,1.333),(9.48,1.531),(9.98,1.745),(10.47,1.938),(10.97,2.101),(11.47,2.242),(11.93,2.301),(12.45,2.363),(12.97,2.403),(13.5,2.403),(13.99,2.425),(14.52,2.388),(15.02,2.412),(15.45,2.403),(15.99,2.393),(16.5,2.321)]), provenance=(_skysource,_skymanufacturer), notes="Certified sea-level curve. Manual cut-in is 3.5 m/s although the certified table has a small positive bin at 3.0 m/s. Cut-out behavior remains unknown. Above-domain output is a model assumption."),
 "sd6": WindTurbineSpec(manufacturer="SD Wind Energy, Ltd.", model="SD6", rated_power_kw=5.2, maximum_curve_output_kw=6.119,
  rotor_diameter_m=5.6, supported_hub_heights_m=(9,15,20), cut_in_wind_speed_m_s=2.5,
  cut_out_behavior=CutOutBehavior.CONTINUOUS_OPERATION, high_wind_curve_policy=HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE,
  power_curve=_curve([(2.54,.012),(3.05,.045),(3.52,.096),(3.98,.172),(4.49,.296),(4.99,.485),(5.5,.739),(5.99,1.020),(6.49,1.326),(7,1.733),(7.5,2.165),(8,2.674),(8.5,3.121),(8.98,3.546),(9.49,4.033),(10.01,4.428),(10.5,4.870),(10.99,5.164),(11.51,5.464),(11.99,5.626),(12.49,5.851),(12.98,5.960),(13.5,6),(13.98,6.026),(14.5,6.064),(15,6.059),(15.5,6.119),(15.99,6.099)]), provenance=(_sdsource,_sdmanufacturer), notes="Certified sea-level curve used only through 15.99 m/s. Manufacturer documents continuous operation; held high-wind output is still a model assumption, not certified performance."),
 "bergey_excel_15": WindTurbineSpec(manufacturer="Bergey Windpower Company", model="Excel 15", rated_power_kw=15.6, maximum_curve_output_kw=20.611,
  rotor_diameter_m=9.6, supported_hub_heights_m=(30,), cut_in_wind_speed_m_s=2.5,
  cut_out_behavior=CutOutBehavior.CONTINUOUS_OPERATION, high_wind_curve_policy=HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE,
  power_curve=_curve([(2.52,0),(2.99,.108),(3.49,.328),(4.01,.679),(4.51,1.280),(5,2.074),(5.5,2.878),(6,3.824),(6.5,4.897),(7,6.089),(7.49,7.226),(8,8.5),(8.5,9.731),(9,11.265),(9.49,12.361),(9.99,13.664),(10.51,14.502),(11.01,15.612),(11.48,16.304),(11.97,16.876),(12.51,17.506),(12.99,18.212),(13.5,18.942),(13.99,19.096),(14.48,19.6),(15,20.355),(15.51,20.251),(15.97,20.611),(16.47,19.687)]), provenance=(_bergesource,_bergemanufacturer), notes="Certified sea-level curve used only through 16.47 m/s. Manufacturer documents no cut-out; held high-wind output is a model assumption, not certified performance."),
}

def _pv(mfr, model, kw, area, eff, gamma, noct, vmpp, impp, voc, isc, title, url):
    src=_source(mfr,model,title,url,SourceType.MANUFACTURER_DATASHEET,mfr,("all_catalog_fields",))
    return PVModuleSpec(manufacturer=mfr,model=model,rated_power_kw=kw,module_area_m2=area,
        module_efficiency=eff,temperature_coefficient_pmax_per_c=gamma,noct_c=noct,
        voltage_mpp_v=vmpp,current_mpp_a=impp,open_circuit_voltage_v=voc,
        short_circuit_current_a=isc,provenance=(src,))
PV_MODULES = {
 "trina_tsm_450_neg9r28": _pv("Trina Solar","TSM-450NEG9R.28",.450,1.762*1.134,.225,-.0029,43,44.6,10.09,52.9,10.74,"Vertex S+ NEG9R.28 Datasheet","https://static.trinasolar.com/sites/default/files/Datasheet_Vertex%20S%2B_NEG9R.28_EN_2024_C_web.pdf"),
 "rec_alpha_pure_rx_470": _pv("REC Group","REC470AA Pure-RX",.470,2.08,.226,-.0024,44,55.4,8.49,65.6,8.95,"REC Alpha Pure-RX Series Datasheet","https://www.recgroup.com/sites/default/files/2024-06/ds_rec_alpha_pure-rx_series_iec_eng_web.pdf"),
 "trina_tsm_460_neg9r28": _pv("Trina Solar","TSM-460NEG9R.28",.460,1.762*1.134,.230,-.0029,43,45.4,10.14,53.8,10.81,"Vertex S+ NEG9R.28 Datasheet","https://static.trinasolar.com/sites/default/files/Datasheet_Vertex%20S%2B_NEG9R.28_EN_2024_C_web.pdf"),
}

def _inv(mfr,model,ac,dc,eff,constant_efficiency,metric,vmin,vmax,vdc,title,url):
    return InverterSpec(manufacturer=mfr,model=model,rated_ac_power_kw=ac,maximum_dc_array_power_kw=dc,
      maximum_efficiency=eff,constant_conversion_efficiency=constant_efficiency,
      constant_efficiency_metric=metric,mppt_voltage_min_v=vmin,mppt_voltage_max_v=vmax,
      maximum_dc_voltage_v=vdc,provenance=(_source(mfr,model,title,url,SourceType.MANUFACTURER_DATASHEET,mfr,("rated_ac_power_kw","maximum_dc_array_power_kw","maximum_efficiency","constant_conversion_efficiency","constant_efficiency_metric","mppt_voltage_limits","maximum_dc_voltage_v")),))
INVERTERS = {
 "sma_core1_stp50_41": _inv("SMA Solar Technology AG","Sunny Tripower CORE1 STP 50-41",50,75,.981,.978,"European efficiency",500,800,1000,"Sunny Tripower CORE1 Datasheet","https://files.sma.de/downloads/STP50-41-DS-en-16.pdf"),
 "fronius_tauro_eco_100": _inv("Fronius International GmbH","Tauro ECO 100-3-D",100,None,.985,.982,"European efficiency at 580 V DC",580,930,1000,"Fronius Tauro Datasheet","https://www.fronius.com/~/downloads/Solar%20Energy/Datasheets/SE_DS_Fronius_Tauro_D_EN_US.pdf"),
}

BATTERIES = {
 "tesla_megapack_2h": BatterySystemSpec(manufacturer="Tesla",model="Megapack 2-hour",nominal_energy_capacity_kwh=3854,usable_energy_capacity_kwh=3854,maximum_charge_power_kw=1927,maximum_discharge_power_kw=1927,round_trip_efficiency=.92,minimum_soc_fraction=0,maximum_soc_fraction=1,chemistry="Lithium-ion; chemistry not specified on cited page",provenance=(_source("Tesla","Megapack 2-hour","Megapack Product Details","https://www.tesla.com/megapack/design",SourceType.MANUFACTURER_PRODUCT_PAGE,"Tesla",("energy_capacity","power","round_trip_efficiency")),)),
 "saft_intensium_max_20_he": BatterySystemSpec(manufacturer="Saft",model="Intensium Max 20 High Energy LFP",nominal_energy_capacity_kwh=2300,usable_energy_capacity_kwh=2185,maximum_charge_power_kw=1100,maximum_discharge_power_kw=1100,round_trip_efficiency=.87,minimum_soc_fraction=.05,maximum_soc_fraction=1,chemistry="Lithium iron phosphate (LFP)",provenance=(_source("Saft","Intensium Max 20 High Energy LFP","Intensium Max AC service flyer and product datasheet","https://saft.com/en/download_file?q=6X7JMGAnv3Fm6HdmtEv%252B2gtlbZ1bRRVHkjS11M6md92GD2EF7vU%252F3Oybbz3WOlG%252BxR8srpA5iCdJ%252FV3IQzTVHQyiTucngZKEg9KkYCLkowAvgaG1hurmW8dDamS2sHPRD6nNl40%252BilVbshZtuw7ZXAX12rHkyf%252ButHzMvnkP2W0N%252FE2tRw%253D%253D%2F20220502_ESS_AC_flyer_LFP_EN_protected.pdf",SourceType.MANUFACTURER_DATASHEET,"Saft",("nominal_energy","rated_power","depth_of_discharge","round_trip_efficiency","chemistry"),"Usable energy is derived as 2.3 MWh x 95% DoD; source reports 87% AC/AC round-trip efficiency for typical use."),)),
}
