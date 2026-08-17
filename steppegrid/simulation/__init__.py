"""Public simulation interfaces."""

from steppegrid.simulation.models import (
    BatteryConfig,
    DataProvenance,
    GridAvailability,
    LoadProfile,
    Location,
    OutageInterval,
    PowerCurvePoint,
    SimulationInput,
    SimulationResult,
    SolarArrayConfig,
    WeatherSeries,
    WeatherDataset,
    WindTurbineConfig,
)

def simulate(*args, **kwargs):
    """Lazily import the simulator so equipment models can share domain types safely."""
    from steppegrid.simulation.simulator import simulate as _simulate
    return _simulate(*args, **kwargs)

__all__ = [
    "BatteryConfig",
    "DataProvenance",
    "GridAvailability",
    "LoadProfile",
    "Location",
    "OutageInterval",
    "PowerCurvePoint",
    "SimulationInput",
    "SimulationResult",
    "SolarArrayConfig",
    "WeatherSeries",
    "WeatherDataset",
    "WindTurbineConfig",
    "simulate",
]
