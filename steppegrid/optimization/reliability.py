"""Explicit energy and optional outage-duration reliability constraints."""

from pydantic import Field
from steppegrid.simulation.models import DomainModel

class ReliabilityConstraints(DomainModel):
    minimum_served_fraction: float = Field(ge=0, le=1)
    max_loss_of_load_hours: int | None = Field(default=None, ge=0)
    max_continuous_deficit_hours: int | None = Field(default=None, ge=0)

def meets_reliability(metrics: dict, constraints: ReliabilityConstraints) -> bool:
    if metrics["served_fraction"] + 1e-12 < constraints.minimum_served_fraction: return False
    if constraints.max_loss_of_load_hours is not None and metrics["loss_of_load_hours"] > constraints.max_loss_of_load_hours: return False
    if constraints.max_continuous_deficit_hours is not None and metrics["longest_deficit_hours"] > constraints.max_continuous_deficit_hours: return False
    return True
