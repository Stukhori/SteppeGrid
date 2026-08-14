"""Helpers for constructing timestamp-aligned grid outage scenarios."""

from datetime import datetime

from steppegrid.simulation.models import GridAvailability, OutageInterval


def availability_with_outages(
    timestamps: list[datetime], outages: list[OutageInterval]
) -> GridAvailability:
    """Mark the grid unavailable in each start-inclusive, end-exclusive interval."""
    available = [
        not any(outage.start <= timestamp < outage.end for outage in outages)
        for timestamp in timestamps
    ]
    return GridAvailability(timestamps=timestamps, available=available)
