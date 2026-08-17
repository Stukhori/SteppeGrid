"""Deterministic renewable-first hourly dispatch."""

from steppegrid.simulation.battery import BatteryState
from steppegrid.simulation.metrics import aggregate
from steppegrid.simulation.models import HourlyResult, SimulationInput, SimulationResult
from steppegrid.simulation.solar import electrical_output_kw as solar_output_kw
from steppegrid.simulation.wind import electrical_output_kw as wind_output_kw

TIMESTEP_HOURS = 1.0


def simulate(inputs: SimulationInput) -> SimulationResult:
    battery = BatteryState(inputs.battery)
    hourly: list[HourlyResult] = []
    total_load = (
        inputs.load.total_load_kwh
        if hasattr(inputs.load, "total_load_kwh")
        else inputs.load.demand_kwh
    )
    critical_load = (
        inputs.load.critical_load_kwh
        if hasattr(inputs.load, "critical_load_kwh")
        else inputs.load.critical_demand_kwh
    )

    for index, timestamp in enumerate(inputs.load.timestamps):
        demand_kwh = total_load[index]
        critical_demand_kwh = critical_load[index] if critical_load is not None else 0.0
        solar_kwh = solar_output_kw(
            inputs.weather.solar_irradiance_w_m2[index], inputs.solar_array
        ) * TIMESTEP_HOURS
        wind_kwh = wind_output_kw(
            inputs.weather.wind_speed_m_s[index], inputs.wind_turbine
        ) * TIMESTEP_HOURS
        renewable_kwh = solar_kwh + wind_kwh

        renewable_direct_kwh = min(demand_kwh, renewable_kwh)
        surplus_kwh = renewable_kwh - renewable_direct_kwh
        deficit_kwh = demand_kwh - renewable_direct_kwh
        soc_start_kwh = battery.soc_kwh

        charge = battery.charge(surplus_kwh, TIMESTEP_HOURS)
        discharge = battery.discharge(deficit_kwh, TIMESTEP_HOURS)
        remaining_deficit_kwh = deficit_kwh - discharge.bus_energy_kwh
        grid_available = inputs.grid.available[index]
        grid_import_kwh = remaining_deficit_kwh if grid_available else 0.0
        unserved_kwh = remaining_deficit_kwh - grid_import_kwh
        curtailed_kwh = surplus_kwh - charge.bus_energy_kwh
        served_kwh = demand_kwh - unserved_kwh
        if inputs.outage_load_policy == "critical_first" and not grid_available:
            critical_served_kwh = min(critical_demand_kwh, served_kwh)
        else:
            critical_served_kwh = (
                critical_demand_kwh * served_kwh / demand_kwh if demand_kwh else 0.0
            )
        critical_unserved_kwh = critical_demand_kwh - critical_served_kwh

        hourly.append(
            HourlyResult(
                timestamp=timestamp,
                demand_kwh=demand_kwh,
                critical_demand_kwh=critical_demand_kwh,
                critical_served_kwh=critical_served_kwh,
                critical_unserved_kwh=critical_unserved_kwh,
                solar_generation_kwh=solar_kwh,
                wind_generation_kwh=wind_kwh,
                renewable_generation_kwh=renewable_kwh,
                renewable_direct_to_load_kwh=renewable_direct_kwh,
                battery_charge_kwh=charge.bus_energy_kwh,
                battery_discharge_kwh=discharge.bus_energy_kwh,
                battery_soc_start_kwh=soc_start_kwh,
                battery_soc_end_kwh=battery.soc_kwh,
                battery_loss_kwh=charge.loss_kwh + discharge.loss_kwh,
                battery_discharge_from_initial_inventory_kwh=discharge.from_initial_inventory_kwh,
                battery_discharge_from_simulation_charge_kwh=discharge.from_simulation_charge_kwh,
                grid_available=grid_available,
                grid_import_kwh=grid_import_kwh,
                curtailed_energy_kwh=curtailed_kwh,
                unserved_energy_kwh=unserved_kwh,
            )
        )

    return SimulationResult(hourly=hourly, metrics=aggregate(hourly))
