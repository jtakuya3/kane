# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository State

This is a freshly scaffolded Python package — `kane/__init__.py` is empty and there is no application code yet. When adding the first modules, place them under the `kane/` package directory. Tests are not yet present; create a `tests/` directory at the repo root for them (pytest will discover it without further configuration).

## Toolchain

- Python `^3.12`, managed by Poetry (see `pyproject.toml`).
- Dev tooling: `pytest`, `black`, `flake8` — none of these have project-specific configuration yet, so they run with defaults.

## Commands

- Install deps: `poetry install`
- Run all tests: `poetry run pytest`
- Run a single test: `poetry run pytest tests/path/to/test_file.py::test_name`
- Lint: `poetry run flake8`
- Format: `poetry run black .`
