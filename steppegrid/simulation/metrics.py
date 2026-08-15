"""Aggregate transparent metrics from hourly simulation records."""

from steppegrid.simulation.models import AggregateMetrics, HourlyResult


def aggregate(hourly: list[HourlyResult]) -> AggregateMetrics:
    total_demand = sum(row.demand_kwh for row in hourly)
    unserved = sum(row.unserved_energy_kwh for row in hourly)
    renewable_to_load = sum(
        row.renewable_direct_to_load_kwh + row.battery_discharge_kwh for row in hourly
    )
    outage_rows = [row for row in hourly if not row.grid_available]
    outage_demand = sum(row.demand_kwh for row in outage_rows)
    outage_unserved = sum(row.unserved_energy_kwh for row in outage_rows)
    outage_served = outage_demand - outage_unserved
    outage_critical_demand = sum(row.critical_demand_kwh for row in outage_rows)
    outage_critical_served = sum(row.critical_served_kwh for row in outage_rows)
    outage_critical_unserved = sum(row.critical_unserved_kwh for row in outage_rows)
    return AggregateMetrics(
        total_demand_kwh=total_demand,
        solar_generation_kwh=sum(row.solar_generation_kwh for row in hourly),
        wind_generation_kwh=sum(row.wind_generation_kwh for row in hourly),
        renewable_generation_kwh=sum(row.renewable_generation_kwh for row in hourly),
        grid_import_kwh=sum(row.grid_import_kwh for row in hourly),
        battery_charge_kwh=sum(row.battery_charge_kwh for row in hourly),
        battery_discharge_kwh=sum(row.battery_discharge_kwh for row in hourly),
        battery_loss_kwh=sum(row.battery_loss_kwh for row in hourly),
        curtailed_energy_kwh=sum(row.curtailed_energy_kwh for row in hourly),
        unserved_energy_kwh=unserved,
        renewable_fraction=min(1.0, renewable_to_load / total_demand) if total_demand else 0.0,
        hours_with_unserved_load=sum(row.unserved_energy_kwh > 1e-9 for row in hourly),
        outage_demand_kwh=outage_demand,
        outage_served_energy_kwh=outage_served,
        outage_unserved_energy_kwh=outage_unserved,
        outage_total_demand_kwh=outage_demand,
        outage_total_served_kwh=outage_served,
        outage_total_unserved_kwh=outage_unserved,
        outage_critical_demand_kwh=outage_critical_demand,
        outage_critical_served_kwh=outage_critical_served,
        outage_critical_unserved_kwh=outage_critical_unserved,
        critical_load_served_fraction=(
            outage_critical_served / outage_critical_demand
            if outage_critical_demand
            else 0.0
        ),
    )
