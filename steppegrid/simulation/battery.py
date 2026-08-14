"""Battery state transitions with explicit bus/storage energy accounting."""

from dataclasses import dataclass

from steppegrid.simulation.models import BatteryConfig


@dataclass(frozen=True)
class BatteryFlow:
    bus_energy_kwh: float
    storage_change_kwh: float
    loss_kwh: float


class BatteryState:
    def __init__(self, config: BatteryConfig) -> None:
        self.config = config
        self.soc_kwh = config.initial_soc_kwh

    def charge(self, available_kwh: float, duration_hours: float = 1.0) -> BatteryFlow:
        storage_room_kwh = self.config.capacity_kwh - self.soc_kwh
        bus_limit_kwh = min(available_kwh, self.config.maximum_charge_kw * duration_hours)
        bus_energy_kwh = min(bus_limit_kwh, storage_room_kwh / self.config.charging_efficiency)
        storage_change_kwh = bus_energy_kwh * self.config.charging_efficiency
        self.soc_kwh += storage_change_kwh
        return BatteryFlow(bus_energy_kwh, storage_change_kwh, bus_energy_kwh - storage_change_kwh)

    def discharge(self, required_kwh: float, duration_hours: float = 1.0) -> BatteryFlow:
        removable_storage_kwh = self.soc_kwh - self.config.minimum_soc_kwh
        bus_limit_kwh = min(required_kwh, self.config.maximum_discharge_kw * duration_hours)
        bus_energy_kwh = min(bus_limit_kwh, removable_storage_kwh * self.config.discharging_efficiency)
        storage_change_kwh = -(bus_energy_kwh / self.config.discharging_efficiency)
        self.soc_kwh += storage_change_kwh
        return BatteryFlow(bus_energy_kwh, storage_change_kwh, -storage_change_kwh - bus_energy_kwh)
