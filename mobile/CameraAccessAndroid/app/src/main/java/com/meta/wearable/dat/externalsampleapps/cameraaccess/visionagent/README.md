# Vision Agent Backend

## Purpose

Parallel Android client path for routing AI sessions through the Python backend without removing the existing direct Gemini flow.

## Public API / Entrypoints

- `VisionAgentMode`
- `VisionAgentConfig`
- `VisionAgentService`
- `VisionAgentSessionViewModel`

## Minimal Example

Select `Vision Agent Backend` in Settings, set `Base URL`, then start AI from the stream screen.

## How To Test

- configure `backendBaseUrl` in app settings
- run the Python backend locally
- start a stream and toggle AI while `Vision Agent Backend` mode is selected
- confirm bootstrap succeeds and websocket acks increment on the overlay
