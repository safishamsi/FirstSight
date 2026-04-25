# Viewer

Purpose:
- A minimal React debug dashboard for the Python backend sessions.

What it shows:
- active sessions
- counters for video/audio/text traffic
- latest processor signals
- recent transcript/debug events

Run:
```bash
cd viewer
npm install
npm run dev
```

Backend URL:
```bash
cp .env.example .env
```

Then set:
```text
VITE_BACKEND_URL=http://localhost:8000
```

Test:
- Start the backend with `make backend-dev`
- Start the viewer with `npm run dev`
- Start a mobile session in `Vision Agent Backend` mode
- Open the viewer and select the newest session
