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

## Minimal Example

From the `backend/` directory:

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Vision Agents starter:

```bash
python -m app.examples.basic_video_agent
```

## Notes

- Use Python `3.11` to `3.13`. `vision-agents` currently pulls native dependencies that are not smooth on Python `3.14`.
- The FastAPI service is intentionally lightweight and does not require a live Stream or model session to boot.
- The Vision Agents example is the starting point for the realtime backend, not the finished architecture.
- The face droop processor is currently a scaffold seam for your real model.

## How To Test

```bash
python -m pytest tests
```
