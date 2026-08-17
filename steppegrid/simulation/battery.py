"""Battery state transitions with explicit bus/storage energy accounting."""

from dataclasses import dataclass

from steppegrid.simulation.models import BatteryConfig


@dataclass(frozen=True)
class BatteryFlow:
    bus_energy_kwh: float
    storage_change_kwh: float
    loss_kwh: float
    from_initial_inventory_kwh: float = 0.0
    from_simulation_charge_kwh: float = 0.0


class BatteryState:
    def __init__(self, config: BatteryConfig) -> None:
        self.config = config
        self.soc_kwh = config.initial_soc_kwh
        self.initial_inventory_remaining_kwh = config.initial_soc_kwh - config.minimum_soc_kwh
        self.simulation_charged_inventory_kwh = 0.0

    def charge(self, available_kwh: float, duration_hours: float = 1.0) -> BatteryFlow:
        storage_room_kwh = self.config.capacity_kwh - self.soc_kwh
        bus_limit_kwh = min(available_kwh, self.config.maximum_charge_kw * duration_hours)
        bus_energy_kwh = min(bus_limit_kwh, storage_room_kwh / self.config.charging_efficiency)
        storage_change_kwh = bus_energy_kwh * self.config.charging_efficiency
        self.soc_kwh += storage_change_kwh
        self.simulation_charged_inventory_kwh += storage_change_kwh
        return BatteryFlow(bus_energy_kwh, storage_change_kwh, bus_energy_kwh - storage_change_kwh)

    def discharge(self, required_kwh: float, duration_hours: float = 1.0) -> BatteryFlow:
        removable_storage_kwh = self.soc_kwh - self.config.minimum_soc_kwh
        bus_limit_kwh = min(required_kwh, self.config.maximum_discharge_kw * duration_hours)
        bus_energy_kwh = min(bus_limit_kwh, removable_storage_kwh * self.config.discharging_efficiency)
        storage_change_kwh = -(bus_energy_kwh / self.config.discharging_efficiency)
        removed = -storage_change_kwh
        from_sim_storage = min(removed, self.simulation_charged_inventory_kwh)
        self.simulation_charged_inventory_kwh -= from_sim_storage
        from_initial_storage = removed - from_sim_storage
        self.initial_inventory_remaining_kwh = max(0.0, self.initial_inventory_remaining_kwh - from_initial_storage)
        self.soc_kwh += storage_change_kwh
        return BatteryFlow(bus_energy_kwh, storage_change_kwh, removed - bus_energy_kwh,
            from_initial_storage * self.config.discharging_efficiency,
            from_sim_storage * self.config.discharging_efficiency)
