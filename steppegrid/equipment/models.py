"""Typed equipment records with parameter-level provenance."""

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from steppegrid.simulation.models import DomainModel, PowerCurvePoint


class SourceType(str, Enum):
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"
    MANUFACTURER_PRODUCT_PAGE = "manufacturer_product_page"
    CERTIFICATION_REPORT = "certification_report"
    MANUFACTURER_MANUAL = "manufacturer_manual"


class EquipmentCategory(str, Enum):
    WIND = "wind"
    PV_MODULE = "pv_module"
    INVERTER = "inverter"
    BATTERY = "battery"


class ProjectScale(str, Enum):
    SMALL_COMMUNITY = "small_community"
    COMMUNITY = "community"
    COMMERCIAL = "commercial"
    UTILITY = "utility"


class CutOutBehavior(str, Enum):
    SPEED_THRESHOLD = "speed_threshold"
    CONTINUOUS_OPERATION = "continuous_operation"
    UNKNOWN = "unknown"


class HighWindCurvePolicy(str, Enum):
    HOLD_LAST_CERTIFIED_VALUE = "hold_last_certified_value"


class EquipmentProvenance(DomainModel):
    manufacturer: str
    product_model: str
    source_title: str
    source_url: str
    source_type: SourceType
    source_organization: str
    parameters_supported: tuple[str, ...]
    accessed_on: date
    category: EquipmentCategory | None = None
    source_year: int | None = Field(default=None, ge=1900, le=9999)
    notes: str | None = None


class WindTurbineSpec(DomainModel):
    manufacturer: str
    model: str
    rated_power_kw: float = Field(gt=0)
    maximum_curve_output_kw: float = Field(gt=0)
    rotor_diameter_m: float | None = Field(default=None, gt=0)
    supported_hub_heights_m: tuple[float, ...]
    cut_in_wind_speed_m_s: float = Field(ge=0)
    rated_wind_speed_m_s: float | None = Field(default=None, gt=0)
    cut_out_wind_speed_m_s: float | None = Field(default=None, gt=0)
    cut_out_behavior: CutOutBehavior
    high_wind_curve_policy: HighWindCurvePolicy
    power_curve: tuple[PowerCurvePoint, ...]
    power_curve_wind_speed_units: str = "m/s"
    power_curve_output_units: str = "kW"
    provenance: tuple[EquipmentProvenance, ...]
    notes: str
    scale_class: ProjectScale = ProjectScale.SMALL_COMMUNITY
    planning_hub_height_m: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_curve(self):
        speeds = [p.wind_speed_m_s for p in self.power_curve]
        if speeds != sorted(speeds) or len(speeds) != len(set(speeds)):
            raise ValueError("power-curve wind speeds must be strictly increasing")
        if max(p.electrical_output_kw for p in self.power_curve) > self.maximum_curve_output_kw:
            raise ValueError("maximum_curve_output_kw must bound the certified curve")
        if self.cut_out_behavior == CutOutBehavior.SPEED_THRESHOLD:
            if self.cut_out_wind_speed_m_s is None:
                raise ValueError("speed_threshold requires cut_out_wind_speed_m_s")
        elif self.cut_out_wind_speed_m_s is not None:
            raise ValueError("only speed_threshold may define cut_out_wind_speed_m_s")
        if self.planning_hub_height_m is not None and self.planning_hub_height_m not in self.supported_hub_heights_m:
            raise ValueError("planning hub height must be one of the documented supported heights")
        return self


class PVModuleSpec(DomainModel):
    manufacturer: str
    model: str
    rated_power_kw: float = Field(gt=0)
    module_area_m2: float = Field(gt=0)
    module_efficiency: float = Field(gt=0, le=1)
    temperature_coefficient_pmax_per_c: float
    noct_c: float = Field(gt=0)
    voltage_mpp_v: float = Field(gt=0)
    current_mpp_a: float = Field(gt=0)
    open_circuit_voltage_v: float = Field(gt=0)
    short_circuit_current_a: float = Field(gt=0)
    provenance: tuple[EquipmentProvenance, ...]
    scale_class: ProjectScale = ProjectScale.COMMERCIAL


class InverterSpec(DomainModel):
    manufacturer: str
    model: str
    rated_ac_power_kw: float = Field(gt=0)
    maximum_dc_array_power_kw: float | None = Field(default=None, gt=0)
    maximum_efficiency: float = Field(gt=0, le=1)
    constant_conversion_efficiency: float = Field(gt=0, le=1)
    constant_efficiency_metric: str
    mppt_voltage_min_v: float = Field(gt=0)
    mppt_voltage_max_v: float = Field(gt=0)
    maximum_dc_voltage_v: float = Field(gt=0)
    provenance: tuple[EquipmentProvenance, ...]
    scale_class: ProjectScale = ProjectScale.COMMERCIAL


class BatterySystemSpec(DomainModel):
    manufacturer: str
    model: str
    nominal_energy_capacity_kwh: float = Field(gt=0)
    usable_energy_capacity_kwh: float = Field(gt=0)
    maximum_charge_power_kw: float = Field(gt=0)
    maximum_discharge_power_kw: float = Field(gt=0)
    round_trip_efficiency: float = Field(gt=0, le=1)
    minimum_soc_fraction: float = Field(ge=0, lt=1)
    maximum_soc_fraction: float = Field(gt=0, le=1)
    chemistry: str
    provenance: tuple[EquipmentProvenance, ...]
    scale_class: ProjectScale = ProjectScale.UTILITY

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.usable_energy_capacity_kwh > self.nominal_energy_capacity_kwh:
            raise ValueError("usable capacity cannot exceed nominal capacity")
        if self.minimum_soc_fraction >= self.maximum_soc_fraction:
            raise ValueError("SOC bounds are reversed")
        return self
