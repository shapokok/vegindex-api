"""Vegetation index formulas.

All functions accept scalars or array-like inputs (broadcast with numpy rules)
and return ``float64`` numpy arrays. Wherever a denominator is zero the index is
undefined; such elements are returned as ``0.0`` instead of ``inf``/``nan`` so the
results are always finite and JSON-serialisable.
"""

from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

# Denominators with an absolute value below this threshold are treated as zero.
EPS: Final = 1e-12

NDVI_STRESSED_MIN: Final = 0.2
NDVI_HEALTHY_MIN: Final = 0.5

NO_VEGETATION: Final = "no vegetation"
STRESSED: Final = "stressed"
HEALTHY: Final = "healthy"


def safe_divide(numerator: ArrayLike, denominator: ArrayLike) -> NDArray[np.float64]:
    """Element-wise ``numerator / denominator`` that yields 0.0 where the denominator is ~0."""
    num, den = np.broadcast_arrays(
        np.asarray(numerator, dtype=np.float64), np.asarray(denominator, dtype=np.float64)
    )
    out = np.zeros(num.shape, dtype=np.float64)
    np.divide(num, den, out=out, where=np.abs(den) >= EPS)
    return out


def ndvi(nir: ArrayLike, red: ArrayLike) -> NDArray[np.float64]:
    """Normalized Difference Vegetation Index: ``(NIR - Red) / (NIR + Red)``."""
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    return safe_divide(nir - red, nir + red)


def vari(red: ArrayLike, green: ArrayLike, blue: ArrayLike) -> NDArray[np.float64]:
    """Visible Atmospherically Resistant Index: ``(G - R) / (G + R - B)``."""
    red = np.asarray(red, dtype=np.float64)
    green = np.asarray(green, dtype=np.float64)
    blue = np.asarray(blue, dtype=np.float64)
    return safe_divide(green - red, green + red - blue)


def exg(red: ArrayLike, green: ArrayLike, blue: ArrayLike) -> NDArray[np.float64]:
    """Excess Green index on chromatic coordinates: ``2g - r - b``.

    ``r``, ``g`` and ``b`` are the bands normalised by ``R + G + B``, so the
    result does not depend on image brightness and lies in ``[-1, 2]`` for
    non-negative inputs.
    """
    red = np.asarray(red, dtype=np.float64)
    green = np.asarray(green, dtype=np.float64)
    blue = np.asarray(blue, dtype=np.float64)
    return safe_divide(2 * green - red - blue, red + green + blue)


def classify_ndvi(value: float) -> str:
    """Map an NDVI value to a vegetation class.

    ``< 0.2`` -> "no vegetation", ``0.2..0.5`` (inclusive) -> "stressed",
    ``> 0.5`` -> "healthy".
    """
    if value < NDVI_STRESSED_MIN:
        return NO_VEGETATION
    if value <= NDVI_HEALTHY_MIN:
        return STRESSED
    return HEALTHY
