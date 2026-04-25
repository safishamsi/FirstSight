# `viewer/AGENTS.md`

Purpose:
- React debug dashboard for backend-owned vision-agent sessions.

Entrypoints:
- `src/App.tsx`
- `src/main.tsx`

Guidelines:
- Keep the viewer read-only.
- Poll backend session state rather than introducing a second custom protocol unless needed.
- Prefer simple debug surfaces first: status, counters, transcripts, processor signals, recent events.
