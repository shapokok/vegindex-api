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

## Docker

The multi-stage [`Dockerfile`](Dockerfile) (based on `python:3.12-slim`, uv pinned via the
`UV_VERSION` build arg) has three stages:

| Stage | Purpose |
|-------|---------|
| `base` | Installs production dependencies from `uv.lock` and the package into `/opt/venv` |
| `test` | Adds dev dependencies and runs `ruff check`, `ruff format --check` and `pytest` (JUnit report at `/reports/junit.xml`); the build fails if any check fails |
| `runtime` (default) | Copies only `/opt/venv` onto a clean base, runs as non-root user `app`, exposes port 8000, has a `HEALTHCHECK` on `/health` |

```sh
# Lint + tests inside the image
docker build --target test -t shapok/vegindex-api:test .
docker run --rm shapok/vegindex-api:test cat /reports/junit.xml > junit.xml

# Runtime image; the commit is reported by GET /version
docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) -t shapok/vegindex-api:dev .
docker run -d -p 8000:8000 --name vi shapok/vegindex-api:dev

curl localhost:8000/health    # {"status":"ok"}
curl localhost:8000/version   # {"name":"vegindex-api","version":"0.1.0","commit":"<sha>"}
docker ps --filter name=vi    # STATUS shows "(healthy)" once the healthcheck passes
docker rm -f vi
```

## Jenkins CI

The declarative [`Jenkinsfile`](Jenkinsfile) polls the repository every 2 minutes and runs:

| Stage | What it does |
|-------|--------------|
| Checkout | Clones the commit and records the branch and short SHA |
| Lint & Unit tests | `docker build --target test` (ruff + pytest); fails the build on any error |
| Publish test report | Copies `/reports/junit.xml` out of the test image with `docker create` + `docker cp` |
| Build image | Builds `shapok/vegindex-api` tagged `:<build number>`, `:<short sha>` and `:latest` with `GIT_COMMIT` |
| Smoke test | Starts the image, waits for `/health`, checks that `/version` reports the built commit |
| Push to Docker Hub | `main` only: `docker login --password-stdin` with the `dockerhub-creds` credentials, pushes all three tags |

Afterwards the JUnit report is published to Jenkins, `docker logout` runs and temporary
containers, per-build tags and the workspace are cleaned up.

### Running Jenkins locally

[`jenkins/`](jenkins) contains a controller image (`jenkins/jenkins:lts-jdk17` + Docker CLI
and buildx + the required plugins) and a Compose file that mounts the host Docker socket:

```sh
docker compose -f jenkins/docker-compose.yml up -d --build
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
open http://localhost:8080
```

On Docker Desktop the socket inside containers is `root:root` with mode `660`, so the
Compose file adds the `jenkins` user to group `0` (`group_add`) instead of running Jenkins
as root. Builds run on the host daemon, which is why the pipeline copies files out of
containers instead of using bind mounts.

Then in Jenkins:

1. Add a *Username with password* credential with ID `dockerhub-creds` (Docker Hub
   username and an access token).
2. Create a *Pipeline* job → *Pipeline script from SCM* → Git
   `https://github.com/shapokok/vegindex-api`, branch `*/main`, script path `Jenkinsfile`.
3. Run it once manually so Jenkins registers the `pollSCM` trigger.

## Project layout

```
Dockerfile     # multi-stage image: base → test → runtime
Jenkinsfile    # CI pipeline
jenkins/       # local Jenkins controller (Dockerfile + docker-compose.yml)
src/vegindex/
  indices.py   # NDVI, VARI, ExG formulas and NDVI classification
  schemas.py   # pydantic request/response models
  api.py       # FastAPI application (vegindex.api:app)
tests/         # pytest suite (formulas, edge cases, endpoints)
```

## Roadmap

- [x] Containerize with Docker
- [x] Jenkins CI pipeline
- [ ] Deploy to Minikube

## License

[MIT](LICENSE) © Nurshapagat Shapay
