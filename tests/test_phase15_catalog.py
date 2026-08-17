import math

import pytest

from steppegrid.equipment.catalog import (
    BATTERIES,
    INVERTERS,
    PV_MODULES,
    WIND_TURBINES,
    EquipmentCatalogVersion,
    PLANNER_V2,
    RODINA_FROZEN_V1,
    get_equipment_catalog,
)
from steppegrid.equipment.models import CutOutBehavior
from steppegrid.optimization.core import dispatch
from steppegrid.optimization.economics import EconomicsVersion
from steppegrid.benchmarks.phase9 import benchmark_pv, load_phase9_weather
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.simulation.wind import commercial_turbine_output_kw


def _scenario(catalog_version):
    return PlanningScenario(
        name="catalog hash",
        site=PlanningSite(preset=SitePreset.SHAMSHI, name="Shamshi", latitude=50.578333, longitude=57.544722),
        demand=DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            annual_kwh=500_000,
            method_notes="deterministic test",
        ),
        reliability_target=.95,
        technologies=TechnologySelection(wind_keys=("sd6",)),
        equipment_catalog_version=catalog_version,
    )


def test_v1_is_exact_frozen_catalog_and_v2_is_strict_superset():
    assert set(RODINA_FROZEN_V1.wind_turbines) == set(WIND_TURBINES) == {
        "skystream_3_7", "sd6", "bergey_excel_15"
    }
    assert set(RODINA_FROZEN_V1.pv_modules) == set(PV_MODULES)
    assert set(RODINA_FROZEN_V1.inverters) == set(INVERTERS)
    assert set(RODINA_FROZEN_V1.batteries) == set(BATTERIES)
    assert set(PLANNER_V2.wind_turbines) > set(RODINA_FROZEN_V1.wind_turbines)
    assert set(PLANNER_V2.inverters) > set(RODINA_FROZEN_V1.inverters)
    assert set(PLANNER_V2.batteries) > set(RODINA_FROZEN_V1.batteries)
    assert get_equipment_catalog("RODINA_FROZEN_V1") is RODINA_FROZEN_V1
    with pytest.raises(TypeError):
        RODINA_FROZEN_V1.wind_turbines["new"] = PLANNER_V2.wind_turbines["sd6"]


def test_catalog_version_changes_scenario_hash():
    assert _scenario(EquipmentCatalogVersion.RODINA_FROZEN_V1).input_hash != _scenario(EquipmentCatalogVersion.PLANNER_V2).input_hash
    planner = _scenario(EquipmentCatalogVersion.PLANNER_V2)
    frozen_economics = planner.model_copy(update={"economics_version": EconomicsVersion.PHASE10_FROZEN_ECONOMICS_V1})
    assert planner.input_hash != frozen_economics.input_hash


@pytest.mark.parametrize("key,source_speed,source_power", [
    ("northern_power_nps_100c_21", 5.0, 10.5),
    ("leitwind_ltw42_250", 8.0, 190.0),
])
def test_new_wind_curves_and_generation_are_valid_and_deterministic(key, source_speed, source_power):
    turbine = PLANNER_V2.wind_turbines[key]
    speeds = [point.wind_speed_m_s for point in turbine.power_curve]
    powers = [point.electrical_output_kw for point in turbine.power_curve]
    assert speeds == sorted(set(speeds))
    assert min(powers) >= 0
    assert max(powers) <= turbine.maximum_curve_output_kw
    assert turbine.planning_hub_height_m in turbine.supported_hub_heights_m
    assert turbine.cut_out_behavior is CutOutBehavior.SPEED_THRESHOLD
    low = commercial_turbine_output_kw(0, turbine, turbine.planning_hub_height_m, 0)
    high = commercial_turbine_output_kw(turbine.cut_out_wind_speed_m_s + 1, turbine, turbine.planning_hub_height_m, 0)
    midpoint = commercial_turbine_output_kw(4.5, turbine, turbine.planning_hub_height_m, 0)
    assert low == high == 0
    assert commercial_turbine_output_kw(source_speed, turbine, turbine.planning_hub_height_m, 0) == source_power
    assert 0 <= midpoint <= turbine.maximum_curve_output_kw
    trace1 = [commercial_turbine_output_kw(speed, turbine, turbine.planning_hub_height_m, 0) for speed in [0, 3, 5, 8, 12, 30] * 1460]
    trace2 = [commercial_turbine_output_kw(speed, turbine, turbine.planning_hub_height_m, 0) for speed in [0, 3, 5, 8, 12, 30] * 1460]
    assert trace1 == trace2
    capacity_factor = math.fsum(trace1) / (turbine.rated_power_kw * 8760)
    assert 0 <= capacity_factor <= 1


def test_smaller_pv_block_uses_verified_inverter_in_existing_physical_model():
    inverter = PLANNER_V2.inverters["sma_sunny_tripower_x_25"]
    assert inverter.rated_ac_power_kw == 25
    assert inverter.maximum_dc_array_power_kw == 37.5
    assert inverter.constant_conversion_efficiency == pytest.approx(.98)
    modules = {"trina_tsm_450_neg9r28": PLANNER_V2.pv_modules["trina_tsm_450_neg9r28"]}
    inverters = {"sma_sunny_tripower_x_25": inverter}
    first_metadata, first_profiles = benchmark_pv(load_phase9_weather(), modules=modules, inverters=inverters)
    second_metadata, second_profiles = benchmark_pv(load_phase9_weather(), modules=modules, inverters=inverters)
    key = "trina_tsm_450_neg9r28__sma_sunny_tripower_x_25"
    assert first_metadata == second_metadata
    assert first_profiles == second_profiles
    assert first_metadata[key]["dc_capacity_kw"] == pytest.approx(24.75)
    assert 0 < max(first_profiles[key]) <= inverter.rated_ac_power_kw


@pytest.mark.parametrize("key,energy,power", [
    ("sungrow_powerstack_st255_2h", 257, 125),
    ("sungrow_powerstack_st510_4h", 514, 125),
])
def test_new_battery_parameters_initial_inventory_and_conservation(key, energy, power):
    battery = PLANNER_V2.batteries[key]
    assert battery.nominal_energy_capacity_kwh == energy
    assert battery.usable_energy_capacity_kwh == energy
    assert battery.maximum_charge_power_kw == power
    assert battery.maximum_discharge_power_kw == power
    assert battery.minimum_soc_fraction == 0
    assert battery.maximum_soc_fraction == 1
    assert battery.round_trip_efficiency == pytest.approx(.90)
    result = dispatch([0, power, power], [power, 0, 0], battery, 1)
    assert result["initial_soc_kwh"] == 0
    assert result["initial_inventory_discharge_kwh"] == 0
    assert abs(result["generation_balance_error_kwh"]) <= 1e-6
    assert abs(result["load_balance_error_kwh"]) <= 1e-6
    assert abs(result["storage_balance_error_kwh"]) <= 1e-6
    assert result == dispatch([0, power, power], [power, 0, 0], battery, 1)


def test_all_v2_additions_have_authoritative_parameter_provenance():
    additions = (
        [PLANNER_V2.wind_turbines[key] for key in set(PLANNER_V2.wind_turbines) - set(WIND_TURBINES)]
        + [PLANNER_V2.inverters[key] for key in set(PLANNER_V2.inverters) - set(INVERTERS)]
        + [PLANNER_V2.batteries[key] for key in set(PLANNER_V2.batteries) - set(BATTERIES)]
    )
    for item in additions:
        assert item.provenance
        assert all(source.source_url.startswith("https://") for source in item.provenance)
        assert all(source.parameters_supported for source in item.provenance)
        assert all(source.category is not None for source in item.provenance)
