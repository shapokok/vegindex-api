import numpy as np
import pytest

from vegindex.indices import (
    HEALTHY,
    NO_VEGETATION,
    STRESSED,
    classify_ndvi,
    exg,
    ndvi,
    safe_divide,
    vari,
)

# --- hand-computed examples -------------------------------------------------


def test_ndvi_hand_example():
    # (0.8 - 0.2) / (0.8 + 0.2) = 0.6
    assert ndvi(0.8, 0.2) == pytest.approx(0.6)


def test_ndvi_negative_for_water_like_pixel():
    # (0.1 - 0.3) / (0.1 + 0.3) = -0.5
    assert ndvi(0.1, 0.3) == pytest.approx(-0.5)


def test_vari_hand_example():
    # (0.5 - 0.3) / (0.5 + 0.3 - 0.2) = 0.2 / 0.6 = 1/3
    assert vari(red=0.3, green=0.5, blue=0.2) == pytest.approx(1 / 3)


def test_exg_hand_example():
    # sum = 100; r=0.2, g=0.5, b=0.3 -> 2*0.5 - 0.2 - 0.3 = 0.5
    assert exg(red=20, green=50, blue=30) == pytest.approx(0.5)


def test_exg_is_brightness_invariant():
    assert exg(20, 50, 30) == pytest.approx(exg(40, 100, 60))


def test_vectorised_inputs():
    nir = np.array([0.8, 0.5, 0.1])
    red = np.array([0.2, 0.5, 0.3])
    np.testing.assert_allclose(ndvi(nir, red), [0.6, 0.0, -0.5])


# --- edge cases ---------------------------------------------------------------


def test_ndvi_zero_denominator_returns_zero():
    assert ndvi(0, 0) == 0.0


def test_vari_zero_denominator_returns_zero():
    # G + R - B = 0.2 + 0.3 - 0.5 = 0
    assert vari(red=0.3, green=0.2, blue=0.5) == 0.0


def test_exg_black_pixel_returns_zero():
    assert exg(0, 0, 0) == 0.0


def test_zero_denominator_in_array_does_not_affect_other_elements():
    result = ndvi([0.0, 0.8], [0.0, 0.2])
    np.testing.assert_allclose(result, [0.0, 0.6])
    assert np.all(np.isfinite(result))


def test_near_zero_denominator_is_treated_as_zero():
    assert safe_divide(1.0, 1e-15) == 0.0


def test_ndvi_extremes():
    assert ndvi(1.0, 0.0) == pytest.approx(1.0)
    assert ndvi(0.0, 1.0) == pytest.approx(-1.0)


def test_returns_float64_array():
    result = ndvi([1, 2], [1, 0])
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float64


# --- classification -------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1.0, NO_VEGETATION),
        (0.0, NO_VEGETATION),
        (0.199, NO_VEGETATION),
        (0.2, STRESSED),
        (0.35, STRESSED),
        (0.5, STRESSED),
        (0.501, HEALTHY),
        (1.0, HEALTHY),
    ],
)
def test_classify_ndvi(value, expected):
    assert classify_ndvi(value) == expected
