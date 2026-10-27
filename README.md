# vegindex-api

A small REST API that computes vegetation indices — **NDVI**, **VARI** and **ExG** — from pixel
or field-observation reflectance values and classifies vegetation health by NDVI.

Built with Python 3.12, FastAPI, numpy and pydantic; managed with [uv](https://docs.astral.sh/uv/).

## Indices

| Index | Formula | Needs |
|-------|---------|-------|
| NDVI  | `(NIR − Red) / (NIR + Red)` | `red`, `nir` |
| VARI  | `(Green − Red) / (Green + Red − Blue)` | `red`, `green`, `blue` |
| ExG   | `2g − r − b`, where `r, g, b = R, G, B / (R + G + B)` | `red`, `green`, `blue` |

If a denominator is zero (e.g. a black pixel), the index is returned as `0.0` instead of
`inf`/`NaN`.

### NDVI classification

| NDVI | Class |
|------|-------|
| `< 0.2` | `no vegetation` |
| `0.2 … 0.5` (inclusive) | `stressed` |
| `> 0.5` | `healthy` |

## Getting started

```sh
uv sync                                    # create .venv and install dependencies
uv run uvicorn vegindex.api:app --reload   # http://localhost:8000
```

Interactive API docs are served at <http://localhost:8000/docs>.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check → `{"status": "ok"}` |
| `GET`  | `/version` | App name, version and git commit (from the `GIT_COMMIT` env var) |
| `POST` | `/indices` | Compute indices for a JSON list of observations |
| `POST` | `/indices/csv` | Compute indices for an uploaded CSV file |

### Observations

Each observation has a required `red` band and optional `green`, `blue`, `nir` and `id`.
Provide `nir` to get NDVI and/or both `green` and `blue` to get VARI and ExG; indices that
cannot be computed are returned as `null`. Band values must be finite and non-negative.
Up to 10,000 observations per request.

```sh
curl -X POST localhost:8000/indices \
  -H 'Content-Type: application/json' \
  -d '[{"id": "p1", "red": 20, "green": 50, "blue": 30, "nir": 80},
       {"id": "p2", "red": 0.3, "nir": 0.45}]'
```

```json
{
  "count": 2,
  "results": [
    {"id": "p1", "ndvi": 0.6, "ndvi_class": "healthy", "vari": 0.75, "exg": 0.5},
    {"id": "p2", "ndvi": 0.2, "ndvi_class": "stressed", "vari": null, "exg": null}
  ]
}
```

### CSV upload

The CSV must be UTF-8 and have a header row with a `red` column plus `nir` and/or
`green`, `blue`; `id` is optional. Header names are case-insensitive, other columns are
ignored, maximum file size is 5 MB.

```csv
id,red,green,blue,nir
p1,20,50,30,80
p2,0.3,,,0.45
```

```sh
curl -F file=@pixels.csv localhost:8000/indices/csv
```

Invalid input returns `422` with the offending line number, e.g.
`{"detail": "line 3: nir: Input should be a valid number, unable to parse string as a number"}`.

## Development

```sh
uv run pytest                                      # run tests
uv run ruff check . && uv run ruff format --check . # lint and format check
```

## Project layout

```
src/vegindex/
  indices.py   # NDVI, VARI, ExG formulas and NDVI classification
  schemas.py   # pydantic request/response models
  api.py       # FastAPI application (vegindex.api:app)
tests/         # pytest suite (formulas, edge cases, endpoints)
```

## Roadmap

- Containerize with Docker
- Jenkins CI pipeline
- Deploy to Minikube

## License

[MIT](LICENSE) © Nurshapagat Shapay
