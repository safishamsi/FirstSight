# Backend

Minimal backend scaffold for the planned smart-glasses realtime agent platform.

## Purpose

- expose a simple FastAPI service teammates can run immediately
- provide a Vision Agents starter example with config-based provider selection
- establish folders for future processors, tools, and RAG wiring

## Public Entry Points

- `app.main:app`
- `app.main:create_app`
- `app.examples.basic_video_agent`

## Current HTTP / WebSocket Surfaces

- `GET /health`
- `GET /bootstrap`
- `POST /sessions`
- `GET /sessions/{session_id}`
- `WS /sessions/{session_id}/stream`

Important:

- the session WebSocket is live and tested for app-to-backend ingest
- it currently counts and acknowledges streamed events
- it does **not** yet forward live media into a real Vision Agents call

## Minimal Example

From the `backend/` directory:

```bash
make setup
make dev
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Vision Agents starter:

```bash
make example
```

Tests:

```bash
make test
```

Live ingest smoke test:

```bash
make smoke-stream
```

## Notes

- Use Python `3.11` to `3.13`. `vision-agents` currently pulls native dependencies that are not smooth on Python `3.14`.
- The FastAPI service is intentionally lightweight and does not require a live Stream or model session to boot.
- The Vision Agents example is the starting point for the realtime backend, not the finished architecture.
- The face droop processor is currently a scaffold seam for your real model.
- The current `/sessions/{id}/stream` endpoint proves the app-to-backend hop, not the full backend-to-provider hop.
- `make clean` removes the backend virtualenv and Python caches.
