# Backend Module Guide

## Purpose

This module owns the planned backend-first runtime:

- FastAPI service surfaces for the mobile apps and future viewer
- Vision Agents bootstrap and provider selection
- custom processors, tools, and RAG integration seams

## Entry Points

- `app.main:create_app` - FastAPI application factory
- `app.main:app` - ASGI app for local development
- `app.examples.basic_video_agent` - minimal Vision Agents starter example

## Editing Rules

- Keep the FastAPI app bootable without requiring a live Vision Agents session
- Keep provider selection config-driven
- Add new model integrations under explicit seams: `processors`, `tools`, `rag`
- Prefer small modules over one large orchestration file

## How To Test

- `python -m pytest tests`
- `uvicorn app.main:app --reload`

