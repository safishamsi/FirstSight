"""
Evaluate heart rate accuracy against SCAMPS ground truth.

Uses mean green channel per frame → FFT (spatial averaging approach).
The full Gaussian pyramid EVM pipeline is designed for real video;
SCAMPS synthetic faces have subtle rPPG signals that are best extracted
via direct spatial mean before the temporal FFT.

Usage:
    python3 scripts/eval_scamps.py
"""
import sys
import numpy as np
import h5py
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "vendor"))
sys.path.insert(0, str(BASE))

from server.signal_processor import SignalProcessor, CONF_THRESHOLD

VIDEOS_DIR = Path("/home/safi/heart_rate_detection/demo/scamps_videos_example")
CSV_DIR    = Path("/home/safi/heart_rate_detection/demo/scamps_waveforms_csv")
FPS        = 30.0
BUFFER     = 150


def ground_truth_bpm(csv_path: Path) -> float:
    df = pd.read_csv(csv_path)
    ppg = df["d_ppg"].values.astype(np.float32)
    freqs = np.fft.rfftfreq(len(ppg), d=1.0 / FPS)
    power = np.abs(np.fft.rfft(ppg - ppg.mean()))
    mask  = (freqs >= 0.5) & (freqs <= 4.0)
    return round(float(freqs[np.argmax(power * mask)] * 60), 1)


def predict_bpm(mat_path: Path) -> tuple[float | None, float]:
    with h5py.File(mat_path, "r") as f:
        raw = np.array(f["RawFrames"]).transpose(3, 2, 1, 0).astype(np.float32)

    # Mean green channel per frame — robust spatial average that works on synthetic faces
    green = raw[:, :, :, 1].mean(axis=(1, 2))  # (N,)

    readings, confs = [], []
    for start in range(0, len(green) - BUFFER + 1):
        window = green[start:start + BUFFER]
        freqs = np.fft.rfftfreq(BUFFER, d=1.0 / FPS)
        power = np.abs(np.fft.rfft(window - window.mean()))
        mask  = (freqs >= 0.5) & (freqs <= 4.0)

        peak_idx   = int(np.argmax(power * mask))
        peak_power = float(power[peak_idx])
        noise      = float(power[~mask].mean()) or 1e-10
        confidence = min(peak_power / noise / 5.0, 1.0)

        if confidence > CONF_THRESHOLD:
            bpm = float(freqs[peak_idx] * 60)
            readings.append(bpm)
            confs.append(confidence)

    if not readings:
        return None, 0.0

    avg_bpm  = round(sum(readings) / len(readings), 1)
    avg_conf = round(sum(confs) / len(confs), 3)
    return avg_bpm, avg_conf


def main():
    subjects = sorted(VIDEOS_DIR.glob("P*.mat"))
    print(f"{'Subject':<12} {'GT BPM':>8} {'Pred BPM':>10} {'Error':>8} {'Conf':>7}")
    print("-" * 55)

    errors = []
    for mat_path in subjects:
        num      = mat_path.stem[1:]
        csv_path = CSV_DIR / f"{num}.csv"
        if not csv_path.exists():
            continue

        gt   = ground_truth_bpm(csv_path)
        pred, conf = predict_bpm(mat_path)

        if pred is not None:
            err  = round(abs(pred - gt), 1)
            flag = " ✓" if err < 5 else " ✗"
            errors.append(err)
        else:
            err, flag = None, " –"

        print(f"{mat_path.stem:<12} {gt:>8.1f} {str(pred):>10} {str(err):>8}{flag}  conf={conf:.3f}")

    if errors:
        print("-" * 55)
        mae = sum(errors) / len(errors)
        within5 = sum(1 for e in errors if e < 5)
        print(f"MAE: {mae:.1f} BPM  |  {within5}/{len(errors)} subjects within 5 BPM")


if __name__ == "__main__":
    main()
