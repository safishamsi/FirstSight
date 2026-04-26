# DroopDetection — Vision-Based Heartbeat Detection via Meta Glasses

**Date:** 2026-04-25  
**Repo:** github.com/dtseng123/droopdetection

---

## Overview

A real-time system that detects a person's heartbeat using only a camera — no sensors, no contact. The primary use case is a bystander or first responder wearing Meta Ray-Ban glasses who looks at someone in potential cardiac arrest. The system analyses the live video stream, detects the subject's pulse from subtle skin color changes, and surfaces a live BPM reading with a confidence score and emergency alert.

---

## Core Algorithm: Eulerian Video Magnification (EVM)

Built on top of the existing notebook codebase (`heart_rate_detection.ipynb`). The pipeline is:

1. **Head detection** — YOLOR neural network finds the head bounding box in each frame
2. **Tracking** — DeepSort assigns and maintains a stable track ID across frames
3. **ROI crop** — the head region is cropped, resized to 320x240, inner padding removed
4. **Gaussian Pyramid** — image is blurred and downsampled 3 levels to isolate broad color changes (strips fine texture/hair detail, keeps skin-tone signal)
5. **Rolling buffer** — level-3 pyramid frames are pushed into a 150-frame sliding window (~5 seconds at 30fps)
6. **FFT** — Fast Fourier Transform run along the time axis of the buffer
7. **Bandpass filter** — frequencies outside the valid HR range masked out (adults: 1.0–2.0 Hz / 60–120 BPM; neonates: 2.0–2.67 Hz / 120–160 BPM)
8. **Peak detection** — dominant frequency = BPM
9. **Amplification** — 170x amplification of the filtered signal (for visual overlay, optional)
10. **Confidence score** — SNR of the FFT peak vs. background noise in the bandpass window

---

## Improvements Over the Notebook

| Notebook | This System |
|---|---|
| File input only | Live WebSocket frame ingestion |
| Waits 150 frames before first reading | Sliding window — continuous update every ~1s |
| No motion handling | Optical flow motion check per frame |
| No confidence output | SNR-based confidence score on every reading |
| No alerting | Emergency flag when no pulse detectable |
| Notebook format | Structured Python project |

---

## System Architecture

```
Meta Glasses (720p @ 30fps)
        ↓  Bluetooth
Mobile App (Meta Wearables SDK — Phase 2)
        ↓  WebSocket (JPEG binary frames)
Python Backend (FastAPI)
  ├── YOLOR head detection
  ├── DeepSort tracker
  ├── Gaussian Pyramid + rolling buffer
  ├── Motion artifact rejection (optical flow)
  ├── FFT → bandpass → peak detection
  └── Confidence scoring + emergency flag
        ↓  WebSocket JSON response
Mobile App: displays live BPM + alert
```

**Development / testing:** any webcam or RTMP stream can substitute for Meta glasses during local dev.

---

## Per-Frame Data Flow

```
WebSocket frame (JPEG bytes)
  → decode to numpy array
  → YOLOR: detect head bounding box
  → DeepSort: assign/update track ID
  → crop ROI → resize 320x240 → strip padding
  → Gaussian pyramid level 3
  → optical flow delta vs previous frame
      → if motion > threshold: mark frame unreliable, skip FFT update
  → push to rolling buffer (150 frames per track ID)
  → FFT along time axis
  → bandpass mask (based on adult/neonate mode)
  → peak frequency → BPM
  → SNR confidence score
  → emit JSON: { track_id, bpm, confidence, alert? }
```

---

## Output Schema

```json
{
  "track_id": 1,
  "bpm": 72,
  "confidence": 0.87,
  "alert": null
}
```

`alert` values: `null` (normal) | `"no_pulse"` (BPM < 40 or > 180, or confidence < 0.3 for 10+ seconds)

---

## Project Structure

```
droopdetection/
├── server/
│   ├── main.py              # FastAPI + WebSocket entry point
│   ├── pipeline.py          # Core rPPG pipeline
│   ├── detector.py          # YOLOR head detection wrapper
│   ├── tracker.py           # DeepSort wrapper
│   └── signal_processor.py  # FFT + bandpass + confidence + alerts
├── mobile/                  # Meta Wearables SDK app (Phase 2)
├── weights/                 # YOLOR + DeepSort model weights
├── config/                  # YOLOR + DeepSort config files
├── docs/
│   └── superpowers/specs/
├── requirements.txt
└── README.md
```

---

## Parameters

| Parameter | Adult | Neonate |
|---|---|---|
| Min frequency | 1.0 Hz | 2.0 Hz |
| Max frequency | 2.0 Hz | 2.67 Hz |
| BPM range | 60–120 | 120–160 |
| Buffer size | 150 frames | 150 frames |
| Amplification | 170x | 170x |
| Pyramid levels | 3 | 3 |

---

## Emergency Detection Logic

- `bpm < 40` → `alert: "no_pulse"`
- `bpm > 180` → `alert: "no_pulse"`
- `confidence < 0.3` for 10 consecutive seconds → `alert: "no_pulse"`

---

## Motion Artifact Rejection

Dense optical flow (Farneback) computed between consecutive frames. If mean flow magnitude exceeds threshold (default: 5.0 px/frame), the frame is flagged as unreliable and excluded from the FFT buffer update. The last valid BPM reading is held until the signal stabilises.

---

## Phase 2: Meta Glasses Integration

The Meta Wearables Device Access Toolkit (iOS/Android SDK, released Dec 2025) provides camera frame access at 720p @ 30fps via Bluetooth. The mobile app:
1. Receives frames from the glasses via the SDK
2. Encodes as JPEG
3. Streams over WiFi WebSocket to the Python backend
4. Receives BPM + alert JSON and displays it on screen

---

## Out of Scope (v1)

- On-device processing (glasses or phone)
- 911 / emergency service integration
- Multi-person tracking (single subject only in v1)
- Deep learning rPPG models (MTTS-CAN)
- Arrhythmia / HRV analysis
