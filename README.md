# Heart Rate Detection via rPPG

Contactless heart rate measurement from video using remote photoplethysmography (rPPG). Designed for real-time use on Meta glasses or any camera feed — no physical contact required.

## How it works

The human skin changes colour very slightly (~1%) with each heartbeat as blood perfuses the capillaries. This change is invisible to the naked eye but detectable in video. The pipeline:

1. **Detects** the face/head using YOLOR with a MediaPipe fallback for unusual angles (babies lying down, top-down cameras)
2. **Crops** the forehead — the flattest skin region with the strongest pulse signal and minimal expression artifacts
3. **Extracts the blood volume pulse (BVP)** using a CHROM/POS ensemble:
   - **CHROM** (de Haan & Jeanne 2013) — cancels illumination drift; works best on lighter skin tones
   - **POS** (Wang et al. 2017) — projects onto the plane orthogonal to the skin-colour vector; adapts to darker skin tones and non-standard lighting automatically
   - Each frame the algorithm with the higher SNR confidence is used
4. **Estimates BPM** via zero-padded FFT with harmonic-weighted peak selection
5. **Smooths** with an EMA filter to prevent frame-to-frame BPM jumps
6. **Classifies and alerts** based on sustained readings

## Skin tone support

CHROM uses fixed channel coefficients calibrated for lighter skin. On darker Fitzpatrick types the fixed model can misfire — reading 96 BPM when the true rate is 72. POS adapts to whatever skin colour is actually in the ROI, recovering the correct BPM at full confidence. The ensemble picks the winner automatically.

## Alert system

| Status | Meaning |
|---|---|
| `normal` | BPM within expected range for the mode |
| `bradycardia` | BPM below normal range |
| `tachycardia` | BPM above normal range |
| `critical` | BPM in emergency range (adult <40 or >180, neonate <80 or >220) |
| `no_signal` | Signal too noisy to measure |
| `no_pulse` | No pulse detected for a sustained period |

Alerts require **~1 second of consistent readings** before firing — a single noisy frame never triggers a false alarm. Recovery to `normal` is immediate.

The WebSocket message includes `alert_changed: true` only when the status transitions, so the client can trigger a sound or visual alert exactly once per event.

## Modes

| Mode | Normal BPM | Bandpass | Use case |
|---|---|---|---|
| `adult` | 60–100 | 1.0–2.0 Hz | Standard monitoring |
| `neonate` | 100–160 | 2.0–2.67 Hz | NICU / infant monitoring |

In neonate mode, if no face is detected (top-down camera above a crib), the full frame is used as the ROI.

## WebSocket API

Connect to `ws://<host>:8000/ws?mode=adult&fps=30`.

Send frames as JPEG-encoded bytes. Receive JSON per detected person:

```json
{
  "track_id": 1,
  "bpm": 73.4,
  "confidence": 0.963,
  "status": "normal",
  "alert_changed": false
}
```

`confidence` ranges from 0–1. Readings below 0.2 are unreliable and return `no_signal`.

## Running

```bash
# Start the server
python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# Test on a video file
python3 scripts/run_video.py path/to/video.mp4 --mode adult

# Evaluate on MCD-rPPG dataset
python3 scripts/eval_mcd_rppg.py

# Evaluate on SCAMPS synthetic dataset
python3 scripts/eval_scamps.py
```

## Requirements

```
torch
opencv-python
mediapipe
scipy
fastapi
uvicorn
numpy
```

## Tests

```bash
pytest tests/
```

35 tests covering BPM accuracy, SNR robustness, dark skin correction, sustained alert logic, critical thresholds, neonate detection, and end-to-end pipeline integration.

## Real-world limitations

- **Motion**: sustained head movement clears the buffer (optical flow threshold: 5 px/frame). Brief motion is tolerated with a grace period.
- **Lighting**: very low light reduces signal amplitude and confidence.
- **Extreme white balance**: if the camera has severe colour cast (blue-dominant), both CHROM and POS may struggle.
- **Short clips**: the buffer requires 5 seconds of video (150 frames at 30 fps) before the first reading.
