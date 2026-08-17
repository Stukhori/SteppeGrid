"""Phase 8 catalog. Values are transcribed from the cited primary/certification sources."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from steppegrid.equipment.models import (BatterySystemSpec, CutOutBehavior,
    EquipmentCategory, EquipmentProvenance, HighWindCurvePolicy, InverterSpec,
    ProjectScale, PVModuleSpec, SourceType, WindTurbineSpec)
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


class EquipmentCatalogVersion(str, Enum):
    RODINA_FROZEN_V1 = "RODINA_FROZEN_V1"
    PLANNER_V2 = "PLANNER_V2"


@dataclass(frozen=True)
class EquipmentCatalog:
    version: EquipmentCatalogVersion
    wind_turbines: Mapping[str, WindTurbineSpec]
    pv_modules: Mapping[str, PVModuleSpec]
    inverters: Mapping[str, InverterSpec]
    batteries: Mapping[str, BatterySystemSpec]

    @property
    def pv_block_keys(self) -> tuple[str, ...]:
        return tuple(
            f"{module_key}__{inverter_key}"
            for module_key in self.pv_modules
            for inverter_key in self.inverters
        )


_nps_source = EquipmentProvenance(
    manufacturer="Northern Power Systems Srl", product_model="NPS 100C-21",
    category=EquipmentCategory.WIND,
    source_title="NPS 100C-21 product brochure and tabulated Class II/A power curve",
    source_url="https://northernpower.com/wp/wp-content/uploads/2025/11/brochure-NPS-100C-21_ed2020_light_ENG.pdf",
    source_type=SourceType.MANUFACTURER_DATASHEET,
    source_organization="Northern Power Systems Srl", source_year=2020,
    parameters_supported=("rated_power_kw", "rotor_diameter_m", "supported_hub_heights_m", "planning_hub_height_m", "cut_in_wind_speed_m_s", "cut_out_wind_speed_m_s", "power_curve"),
    accessed_on=ACCESSED,
    notes="The brochure's curve table is printed beneath an apparent NPS 100C-24 label typo, while the page heading, 100 kW rating, 21 m rotor, and surrounding specifications identify the NPS 100C-21. Negative parasitic bins at 1-2 m/s are bounded to zero and are below cut-in.",
)
_leitwind_source = EquipmentProvenance(
    manufacturer="LEITNER SpA", product_model="LTW42 250 kW",
    category=EquipmentCategory.WIND,
    source_title="LEITWIND Product Portfolio — LTW42 tabulated power curve",
    source_url="https://www.leitwind.com/wp-content/uploads/2025/08/Leitwind_ProductPortfolio_ENG_Esecutivo-LR_WC_S.pdf",
    source_type=SourceType.MANUFACTURER_DATASHEET,
    source_organization="LEITNER SpA", source_year=2025,
    parameters_supported=("rated_power_kw", "rotor_diameter_m", "supported_hub_heights_m", "planning_hub_height_m", "cut_in_wind_speed_m_s", "cut_out_wind_speed_m_s", "power_curve"),
    accessed_on=ACCESSED,
    notes="The deterministic planning configuration uses the documented 39 m tower. The manufacturer table reports constant 250 kW from 15 through the 20 m/s cut-out threshold.",
)

_V2_WIND_ADDITIONS = {
    "northern_power_nps_100c_21": WindTurbineSpec(
        manufacturer="Northern Power Systems Srl", model="NPS 100C-21",
        rated_power_kw=100, maximum_curve_output_kw=100, rotor_diameter_m=20.7,
        supported_hub_heights_m=(22, 29, 37), planning_hub_height_m=37,
        cut_in_wind_speed_m_s=3, rated_wind_speed_m_s=15,
        cut_out_wind_speed_m_s=25, cut_out_behavior=CutOutBehavior.SPEED_THRESHOLD,
        high_wind_curve_policy=HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE,
        power_curve=_curve([(1,0),(2,0),(3,.5),(4,4.1),(5,10.5),(6,19),(7,29.4),(8,41),(9,54.3),(10,66.8),(11,77.7),(12,86.4),(13,92.8),(14,97.8),(15,100),(16,99.9),(17,99.2),(18,98.4),(19,97.5),(20,96.8),(21,96.4),(22,96.3),(23,96.8),(24,98),(25,99.2)]),
        provenance=(_nps_source,), scale_class=ProjectScale.COMMUNITY,
        notes="Manufacturer tabulated standard-density curve; output is zero below documented 3 m/s cut-in and above 25 m/s cut-out.",
    ),
    "leitwind_ltw42_250": WindTurbineSpec(
        manufacturer="LEITNER SpA", model="LTW42 250 kW",
        rated_power_kw=250, maximum_curve_output_kw=250, rotor_diameter_m=42,
        supported_hub_heights_m=(28, 39), planning_hub_height_m=39,
        cut_in_wind_speed_m_s=2.5, rated_wind_speed_m_s=11,
        cut_out_wind_speed_m_s=20, cut_out_behavior=CutOutBehavior.SPEED_THRESHOLD,
        high_wind_curve_policy=HighWindCurvePolicy.HOLD_LAST_CERTIFIED_VALUE,
        power_curve=_curve([(2.5,3),(3,7),(4,22),(5,47),(6,81),(7,128),(8,190),(9,234),(10,249),(11,250),(12,250),(13,250),(14,250),(15,250),(20,250)]),
        provenance=(_leitwind_source,), scale_class=ProjectScale.COMMERCIAL,
        notes="Manufacturer tabulated curve for the 250 kW variant; deterministic 39 m planning tower; output is zero above documented 20 m/s cut-out.",
    ),
}

_V2_INVERTER_ADDITIONS = {
    "sma_sunny_tripower_x_25": InverterSpec(
        manufacturer="SMA Solar Technology AG", model="Sunny Tripower X 25 (STP 25-50)",
        rated_ac_power_kw=25, maximum_dc_array_power_kw=37.5,
        maximum_efficiency=.982, constant_conversion_efficiency=.980,
        constant_efficiency_metric="European efficiency",
        mppt_voltage_min_v=430, mppt_voltage_max_v=800, maximum_dc_voltage_v=1000,
        scale_class=ProjectScale.SMALL_COMMUNITY,
        provenance=(EquipmentProvenance(
            manufacturer="SMA Solar Technology AG", product_model="Sunny Tripower X 25 (STP 25-50)",
            category=EquipmentCategory.INVERTER,
            source_title="Sunny Tripower X STP 12-50 / 15-50 / 20-50 / 25-50 Datasheet",
            source_url="https://files.sma.de/downloads/STPxx-50-DS-en-21.pdf",
            source_type=SourceType.MANUFACTURER_DATASHEET,
            source_organization="SMA Solar Technology AG", source_year=2023,
            parameters_supported=("rated_ac_power_kw", "maximum_dc_array_power_kw", "maximum_efficiency", "constant_conversion_efficiency", "constant_efficiency_metric", "mppt_voltage_limits", "maximum_dc_voltage_v"),
            accessed_on=ACCESSED,
        ),),
    )
}

_sungrow_255_datasheet = EquipmentProvenance(
    manufacturer="Sungrow Power Supply Co., Ltd.", product_model="ST255CS-2H PowerStack",
    category=EquipmentCategory.BATTERY,
    source_title="PowerStack ST255CS-2H Datasheet",
    source_url="https://info-support.sungrowpower.com/datasheet-materials/b4f56963-dbd2-4c43-8cbc-0808eb4cf083.pdf",
    source_type=SourceType.MANUFACTURER_DATASHEET,
    source_organization="Sungrow Power Supply Co., Ltd.", source_year=2025,
    parameters_supported=("nominal_energy", "usable_energy", "rated_power", "soc_bounds", "chemistry"),
    accessed_on=ACCESSED,
    notes="Datasheet reports LFP, 257 kWh rated capacity, 125 kW rated power, and 0–100% depth of charge and discharge; SteppeGrid therefore treats rated capacity as usable capacity.",
)
_sungrow_255_product = EquipmentProvenance(
    manufacturer="Sungrow Power Supply Co., Ltd.", product_model="ST255CS-2H PowerStack",
    category=EquipmentCategory.BATTERY,
    source_title="PowerStack ST255CS-2H manufacturer product specification",
    source_url="https://www.sungrowpower.com/en/products/c-i-energy-storage-system/st255cs-2h",
    source_type=SourceType.MANUFACTURER_PRODUCT_PAGE,
    source_organization="Sungrow Power Supply Co., Ltd.", source_year=2025,
    parameters_supported=("round_trip_efficiency",),
    accessed_on=ACCESSED,
    notes="Manufacturer reports system round-trip efficiency greater than 90%; SteppeGrid uses 90% deterministically.",
)
_sungrow_510_source = EquipmentProvenance(
    manufacturer="Sungrow Power Supply Co., Ltd.", product_model="ST510CS-4H PowerStack",
    category=EquipmentCategory.BATTERY,
    source_title="PowerStack 255CS ST510CS-4H manufacturer product specification",
    source_url="https://www.sungrowpower.com/us/en/products/residential-energy-storage-system/st510cs-4h-0708",
    source_type=SourceType.MANUFACTURER_PRODUCT_PAGE,
    source_organization="Sungrow Power Supply Co., Ltd.", source_year=2025,
    parameters_supported=("round_trip_efficiency",),
    accessed_on=ACCESSED,
    notes="Manufacturer reports 90% system round-trip efficiency.",
)
_sungrow_510_manual = EquipmentProvenance(
    manufacturer="Sungrow Power Supply Co., Ltd.", product_model="ST510CS-4H-AU PowerStack",
    category=EquipmentCategory.BATTERY,
    source_title="PowerStack ST510CS-4H-AU Energy Storage System User Manual",
    source_url="https://info-support.sungrowpower.com/product-materials/137cdbea-46d5-4a6f-a017-e851b87088db.pdf",
    source_type=SourceType.MANUFACTURER_MANUAL,
    source_organization="Sungrow Power Supply Co., Ltd.", source_year=2025,
    parameters_supported=("nominal_energy", "usable_energy", "rated_power", "soc_bounds", "chemistry"),
    accessed_on=ACCESSED,
    notes="Manual reports LFP, 514 kWh rated capacity, 125 kW rated power, and 0–100% depth of charge/discharge.",
)
_V2_BATTERY_ADDITIONS = {
    "sungrow_powerstack_st255_2h": BatterySystemSpec(
        manufacturer="Sungrow Power Supply Co., Ltd.", model="ST255CS-2H PowerStack",
        nominal_energy_capacity_kwh=257, usable_energy_capacity_kwh=257,
        maximum_charge_power_kw=125, maximum_discharge_power_kw=125,
        round_trip_efficiency=.90, minimum_soc_fraction=0, maximum_soc_fraction=1,
        chemistry="Lithium iron phosphate (LFP)", provenance=(_sungrow_255_datasheet, _sungrow_255_product),
        scale_class=ProjectScale.SMALL_COMMUNITY,
    ),
    "sungrow_powerstack_st510_4h": BatterySystemSpec(
        manufacturer="Sungrow Power Supply Co., Ltd.", model="ST510CS-4H PowerStack",
        nominal_energy_capacity_kwh=514, usable_energy_capacity_kwh=514,
        maximum_charge_power_kw=125, maximum_discharge_power_kw=125,
        round_trip_efficiency=.90, minimum_soc_fraction=0, maximum_soc_fraction=1,
        chemistry="Lithium iron phosphate (LFP)", provenance=(_sungrow_510_source, _sungrow_510_manual),
        scale_class=ProjectScale.COMMUNITY,
    ),
}

RODINA_FROZEN_V1 = EquipmentCatalog(
    version=EquipmentCatalogVersion.RODINA_FROZEN_V1,
    wind_turbines=MappingProxyType(dict(WIND_TURBINES)),
    pv_modules=MappingProxyType(dict(PV_MODULES)),
    inverters=MappingProxyType(dict(INVERTERS)),
    batteries=MappingProxyType(dict(BATTERIES)),
)
PLANNER_V2 = EquipmentCatalog(
    version=EquipmentCatalogVersion.PLANNER_V2,
    wind_turbines=MappingProxyType({**WIND_TURBINES, **_V2_WIND_ADDITIONS}),
    pv_modules=MappingProxyType(dict(PV_MODULES)),
    inverters=MappingProxyType({**INVERTERS, **_V2_INVERTER_ADDITIONS}),
    batteries=MappingProxyType({**BATTERIES, **_V2_BATTERY_ADDITIONS}),
)


def get_equipment_catalog(version: EquipmentCatalogVersion | str) -> EquipmentCatalog:
    parsed = EquipmentCatalogVersion(version)
    return RODINA_FROZEN_V1 if parsed is EquipmentCatalogVersion.RODINA_FROZEN_V1 else PLANNER_V2
