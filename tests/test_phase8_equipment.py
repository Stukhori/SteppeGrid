from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from steppegrid.equipment.catalog import BATTERIES, INVERTERS, PV_MODULES, WIND_TURBINES
from steppegrid.equipment.models import CutOutBehavior, InverterSpec, WindTurbineSpec
from steppegrid.simulation.battery import BatteryState
from steppegrid.simulation.models import BatteryConfig
from steppegrid.simulation.pv import hourly_pv_output, solar_geometry_timestamp_for_hourly_radiation
from steppegrid.simulation.wind import commercial_turbine_output_kw, wind_speed_at_hub_height


def test_catalog_has_required_real_products_and_provenance():
    assert len(WIND_TURBINES) >= 3 and len(PV_MODULES) >= 3
    assert len(INVERTERS) >= 2 and len(BATTERIES) >= 2
    for product in (*WIND_TURBINES.values(), *PV_MODULES.values(), *INVERTERS.values(), *BATTERIES.values()):
        assert product.provenance
        for source in product.provenance:
            assert source.source_url.startswith("https://")
            assert source.source_title and source.parameters_supported


@pytest.mark.parametrize("turbine", WIND_TURBINES.values())
def test_certified_curves_are_ordered_nonnegative_and_bounded(turbine):
    speeds = [point.wind_speed_m_s for point in turbine.power_curve]
    outputs = [point.electrical_output_kw for point in turbine.power_curve]
    assert speeds == sorted(speeds) and len(speeds) == len(set(speeds))
    assert min(outputs) >= 0
    assert max(outputs) <= turbine.maximum_curve_output_kw


def test_wind_height_conversion_and_physical_boundaries():
    turbine = WIND_TURBINES["bergey_excel_15"]
    assert wind_speed_at_hub_height(8, 100) == pytest.approx(8)
    assert wind_speed_at_hub_height(8, 120) > 8
    assert commercial_turbine_output_kw(0, turbine, 100) == 0
    assert commercial_turbine_output_kw(2, turbine, 100) == 0
    with pytest.raises(ValueError):
        wind_speed_at_hub_height(-1, 100)


def test_wind_exact_curve_point_and_interpolation():
    turbine = WIND_TURBINES["sd6"]
    assert commercial_turbine_output_kw(7, turbine, 100, shear_exponent=0) == pytest.approx(1.733)
    expected = (1.733 + 2.165) / 2
    assert commercial_turbine_output_kw(7.25, turbine, 100, shear_exponent=0) == pytest.approx(expected)


@pytest.mark.parametrize("key", ["sd6", "bergey_excel_15"])
def test_documented_continuous_operation_holds_last_curve_value(key):
    turbine = WIND_TURBINES[key]
    last = turbine.power_curve[-1]
    assert turbine.cut_out_behavior == CutOutBehavior.CONTINUOUS_OPERATION
    assert commercial_turbine_output_kw(last.wind_speed_m_s, turbine, 100, 0) == last.electrical_output_kw
    assert commercial_turbine_output_kw(last.wind_speed_m_s + .01, turbine, 100, 0) == last.electrical_output_kw
    assert commercial_turbine_output_kw(100, turbine, 100, 0) == last.electrical_output_kw


def test_unknown_cut_out_uses_same_explicit_non_extrapolating_policy():
    turbine = WIND_TURBINES["skystream_3_7"]
    assert turbine.cut_out_behavior == CutOutBehavior.UNKNOWN
    assert commercial_turbine_output_kw(100, turbine, 100, 0) == turbine.power_curve[-1].electrical_output_kw


def test_documented_numeric_cut_out_overrides_high_wind_hold_policy():
    values = WIND_TURBINES["skystream_3_7"].model_dump()
    values.update(cut_out_behavior="speed_threshold", cut_out_wind_speed_m_s=18)
    turbine = WindTurbineSpec.model_validate(values)
    assert commercial_turbine_output_kw(18, turbine, 100, 0) == turbine.power_curve[-1].electrical_output_kw
    assert commercial_turbine_output_kw(18.01, turbine, 100, 0) == 0


def _pv(temp=20, ghi=800, dni=700, dhi=100, inverter_key="sma_core1_stp50_41", modules=200):
    return hourly_pv_output(datetime(2025, 6, 21, 7, tzinfo=timezone.utc), 51.302445, 70.541645,
        temp, ghi, dni, dhi, PV_MODULES["trina_tsm_450_neg9r28"], modules,
        INVERTERS[inverter_key], 1, 35, 180)


def test_pv_zero_irradiance_and_temperature_response():
    zero = _pv(ghi=0, dni=0, dhi=0)
    assert zero.dc_power_kw == 0 and zero.ac_power_kw == 0
    assert _pv(temp=40).dc_power_kw < _pv(temp=0).dc_power_kw


def test_poa_and_inverter_clipping_are_physical():
    result = _pv(modules=1000)
    assert result.poa_irradiance_w_m2 >= 0
    assert result.dc_power_kw >= result.ac_power_kw
    assert result.ac_power_kw <= INVERTERS["sma_core1_stp50_41"].rated_ac_power_kw
    assert result.clipped_power_kw >= 0 and result.inverter_loss_kw >= 0
    converted = result.dc_power_kw * INVERTERS["sma_core1_stp50_41"].constant_conversion_efficiency
    assert result.inverter_loss_kw == pytest.approx(result.dc_power_kw - converted)
    assert result.clipped_power_kw == pytest.approx(max(0, converted - result.ac_power_kw))


def test_open_meteo_hourly_radiation_uses_interval_midpoint_for_geometry():
    stamp = datetime(2025, 6, 21, 14, tzinfo=timezone(timedelta(hours=5)))
    assert solar_geometry_timestamp_for_hourly_radiation(stamp) == datetime(
        2025, 6, 21, 13, 30, tzinfo=timezone(timedelta(hours=5)))
    result = hourly_pv_output(stamp, 51.302445, 70.541645, 20, 800, 700, 100,
        PV_MODULES["trina_tsm_450_neg9r28"], 10, INVERTERS["sma_core1_stp50_41"], 1, 35, 180)
    assert result.weather_timestamp == stamp
    assert result.solar_geometry_timestamp == stamp - timedelta(minutes=30)
    assert result.poa_irradiance_w_m2 >= 0


def test_sunrise_boundary_keeps_alignment_and_finite_poa():
    stamp = datetime(2025, 6, 21, 5, tzinfo=timezone(timedelta(hours=5)))
    result = hourly_pv_output(stamp, 51.302445, 70.541645, 10, 10, 0, 10,
        PV_MODULES["rec_alpha_pure_rx_470"], 1, INVERTERS["sma_core1_stp50_41"], 1, 35, 180)
    assert result.weather_timestamp == stamp
    assert result.solar_geometry_timestamp.utcoffset() == timedelta(hours=5)
    assert 0 <= result.poa_irradiance_w_m2 < float("inf")


def test_naive_radiation_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        solar_geometry_timestamp_for_hourly_radiation(datetime(2025, 1, 1, 12))


def test_invalid_inverter_efficiency_rejected():
    with pytest.raises(ValidationError):
        values = INVERTERS["sma_core1_stp50_41"].model_dump()
        values["maximum_efficiency"] = 1.1
        InverterSpec.model_validate(values)


def test_battery_limits_efficiency_and_inventory_tracking():
    config = BatteryConfig(capacity_kwh=10, initial_soc_kwh=5, minimum_soc_kwh=1,
        maximum_charge_kw=2, maximum_discharge_kw=3, charging_efficiency=.8,
        discharging_efficiency=.9)
    battery = BatteryState(config)
    discharge = battery.discharge(10)
    assert discharge.bus_energy_kwh == pytest.approx(3)
    assert discharge.from_initial_inventory_kwh == pytest.approx(3)
    assert discharge.from_simulation_charge_kwh == 0
    charge = battery.charge(10)
    assert charge.bus_energy_kwh == pytest.approx(2)
    assert battery.soc_kwh <= config.capacity_kwh


def test_battery_cannot_cross_minimum_or_maximum_soc():
    config = BatteryConfig(capacity_kwh=2, initial_soc_kwh=1, minimum_soc_kwh=.5,
        maximum_charge_kw=100, maximum_discharge_kw=100, charging_efficiency=.5,
        discharging_efficiency=.5)
    battery = BatteryState(config)
    assert battery.discharge(100).bus_energy_kwh == pytest.approx(.25)
    assert battery.soc_kwh == pytest.approx(.5)
    battery.charge(100)
    assert battery.soc_kwh == pytest.approx(2)
