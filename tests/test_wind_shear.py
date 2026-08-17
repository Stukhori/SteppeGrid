import math

import pytest

from steppegrid.benchmarks.wind_shear import (
    GENERIC_SHEAR_EXPONENT, MINIMUM_SHEAR_WIND_SPEED_M_S,
    estimate_two_height_shear, reconstruct_10m_diagnostics,
)
from steppegrid.simulation.wind import DEFAULT_WIND_SHEAR_EXPONENT, wind_speed_at_hub_height


def test_known_two_height_relationship_recovers_alpha():
    expected=.23
    wind10=[1,2,3,4,5]
    wind100=[v*10**expected for v in wind10]
    result=estimate_two_height_shear(wind10,wind100)
    assert result.exponent==pytest.approx(expected)
    assert result.valid_pairs==5


def test_zero_near_zero_nonfinite_and_negative_shear_handling_is_explicit():
    result=estimate_two_height_shear(
        [0,.49,1,2,3,float("nan")],
        [0,1,2,1.5,6,7],
    )
    assert result.excluded_near_zero_pairs==2
    assert result.excluded_nonfinite_pairs==1
    assert result.valid_pairs==3
    assert result.pairs_100m_not_above_10m==2  # equal zero and retained 1.5 < 2
    assert result.minimum_hourly_exponent<0
    assert result.minimum_wind_speed_m_s==MINIMUM_SHEAR_WIND_SPEED_M_S


def test_estimator_is_deterministic():
    first=estimate_two_height_shear([1,2,3],[2,4,6])
    second=estimate_two_height_shear([1,2,3],[2,4,6])
    assert first==second


@pytest.mark.parametrize("left,right", [([0,.1],[0,.2]),([1],[2]),([1,2],[2])])
def test_insufficient_or_misaligned_data_fails_clearly(left,right):
    with pytest.raises(ValueError):
        estimate_two_height_shear(left,right)


def test_reconstruction_diagnostics_recover_known_profile():
    alpha=.2; wind10=[1,2,4,8]; wind100=[v*10**alpha for v in wind10]
    diagnostics=reconstruct_10m_diagnostics(wind10,wind100,alpha)
    assert diagnostics["mae_m_s"]==pytest.approx(0,abs=1e-12)
    assert diagnostics["rmse_m_s"]==pytest.approx(0,abs=1e-12)


def test_phase8_generic_one_seventh_fallback_remains_unchanged():
    assert DEFAULT_WIND_SHEAR_EXPONENT==GENERIC_SHEAR_EXPONENT==pytest.approx(1/7)
    assert wind_speed_at_hub_height(8,50)==pytest.approx(8*(50/100)**(1/7))
