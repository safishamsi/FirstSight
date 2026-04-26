# Protocol Packs

Filesystem-backed first-aid protocol packs for the vision-agent backend.

## Purpose

Provide human-editable first-aid guidance bundles that combine:

- searchable manual text
- activation metadata
- checklist templates
- lightweight full-text search over guide content

## Public API / Entrypoints

- `app.protocols.loader.load_protocol_packs()`
- `app.protocols.loader.get_protocol_registry()`
- `app.protocols.search.search_protocols()`
- `GET /protocols`
- `GET /protocols/search`
- `GET /protocols/{id}`

## Minimal Example

Each pack lives under `packs/<protocol_id>/` with:

- `metadata.json`
- `manual.md`
- `checklist.md`

## How To Test

- `pytest backend/tests/test_sessions.py -q`
