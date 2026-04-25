# App Runtime

This package contains the backend runtime for local development and future deployment.

## Purpose

- expose a small FastAPI surface for the mobile app
- hold local session state while the realtime wiring is still evolving
- provide a clean seam for later Vision Agents transport integration

## Public Surfaces

- `GET /health`
- `GET /bootstrap`
- `POST /sessions`
- `GET /sessions/{session_id}`
- `WS /sessions/{session_id}/stream`

## Minimal Example

Run the backend:

```bash
make dev
```

In another shell:

```bash
python -m app.examples.mock_stream_client
```

## How To Test

```bash
make test
```

