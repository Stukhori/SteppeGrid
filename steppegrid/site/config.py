"""Typed pilot-site configuration and placeholder-aware loading."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import model_validator

from steppegrid.simulation.models import DomainModel, Location


class PilotSiteConfigError(ValueError):
    pass


class PilotWeatherConfig(DomainModel):
    provider: Literal["open-meteo"] = "open-meteo"
    model: Literal["era5"] = "era5"
    start_date: date
    end_date: date
    cache_directory: str = "../../data/weather/cache"

    @model_validator(mode="after")
    def require_complete_calendar_year(self) -> PilotWeatherConfig:
        if (self.start_date.month, self.start_date.day) != (1, 1):
            raise ValueError("pilot weather start_date must be January 1")
        expected_end = date(self.start_date.year + 1, 1, 1)
        if self.end_date != expected_end:
            raise ValueError("pilot weather end_date must be January 1 of the next year")
        return self


class PilotSiteConfig(DomainModel):
    site: Location
    weather: PilotWeatherConfig
    output_directory: str = "../../outputs/pilot_site"

    @model_validator(mode="after")
    def require_named_kazakhstan_site(self) -> PilotSiteConfig:
        if not self.site.name or not self.site.name.strip():
            raise ValueError("pilot site name must not be empty")
        if self.site.country.casefold() != "kazakhstan":
            raise ValueError("pilot site country must be Kazakhstan")
        return self

    @property
    def start_datetime(self) -> datetime:
        return datetime.combine(self.weather.start_date, time.min, tzinfo=timezone.utc)

    @property
    def end_datetime(self) -> datetime:
        return datetime.combine(self.weather.end_date, time.min, tzinfo=timezone.utc)


def _placeholder_paths(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_placeholder_paths(child, path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(_placeholder_paths(child, f"{prefix}[{index}]"))
        return paths
    return [prefix] if value == "REPLACE_ME" else []


def load_pilot_site_config(path: str | Path) -> PilotSiteConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise PilotSiteConfigError(f"pilot-site config does not exist: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PilotSiteConfigError("pilot-site config must contain a mapping")
    placeholders = _placeholder_paths(raw)
    if placeholders:
        raise PilotSiteConfigError(
            "replace pilot-site placeholders before analysis: " + ", ".join(placeholders)
        )
    try:
        return PilotSiteConfig.model_validate(raw)
    except ValueError as error:
        raise PilotSiteConfigError(f"invalid pilot-site config: {error}") from error
