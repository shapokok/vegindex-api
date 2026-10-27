"""FastAPI application exposing the vegetation index calculations."""

import csv
import io
import os

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, status
from pydantic import ValidationError

from vegindex import __version__, indices
from vegindex.schemas import (
    BANDS,
    MAX_OBSERVATIONS,
    HealthResponse,
    IndexResult,
    IndicesResponse,
    Observation,
    ObservationList,
    VersionResponse,
)

MAX_CSV_BYTES = 5 * 1024 * 1024
CSV_COLUMNS = ("id", *BANDS)

app = FastAPI(
    title="vegindex-api",
    version=__version__,
    description="Compute NDVI, VARI and ExG vegetation indices for pixels or field observations.",
)


def _band(observations: list[Observation], name: str) -> np.ndarray:
    values = [getattr(obs, name) for obs in observations]
    return np.array([np.nan if v is None else v for v in values], dtype=np.float64)


def compute_indices(observations: list[Observation]) -> IndicesResponse:
    red, green, blue, nir = (_band(observations, band) for band in BANDS)
    has_nir = ~np.isnan(nir)
    has_rgb = ~(np.isnan(green) | np.isnan(blue))

    ndvi = indices.ndvi(nir, red)
    vari = indices.vari(red, green, blue)
    exg = indices.exg(red, green, blue)

    results = []
    for i, obs in enumerate(observations):
        ndvi_value = float(ndvi[i]) if has_nir[i] else None
        results.append(
            IndexResult(
                id=obs.id,
                ndvi=ndvi_value,
                ndvi_class=None if ndvi_value is None else indices.classify_ndvi(ndvi_value),
                vari=float(vari[i]) if has_rgb[i] else None,
                exg=float(exg[i]) if has_rgb[i] else None,
            )
        )
    return IndicesResponse(count=len(results), results=results)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _parse_csv(text: str) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise _unprocessable("CSV file is empty")

    # Map normalised column names (case/whitespace-insensitive) to the original header.
    columns = {
        name.strip().lower(): name
        for name in reader.fieldnames
        if name and name.strip().lower() in CSV_COLUMNS
    }
    if "red" not in columns:
        raise _unprocessable(f"CSV must have a 'red' column; supported columns: {CSV_COLUMNS}")

    observations = []
    try:
        for line, row in enumerate(reader, start=2):
            if len(observations) >= MAX_OBSERVATIONS:
                raise _unprocessable(f"CSV has more than {MAX_OBSERVATIONS} rows")
            data = {
                field: value.strip()
                for field, header in columns.items()
                if (value := row.get(header)) is not None and value.strip()
            }
            if not data:
                continue  # skip blank lines
            try:
                observations.append(Observation.model_validate(data))
            except ValidationError as exc:
                errors = "; ".join(
                    f"{'.'.join(map(str, err['loc'])) or 'row'}: {err['msg']}"
                    for err in exc.errors()
                )
                raise _unprocessable(f"line {line}: {errors}") from exc
    except csv.Error as exc:
        raise _unprocessable(f"malformed CSV: {exc}") from exc
    return observations


@app.get("/health", response_model=HealthResponse, tags=["service"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/version", response_model=VersionResponse, tags=["service"])
def get_version() -> VersionResponse:
    return VersionResponse(
        name="vegindex-api",
        version=__version__,
        commit=os.getenv("GIT_COMMIT", "unknown"),
    )


@app.post("/indices", response_model=IndicesResponse, tags=["indices"])
def indices_from_json(observations: ObservationList) -> IndicesResponse:
    """Compute indices for a JSON list of pixels/observations."""
    return compute_indices(observations)


@app.post("/indices/csv", response_model=IndicesResponse, tags=["indices"])
async def indices_from_csv(file: UploadFile) -> IndicesResponse:
    """Compute indices for an uploaded CSV with columns ``red`` and ``nir`` and/or ``green``,
    ``blue`` (optional ``id``). Header names are case-insensitive."""
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"CSV file exceeds {MAX_CSV_BYTES // (1024 * 1024)} MB",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _unprocessable("CSV file must be UTF-8 encoded") from exc
    return compute_indices(_parse_csv(text))
