import pytest

from steppegrid.data.turbine_curves import TurbineCurveError, load_turbine_curve_csv
from steppegrid.simulation.wind import electrical_output_kw


def test_loaded_curve_exact_interpolated_and_bounds(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("wind_speed_m_s,power_kw\n3,0\n5,1\n10,2\n25,0\n", encoding="utf-8")
    turbine = load_turbine_curve_csv(path, name="synthetic test")
    assert electrical_output_kw(5, turbine) == pytest.approx(1)
    assert electrical_output_kw(7.5, turbine) == pytest.approx(1.5)
    assert electrical_output_kw(1, turbine) == pytest.approx(0)
    assert electrical_output_kw(30, turbine) == pytest.approx(0)


def test_loaded_curve_rejects_unsorted_points(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("wind_speed_m_s,power_kw\n5,1\n3,0\n", encoding="utf-8")
    with pytest.raises(TurbineCurveError, match="strictly increasing"):
        load_turbine_curve_csv(path, name="invalid")
