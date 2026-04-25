# Vision Agent Backend Module

- Purpose: Android-side session routing and transport for the Vision Agent backend mode.
- Entry points: `VisionAgentConfig`, `VisionAgentService`, `VisionAgentSessionViewModel`.
- Testing: use the local Python backend, start a stream, enable `Vision Agent Backend` mode, and verify websocket acks increase while frames/audio are sent.
