import pytest

from steppegrid.optimization.economics import (
    EconomicsVersion,
    battery_cost_assumption,
    system_cost,
    wind_cost_assumption,
)
from steppegrid.optimization.core import dispatch
from steppegrid.equipment.catalog import PLANNER_V2


def test_v1_economics_remain_frozen_and_v2_boundaries_are_deterministic():
    frozen = system_cost(wind_kw=250, pv_dc_kw=0, pv_ac_kw=0, battery_usable_kwh=0)
    assert frozen["reference_capex_basis"]["wind"] == "8425.0 USD/kW"
    assert wind_cost_assumption(20, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "distributed_wind_reference"
    assert wind_cost_assumption(20.0001, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "commercial_distributed_wind"
    assert wind_cost_assumption(100, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "commercial_distributed_wind"
    assert wind_cost_assumption(100.0001, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "large_distributed_wind"
    assert battery_cost_assumption(999.999, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "commercial_storage_under_1mwh"
    assert battery_cost_assumption(1000, EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2).scale_category == "generic_lithium_ion_storage_reference"


def test_economics_version_changes_cost_not_physical_dispatch():
    battery = PLANNER_V2.batteries["sungrow_powerstack_st255_2h"]
    physical_before = dispatch([100, 100], [200, 0], battery, 1)
    v1 = system_cost(wind_kw=250, pv_dc_kw=0, pv_ac_kw=0, battery_usable_kwh=257)
    v2 = system_cost(
        wind_kw=250, pv_dc_kw=0, pv_ac_kw=0, battery_usable_kwh=257,
        economics_version=EconomicsVersion.PLANNER_SCALE_AWARE_ECONOMICS_V2,
    )
    physical_after = dispatch([100, 100], [200, 0], battery, 1)
    assert physical_before == physical_after
    assert v1["net_present_cost_usd"] != pytest.approx(v2["net_present_cost_usd"])
    assert v2["reference_cost_base_years"] == {"wind": 2022, "battery": 2021}
