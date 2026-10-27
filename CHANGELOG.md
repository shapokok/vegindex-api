# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Docker: multi-stage `Dockerfile` (`base` → `test` → `runtime`) on `python:3.12-slim`
  with a pinned uv; lint and tests run in the `test` stage, the runtime image ships only
  the virtualenv, runs as a non-root user and has a `/health` healthcheck
  ([#4](https://github.com/shapokok/vegindex-api/pull/4)).
- Jenkins: local controller in `jenkins/` (Docker CLI + pipeline plugins) and a declarative
  `Jenkinsfile` that polls SCM, runs lint and tests, publishes the JUnit report, builds and
  smoke-tests the image and pushes it to Docker Hub from `main`
  ([#5](https://github.com/shapokok/vegindex-api/pull/5)).

## [0.1.0] - 2026-10-27

### Added

- NDVI, VARI and ExG calculations with NDVI classification.
- REST API: `GET /health`, `GET /version`, `POST /indices`, `POST /indices/csv`.
