"""Hourly PV physics using pvlib solar position and irradiance transposition."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
import pvlib

from steppegrid.equipment.models import InverterSpec, PVModuleSpec

STC_IRRADIANCE_W_M2 = 1000.0
STC_CELL_TEMPERATURE_C = 25.0

@dataclass(frozen=True)
class PVGeneration:
    weather_timestamp: datetime
    solar_geometry_timestamp: datetime
    poa_irradiance_w_m2: float
    cell_temperature_c: float
    dc_power_kw: float
    ac_power_kw: float
    inverter_loss_kw: float
    clipped_power_kw: float


def solar_geometry_timestamp_for_hourly_radiation(weather_timestamp: datetime) -> datetime:
    """Return midpoint of Open-Meteo's preceding-hour mean radiation interval."""
    if weather_timestamp.tzinfo is None or weather_timestamp.utcoffset() is None:
        raise ValueError("weather_timestamp must be timezone-aware")
    return weather_timestamp - timedelta(minutes=30)

def hourly_pv_output(timestamp: datetime, latitude: float, longitude: float,
    ambient_temperature_c: float, global_horizontal_irradiance_w_m2: float,
    direct_normal_irradiance_w_m2: float, diffuse_horizontal_irradiance_w_m2: float,
    module: PVModuleSpec, module_count: int, inverter: InverterSpec,
    inverter_count: int, surface_tilt_deg: float, surface_azimuth_deg: float) -> PVGeneration:
    """PVWatts-style DC model. Azimuth is degrees clockwise from north (south=180)."""
    if module_count < 0 or inverter_count < 1 or not 0 <= surface_tilt_deg <= 180 or not 0 <= surface_azimuth_deg < 360:
        raise ValueError("invalid array count, inverter count, tilt, or azimuth")
    for value in (global_horizontal_irradiance_w_m2,direct_normal_irradiance_w_m2,diffuse_horizontal_irradiance_w_m2):
        if value < 0:
            raise ValueError("irradiance cannot be negative")
    geometry_timestamp = solar_geometry_timestamp_for_hourly_radiation(timestamp)
    times = pd.DatetimeIndex([geometry_timestamp])
    position = pvlib.solarposition.get_solarposition(times, latitude, longitude).iloc[0]
    poa = pvlib.irradiance.get_total_irradiance(surface_tilt_deg, surface_azimuth_deg,
        position.apparent_zenith, position.azimuth, direct_normal_irradiance_w_m2,
        global_horizontal_irradiance_w_m2, diffuse_horizontal_irradiance_w_m2,
        model="isotropic")
    poa_global = max(0.0, float(poa["poa_global"]))
    cell_c = ambient_temperature_c + (module.noct_c - 20.0) / 800.0 * poa_global
    temp_factor = max(0.0, 1 + module.temperature_coefficient_pmax_per_c * (cell_c - STC_CELL_TEMPERATURE_C))
    dc_kw = max(0.0, module.rated_power_kw * module_count * poa_global / STC_IRRADIANCE_W_M2 * temp_factor)
    # Constant published weighted-efficiency approximation, not a load-dependent curve.
    converted_kw = dc_kw * inverter.constant_conversion_efficiency
    ac_limit_kw = inverter.rated_ac_power_kw * inverter_count
    ac_kw = min(converted_kw, ac_limit_kw)
    return PVGeneration(timestamp, geometry_timestamp, poa_global, cell_c, dc_kw, ac_kw,
        max(0.0, dc_kw-converted_kw), max(0.0, converted_kw-ac_kw))
