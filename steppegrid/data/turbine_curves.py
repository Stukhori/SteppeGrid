"""Load generic empirical or synthetic turbine curves from CSV."""

import csv
from pathlib import Path

from steppegrid.simulation.models import PowerCurvePoint, WindTurbineConfig


class TurbineCurveError(ValueError):
    pass


def load_turbine_curve_csv(
    path: str | Path,
    *,
    name: str,
    turbine_count: int = 1,
    manufacturer: str | None = None,
    rated_power_kw: float | None = None,
    source: str | None = None,
    measurement_or_datasheet: str | None = None,
    notes: str | None = None,
) -> WindTurbineConfig:
    curve_path = Path(path)
    if not curve_path.is_file():
        raise TurbineCurveError(f"turbine curve CSV does not exist: {curve_path}")
    points: list[PowerCurvePoint] = []
    with curve_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["wind_speed_m_s", "power_kw"]:
            raise TurbineCurveError("turbine curve columns must be: wind_speed_m_s,power_kw")
        for row_number, row in enumerate(reader, start=2):
            if not row["wind_speed_m_s"] or not row["power_kw"]:
                raise TurbineCurveError(f"row {row_number}: missing turbine curve value")
            try:
                points.append(
                    PowerCurvePoint(
                        wind_speed_m_s=float(row["wind_speed_m_s"]),
                        electrical_output_kw=float(row["power_kw"]),
                    )
                )
            except ValueError as error:
                raise TurbineCurveError(f"row {row_number}: invalid turbine curve value") from error
    try:
        return WindTurbineConfig(
            name=name,
            power_curve=points,
            turbine_count=turbine_count,
            manufacturer=manufacturer,
            rated_power_kw=rated_power_kw,
            source=source or f"CSV file: {curve_path.name}",
            measurement_or_datasheet=measurement_or_datasheet,
            notes=notes,
        )
    except ValueError as error:
        raise TurbineCurveError(f"invalid turbine curve: {error}") from error
