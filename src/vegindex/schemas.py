"""Request and response models for the API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_OBSERVATIONS = 10_000

Reflectance = Annotated[float, Field(ge=0, allow_inf_nan=False)]

BANDS = ("red", "green", "blue", "nir")


class Observation(BaseModel):
    """A single pixel or field observation.

    ``red`` is always required. Provide ``nir`` to get NDVI and/or both
    ``green`` and ``blue`` to get VARI and ExG.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"id": "p1", "red": 0.2, "green": 0.5, "blue": 0.1, "nir": 0.8}]
        },
    )

    id: str | None = None
    red: Reflectance
    green: Reflectance | None = None
    blue: Reflectance | None = None
    nir: Reflectance | None = None

    @model_validator(mode="after")
    def _has_enough_bands(self) -> "Observation":
        if self.nir is None and (self.green is None or self.blue is None):
            raise ValueError("provide 'nir' for NDVI and/or both 'green' and 'blue' for VARI/ExG")
        return self


ObservationList = Annotated[list[Observation], Field(max_length=MAX_OBSERVATIONS)]


class IndexResult(BaseModel):
    id: str | None = None
    ndvi: float | None = None
    ndvi_class: Literal["no vegetation", "stressed", "healthy"] | None = None
    vari: float | None = None
    exg: float | None = None


class IndicesResponse(BaseModel):
    count: int
    results: list[IndexResult]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class VersionResponse(BaseModel):
    name: str
    version: str
    commit: str
