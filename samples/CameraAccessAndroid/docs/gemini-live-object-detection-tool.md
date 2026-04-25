# Gemini Live Grounding + Guidance Tools

This repo now includes a Python grounding + demo-guidance service for Gemini Live.

## Fast local mode (recommended)

For the lowest-latency demo path, run the service with the local Ultralytics backend:

```bash
cd samples/CameraAccessAndroid
python3 -m venv tools/.venv
source tools/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ultralytics pillow
export VISION_TOOL_BACKEND=ultralytics
python tools/vision_tool_server.py
```

This uses a local YOLO model (`yolo11n.pt`) and avoids slow Gemini-image round trips for common objects.

## Moondream cloud SDK mode

On this Apple Silicon Mac, the working Moondream path is **cloud SDK mode** (not `local=True`).

```bash
cd samples/CameraAccessAndroid
source tools/moondream-venv/bin/activate
export MOONDREAM_API_KEY=your_key_here
export VISION_TOOL_BACKEND=moondream
python tools/vision_tool_server.py
```

Notes:
- use `md.vl(api_key=...)`
- do **not** use `local=True` on this Mac
- the server now uses the Moondream SDK for `detect` and `segment` when available

## What it does

- Gemini Live can call `locate_object(query, includeSegmentation?)`
- the app sends the latest frame to a local Python service
- the service calls Gemini image understanding and returns:
  - `found`
  - `label`
  - `confidence`
  - normalized `bbox`
  - optional polygon points for segmentation-style overlay
- Gemini Live can also call `guide_step(stepIndex, observedLabel?, objectFound?)`
- the service returns the next instruction for the laptop-inspection demo workflow

## Start the service

```bash
cd samples/CameraAccessAndroid
export GEMINI_API_KEY=your_key_here
export VISION_TOOL_MODEL=gemini-3-flash-preview
python3 tools/vision_tool_server.py
```

Optional auth:

```bash
export VISION_TOOL_TOKEN=secret-token
```

Service routes:

- `GET /health`
- `POST /locate-object`
- `POST /guide-step`

## Configure the Android app

Open **Settings** in the app and set:

- **Vision Tool / Service URL** → `http://YOUR_MAC_HOSTNAME.local:8765`
- **Vision Tool / Auth Token** → same as `VISION_TOOL_TOKEN` if used

## Health check

```bash
curl http://localhost:8765/health
```

## Manual test

```bash
curl -X POST http://localhost:8765/locate-object \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "wire",
    "includeSegmentation": true,
    "imageBase64": "BASE64_JPEG_HERE"
  }'
```

Guide-step test:

```bash
curl -X POST http://localhost:8765/guide-step \
  -H 'Content-Type: application/json' \
  -d '{
    "task": "Inspect laptop setup",
    "stepIndex": 0,
    "observedLabel": "charging cable",
    "objectFound": true
  }'
```

## Demo flow

1. Start stream on phone or glasses
2. Start Gemini Live
3. Ask:
   - “Which one is the wire?”
   - “Point to the screwdriver.”
4. Gemini should call `locate_object`
5. The app should render a cyan overlay on the detected object
6. For the laptop demo, ask:
   - “Help me inspect this laptop setup.”
   - “What should I do first?”
   - “Point to the charging cable.”
   - “What do I do next?”

## Current backend options

- `VISION_TOOL_BACKEND=ultralytics` → fastest local detector for common objects like `bottle`, `scissors`, `person`, `potted plant`
- `VISION_TOOL_BACKEND=gemini` → slower fallback using Gemini image understanding
- `VISION_TOOL_BACKEND=auto` → prefers Ultralytics when installed
