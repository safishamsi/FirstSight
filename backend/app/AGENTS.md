# App Module Guide

## Purpose

This package owns the backend runtime code:

- FastAPI routes and request contracts
- in-memory session state for local development
- Vision Agents bootstrap and provider selection
- processor seams for future CV integrations

## Entry Points

- `main.py` - FastAPI application factory
- `routes.py` - HTTP and WebSocket surfaces
- `agent_factory.py` - Vision Agents bootstrap helpers
- `session_manager.py` - local session state and ingest accounting

## Notes

- Keep the local ingest path bootable even when provider credentials are missing.
- Treat `/sessions/{id}/stream` as the app-to-backend seam for early integration work.
- Do not claim model forwarding is live unless the session path is actually wired through Vision Agents.

