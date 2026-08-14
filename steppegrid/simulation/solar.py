"""Initial transparent solar PV model."""

from steppegrid.simulation.models import SolarArrayConfig

REFERENCE_IRRADIANCE_W_M2 = 1000.0


def electrical_output_kw(irradiance_w_m2: float, array: SolarArrayConfig) -> float:
    """Scale DC rating by irradiance and a configurable aggregate performance ratio."""
    unbounded_output = (
        array.dc_capacity_kw
        * irradiance_w_m2
        / REFERENCE_IRRADIANCE_W_M2
        * array.performance_ratio
    )
    return min(array.dc_capacity_kw, unbounded_output)
