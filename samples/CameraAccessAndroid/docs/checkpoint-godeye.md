# GodEye Checkpoint

Date: 2026-03-28
Branch: `feature/gemini-object-detection-tool`

## What exists now

- Gemini Live integration with multiple tool declarations
- Focus-mode platform behavior:
  - `focus_object`
  - `clear_focus`
- Object grounding + tracking loop
- Direction hints (`look left/right/up/down`)
- Stale overlay clearing
- Object inspection flow:
  - `inspect_object`
  - info panel in stream UI
- Guidance-session flow:
  - `start_guidance`
  - `guide_step`
  - `advance_step`
- User-facing app name changed to **GodEye**

## Backend status

- Python tool server supports:
  - grounding
  - tracking
  - guidance session
  - object inspection
- Moondream works through the Python SDK cloud path on this Mac
- Ultralytics fast local mode also exists as an alternate backend

## Known caveats

- Tracking is simple reacquire tracking, not world-anchored tracking
- Direction hints are frame-relative, not head-pose-aware
- Guidance is still laptop-demo-oriented and not yet a generalized task engine
- Search-style object panel content is currently static knowledge data, not live web search
- App settings may still need manual adjustment on-device depending on saved preferences

## Recommended next steps

1. Re-test the on-device loop with:
   - `focus_object`
   - tracking
   - `inspect_object`
2. Improve failure messages when the backend is unreachable
3. If needed, make inspect/search implicitly focus the object even more aggressively
4. Add lightweight live search enrichment for the object panel
