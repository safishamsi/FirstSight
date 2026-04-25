# Droop Detection API

Screens for facial droopiness (a key stroke indicator) from images or videos. Combines an EfficientNet-B0 CNN on mouth crops with MediaPipe landmark-based asymmetry scoring. Not a medical diagnosis tool.

## Requirements

- Python 3.10+
- `ffmpeg` (for video support)

## Setup

```bash
pip install -r requirements.txt
```

Download the MediaPipe face landmarker model:

```bash
curl -sL https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
  -o model/face_landmarker.task
```

## Running the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The server expects these files to exist before starting:

| File | Description |
|---|---|
| `model/droop_model.onnx` | INT8 quantized EfficientNet-B0 |
| `model/face_landmarker.task` | MediaPipe face landmarker |
| `checkpoints/threshold.json` | Classification threshold from evaluation |

## API endpoints

### `POST /predict` — single image

Upload a JPEG, PNG, or WebP image (max 10 MB).

```bash
curl -X POST http://localhost:8000/predict \
  -F "file=@photo.jpg"
```

Response:

```json
{
  "droop_probability": 0.83,
  "is_drooping": true,
  "severity": "severe",
  "confidence": 0.72,
  "face_detected": true,
  "asymmetry_score": 0.071,
  "mouth_asymmetry": 0.082,
  "eye_asymmetry": 0.054,
  "brow_asymmetry": 0.063
}
```

- `severity`: `"none"` / `"mild"` / `"severe"`
- `asymmetry_score`: combined landmark asymmetry (0 = symmetric)
- `face_detected: false` means no face was found; all other fields will be `null`

### `POST /predict/video` — video file

Upload an MP4, MOV, AVI, or WebM file (max 200 MB). Samples frames at 6 fps, runs per-frame inference, and aggregates into a temporal score.

```bash
curl -X POST http://localhost:8000/predict/video \
  -F "file=@clip.mp4"
```

Optional query parameters:

| Parameter | Default | Description |
|---|---|---|
| `sample_fps` | `6.0` | Frames per second to sample (1–30) |
| `max_frames` | `90` | Max frames to process (caps at ~15 s at 6 fps) |

Response:

```json
{
  "droop_likelihood": 0.76,
  "fraction_frames_flagged": 0.82,
  "peak_probability": 0.91,
  "temporal_consistency": 0.85,
  "is_drooping": true,
  "severity": "severe",
  "frames_analyzed": 54,
  "frames_skipped": 3,
  "video_duration_s": 9.5,
  "median_asymmetry": 0.087
}
```

- `droop_likelihood`: blended score — 40% mean probability + 60% fraction of frames flagged
- `temporal_consistency`: 1.0 = signal persistent across all frames, 0.0 = highly variable
- `frames_skipped`: frames where no face was detected
- `median_asymmetry`: median combined asymmetry across frames; values below 0.040 override `is_drooping` to `false`

### `GET /health`

```bash
curl http://localhost:8000/health
```

### `GET /threshold`

Returns the classification threshold and its sensitivity/specificity from evaluation.

## Interactive docs

Swagger UI is available at `http://localhost:8000/docs` when the server is running.

## Training from scratch

If you want to retrain the model on your own data:

```bash
# 1. Prepare dataset (requires data/splits.json)
python train.py --pos-weight 1.5 --epochs 30 --unfreeze-epoch 6

# 2. Evaluate and select threshold
python evaluate.py

# 3. Export to ONNX
python scripts/export_onnx.py
```

Restart the server after export to pick up the new model.

## Model performance (test set, n=881)

| Metric | Value |
|---|---|
| AUROC | 0.985 |
| Sensitivity | 0.884 |
| Specificity | 0.982 |
| Threshold | 0.059 |
