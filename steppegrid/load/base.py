"""Load-provider contract consumed by scenario construction."""

from datetime import datetime
from typing import Protocol

from steppegrid.simulation.models import LoadDataset


class LoadProvider(Protocol):
    def get_hourly_load(self, start: datetime, end: datetime) -> LoadDataset:
        """Return normalized hourly load for the half-open interval [start, end)."""
        ...
