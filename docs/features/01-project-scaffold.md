# 01 — Project scaffold

**Commit:** `7b8626c` "Sprint 1: scaffold project (FastAPI + React + SQLite)"

## What it does

Bootstraps the two halves of the app so later features have somewhere to
live: a FastAPI backend and a React + TypeScript + Vite frontend, wired to
compile and run, with no business logic yet.

## Backend

- `app/core/config.py` — `pydantic-settings` `Settings`, reads `APP_*` env vars
- `app/core/logging.py` — stdlib logging configured once at startup
- `app/db/session.py` — SQLAlchemy engine + `SessionLocal`, SQLite with
  `check_same_thread=False` and a busy `timeout` (needed once downloads run
  on background threads and write concurrently)
- `app/api/deps.py` — DI providers (`get_db`, `get_settings`, later extended
  with `get_download_engine`, `get_event_bus`, service providers)
- `app/api/v1/endpoints/health.py` — the only endpoint at this stage, proves
  the DI chain (settings → DB session) works end to end

## Frontend

- Vite + React + TypeScript, `react-router-dom` for routing
- Pinned to Vite 5.x / React 19 rather than the bleeding-edge Vite 8
  (rolldown-based) that shipped from `npm create vite@latest` at the time --
  Vite 8 requires Node ≥20.19 and the dev machine had 20.14

## Verification at the time

`uvicorn` boots and `/api/v1/health` returns 200 with a real SQLite round
trip; `npm run build` compiles cleanly.
