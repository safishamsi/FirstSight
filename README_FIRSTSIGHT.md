# FirstSight

<p align="center">
  <img src="assets/firstsight-logo.svg" width="200" alt="FirstSight logo" />
</p>

<p align="center">
  <strong>Real-time health monitoring through smart glasses.</strong><br/>
  Detect emergencies at first sight — hands-free, contactless, always on.
</p>

---

FirstSight streams live video from Meta smart glasses to an AI-powered backend that silently monitors the people you're looking at. When it detects a cardiac event, a stroke warning sign, or an abnormal heart rate, it alerts you and guides your response — all without touching the patient.

## Features

### Contactless Heart Rate Detection
Measures pulse from the subtle colour change skin makes with every heartbeat (~1% variation, invisible to the eye). Uses a CHROM/POS ensemble algorithm that adapts automatically to different skin tones — no pulse oximeter, no physical contact, no interruption.

- Works on adults and neonates (separate calibrated modes)
- Alerts for bradycardia, tachycardia, and critical extremes (<40 or >180 BPM for adults)
- False-alarm suppression: alerts require ~1 second of consistent readings before firing
- Confidence score on every reading so you know when to trust the number

### Facial Droopiness Detection
Detects facial asymmetry in real time — a key early indicator of stroke, Bell's palsy, and other neurological events. Catches what a bystander might miss in the first critical seconds.

### Guided First-Aid Playbooks
When an emergency is detected, FirstSight overlays step-by-step response guidance directly in your field of view. No fumbling with a phone. No recalling protocol under pressure. Stroke assessment, cardiac response, and more.

### Live AI Scene Understanding
Powered by Gemini Live API, FirstSight understands context — not just individual signals. It correlates what it sees with what it detects to surface the right alert at the right moment.

## Architecture

```
Meta Smart Glasses (camera feed)
        │
        ▼
  Mobile App (iOS / Android)
  ├── Streams frames via WebSocket
  └── Receives overlay instructions
        │
        ▼
  Python Backend
  ├── Heart rate pipeline  (server/pipeline.py)
  │   ├── YOLOR head detector + MediaPipe fallback
  │   ├── DeepSort tracker
  │   └── CHROM/POS rPPG signal processor
  ├── Facial droopiness detector
  ├── Playbook engine  (guided first-aid steps)
  └── Gemini Live integration
        │
        ▼
  React Debug Viewer  (overlay preview, logs, telemetry)
```

## Getting Started

### Prerequisites

- Python 3.10+
- PyTorch (CPU or CUDA)
- Android or iOS device with Meta glasses connected

### Backend setup

```bash
git clone https://github.com/dtseng123/droopdetection.git
cd droopdetection

pip install -r requirements.txt

# Download model weights
# Place yolor_head.pt in weights/

python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### Mobile setup

Copy the example secrets files and fill in your API keys:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp mobile/CameraAccessAndroid/local.properties.example mobile/CameraAccessAndroid/local.properties
```

Required keys:
- `GEMINI_API_KEY` — Gemini Live API
- `github_token` — for Android dependency resolution

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full data-flow diagram.

## Heart Rate API

Connect via WebSocket:

```
ws://<host>:8000/ws?mode=adult&fps=30
```

Send JPEG frames as bytes. Receive per-person readings:

```json
{
  "track_id": 1,
  "bpm": 73.4,
  "confidence": 0.963,
  "status": "normal",
  "alert_changed": true
}
```

| Status | Meaning |
|---|---|
| `normal` | Within expected range |
| `bradycardia` | Below normal |
| `tachycardia` | Above normal |
| `critical` | Emergency range |
| `no_signal` | Signal too noisy |
| `no_pulse` | No pulse detected (sustained) |

`alert_changed: true` only fires on status transitions — use it to trigger audio/haptic alerts without spam.

## Supported Platforms

| Platform | Status |
|---|---|
| Meta smart glasses (via iOS DAT SDK) | ✅ |
| Meta smart glasses (via Android DAT SDK) | ✅ |
| Any camera over WebSocket | ✅ |

## Running Tests

```bash
pytest tests/
```

35 tests covering heart rate accuracy, SNR robustness, dark skin correction, sustained alert logic, critical thresholds, neonate detection, and end-to-end pipeline integration.

## Branches

| Branch | Description |
|---|---|
| `main` | Heart rate detection Python backend |
| `smart-glasses-integration` | iOS + Android apps, React viewer, Gemini Live |
| `facial-droopines` | Facial asymmetry / stroke detection |
| `logfire` | Observability integration |

## Built With

- [Meta Wearables DAT SDK](https://github.com/facebook/meta-wearables-dat-ios) (iOS/Android)
- [Gemini Live API](https://ai.google.dev/gemini-api/docs/live)
- YOLOR · DeepSort · MediaPipe · PyTorch · FastAPI
- CHROM rPPG (de Haan & Jeanne 2013) · POS rPPG (Wang et al. 2017)
