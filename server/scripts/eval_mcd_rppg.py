"""
Evaluate heart rate accuracy against MCD-rPPG dataset.

Uses MediaPipe face detection + CHROM rPPG (de Haan & Jeanne 2013) +
Butterworth bandpass (0.7–3.5 Hz) + weighted-median aggregation.

Ground truth: db.csv column 'pulse' (BP-device spot measurement).
Note: pulse is measured by a blood-pressure cuff at a point in time
that may differ from the video recording window; ECG-synchronized
BPM tends to be 5–15 BPM lower for "after-exercise" clips.

Usage:
    python3 scripts/eval_mcd_rppg.py
"""
import sys
import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import signal as sp_signal

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

_SERVER = Path(__file__).parent.parent
_ROOT = _SERVER.parent
sys.path.insert(0, str(_SERVER / "vendor"))
sys.path.insert(0, str(_ROOT))

from server.signal_processor import CONF_THRESHOLD

DATASET_DIR  = Path("/home/safi/heart_rate_detection/demo/mcd_rppg")
TFLITE_MODEL = "/tmp/blaze_face_short_range.tflite"
FPS          = 30.0
BUFFER       = 300   # 10 s → 0.1 Hz freq resolution = 6 BPM steps
DETECT_EVERY = 30
LOW_HZ       = 0.9   # 54 BPM lower bound — avoids sub-cardiac respiration harmonics
HIGH_HZ      = 3.5   # 210 BPM upper bound
MAX_FRAMES   = 1350  # ~45–56 s, closest to the GT spot measurement time


def _make_detector():
    base_opts = mp_python.BaseOptions(model_asset_path=TFLITE_MODEL)
    opts = mp_vision.FaceDetectorOptions(
        base_options=base_opts,
        min_detection_confidence=0.4,
    )
    return mp_vision.FaceDetector.create_from_options(opts)


def _detect_face(detector, frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.detections:
        return None
    best = max(result.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
    bb = best.bounding_box
    h, w = frame.shape[:2]
    x1 = max(0, bb.origin_x)
    y1 = max(0, bb.origin_y)
    x2 = min(w, bb.origin_x + bb.width)
    # Forehead-only: top 40% of face height — avoids eyes, mouth, and collar
    # Forehead skin is flatter (less motion), minimally affected by expression changes
    y2 = min(h, y1 + int(bb.height * 0.40))
    return (x1, y1, x2, y2)


def _bandpass(signal_1d: np.ndarray, fps: float) -> np.ndarray:
    nyq = fps / 2.0
    b, a = sp_signal.butter(2, [LOW_HZ / nyq, HIGH_HZ / nyq], btype="band")
    return sp_signal.filtfilt(b, a, signal_1d)


def _chrom_bvp(rgb_means: np.ndarray, fps: float) -> np.ndarray:
    """CHROM algorithm — cancels illumination drift, isolates blood volume pulse."""
    B = rgb_means[:, 0].astype(np.float64)
    G = rgb_means[:, 1].astype(np.float64)
    R = rgb_means[:, 2].astype(np.float64)
    Rn = R / (R.mean() + 1e-8)
    Gn = G / (G.mean() + 1e-8)
    Bn = B / (B.mean() + 1e-8)
    Xs = 3 * Rn - 2 * Gn
    Ys = 1.5 * Rn + Gn - 1.5 * Bn
    alpha = Xs.std() / (Ys.std() + 1e-8)
    bvp = Xs - alpha * Ys
    return _bandpass(bvp.astype(np.float32), fps)


def predict_bpm(video_path: Path) -> tuple[float | None, float]:
    cap      = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
    fps      = cap.get(cv2.CAP_PROP_FPS) or FPS
    detector = _make_detector()

    rgb_list = []
    bbox     = None
    fi       = 0

    while fi < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % DETECT_EVERY == 0:
            detected = _detect_face(detector, frame)
            if detected is not None:
                bbox = detected
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                rgb_list.append(roi.mean(axis=(0, 1)))
        fi += 1

    cap.release()

    if len(rgb_list) < BUFFER:
        return None, 0.0

    rgb_means = np.array(rgb_list, dtype=np.float32)
    n_fft     = max(BUFFER * 4, 512)
    freqs     = np.fft.rfftfreq(n_fft, d=1.0 / fps)
    mask      = (freqs >= LOW_HZ) & (freqs <= HIGH_HZ)

    readings, confs = [], []
    for start in range(0, len(rgb_means) - BUFFER + 1, BUFFER // 3):
        window       = rgb_means[start:start + BUFFER]
        bvp          = _chrom_bvp(window, fps)
        power        = np.abs(np.fft.rfft(bvp, n=n_fft)) ** 2
        masked_power = power * mask
        candidates   = np.argsort(masked_power)[-5:][::-1]
        best_idx, best_score = candidates[0], -1.0
        for c_idx in candidates:
            if masked_power[c_idx] == 0:
                continue
            f       = freqs[c_idx]
            h_idx   = int(np.argmin(np.abs(freqs - 2 * f)))
            h_ratio = power[h_idx] / (power[c_idx] + 1e-10)
            score   = power[c_idx] * 1.5 if h_ratio >= 0.15 else power[c_idx]
            if score > best_score:
                best_score, best_idx = score, c_idx
        peak_power = float(power[best_idx])
        noise_bins = power[~mask]
        noise      = float(noise_bins.mean()) if noise_bins.size else 1e-10
        confidence = min(peak_power / max(noise, 1e-10) / 5.0, 1.0)
        if confidence > CONF_THRESHOLD:
            readings.append(float(freqs[best_idx] * 60))
            confs.append(confidence)

    if not readings:
        return None, 0.0

    weights    = np.array(confs, dtype=np.float32)
    sorted_idx = np.argsort(readings)
    sorted_bpm = np.array(readings)[sorted_idx]
    sorted_w   = weights[sorted_idx]
    cumw       = np.cumsum(sorted_w)
    pred_bpm   = round(float(sorted_bpm[np.searchsorted(cumw, cumw[-1] / 2)]), 1)
    avg_conf   = round(float(weights.mean()), 3)
    return pred_bpm, avg_conf


def main():
    df = pd.read_csv(DATASET_DIR / "db.csv")
    subset = df[df["camera"] == "FullHDwebcam"].copy()

    video_files = {v.name for v in (DATASET_DIR / "video").glob("*.avi")}
    subset = subset[subset["video"].apply(lambda p: Path(p).name in video_files)]

    if subset.empty:
        print("No matching videos found in", DATASET_DIR / "video")
        return

    print(f"{'Video':<38} {'GT BPM':>8} {'Pred BPM':>10} {'Error':>8} {'Conf':>7}")
    print("-" * 78)

    errors = []
    for _, row in subset.iterrows():
        video_path = DATASET_DIR / row["video"]
        gt         = float(row["pulse"])
        pred, conf = predict_bpm(video_path)

        if pred is not None:
            err  = round(abs(pred - gt), 1)
            flag = " ✓" if err < 5 else " ✗"
            errors.append(err)
        else:
            err, flag = None, " –"

        name = Path(row["video"]).name
        print(f"{name:<38} {gt:>8.1f} {str(pred):>10} {str(err):>8}{flag}  conf={conf:.3f}")

    if errors:
        print("-" * 78)
        mae      = sum(errors) / len(errors)
        within5  = sum(1 for e in errors if e < 5)
        within10 = sum(1 for e in errors if e < 10)
        print(f"MAE: {mae:.1f} BPM  |  within 5 BPM: {within5}/{len(errors)}  |  within 10 BPM: {within10}/{len(errors)}")
        print()
        print("Note: GT 'pulse' is from a BP-cuff at a different time than the video.")
        print("ECG-synchronized BPM during video tends to be 5-15 BPM lower for")
        print("'after-exercise' clips, which partially explains the systematic offset.")


if __name__ == "__main__":
    main()
