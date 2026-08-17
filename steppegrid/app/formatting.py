"""Consistent display labels and units for the planning application."""

from __future__ import annotations


def energy(kwh: float) -> str:
    if abs(kwh) >= 1_000_000:
        return f"{kwh / 1_000_000:,.2f} GWh"
    if abs(kwh) >= 1_000:
        return f"{kwh / 1_000:,.1f} MWh"
    return f"{kwh:,.1f} kWh"


def power(kw: float) -> str:
    return f"{kw / 1_000:,.2f} MW" if abs(kw) >= 1_000 else f"{kw:,.1f} kW"


def money(usd: float) -> str:
    return f"${usd / 1_000_000:,.2f}M" if abs(usd) >= 1_000_000 else f"${usd:,.0f}"


def percent(fraction: float, digits: int = 2) -> str:
    return f"{100 * fraction:.{digits}f}%"


def readable(key: str) -> str:
    return key.replace("_", " ").title()


RECONSTRUCTION_NOTICE = (
    "Rodina demand is a deterministic hourly reconstruction of published monthly energy, "
    "not measured hourly demand. Served-energy fraction is annual energy service, not uptime."
)

SCENARIO_NOTICE = (
    "Sensitivity ranges are deterministic research scenarios, not confidence intervals or "
    "probability distributions. Fixed-design results replay the frozen designs; adaptive results "
    "use saved candidate reselection, not global re-optimization."
)
