"""
Evaluate heart rate accuracy against SCAMPS ground truth.

Uses mean green channel per frame → FFT (spatial averaging approach).
The full Gaussian pyramid EVM pipeline is designed for real video;
SCAMPS synthetic faces have subtle rPPG signals that are best extracted
via direct spatial mean before the temporal FFT.

Usage:
    python3 server/scripts/eval_scamps.py
"""
import sys
import numpy as np
import h5py
import pandas as pd
from pathlib import Path
from scipy.signal import butter, filtfilt

_SERVER = Path(__file__).parent.parent
_ROOT = _SERVER.parent
sys.path.insert(0, str(_SERVER / "vendor"))
sys.path.insert(0, str(_ROOT))

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

    LOW_HZ, HIGH_HZ = 0.5, 4.0
    nyq = FPS / 2.0
    lo, hi = LOW_HZ / nyq, HIGH_HZ / nyq
    b_bp, a_bp = butter(2, [lo, hi], btype="band")

    n_fft = max(BUFFER * 4, 512)

    readings, confs = [], []
    for start in range(0, len(green) - BUFFER + 1):
        window = green[start:start + BUFFER]

        # Butterworth bandpass then zero-padded rfft for peak detection
        filtered = filtfilt(b_bp, a_bp, window - window.mean())
        spec     = np.fft.rfft(filtered, n=n_fft)
        freqs    = np.fft.rfftfreq(n_fft, d=1.0 / FPS)
        power    = np.abs(spec)
        mask     = (freqs >= LOW_HZ) & (freqs <= HIGH_HZ)

        # Harmonic-weighted peak selection
        masked_power = power * mask
        candidates   = np.argsort(masked_power)[-5:][::-1]
        best_idx     = candidates[0]
        best_score   = -1.0
        for c_idx in candidates:
            if masked_power[c_idx] == 0:
                continue
            f     = freqs[c_idx]
            h_idx = int(np.argmin(np.abs(freqs - 2 * f)))
            hr    = power[h_idx] / (power[c_idx] + 1e-10)
            score = power[c_idx] * 1.5 if hr >= 0.15 else power[c_idx]
            if score > best_score:
                best_score = score
                best_idx   = c_idx

        # Confidence from unfiltered coarse FFT (broadband noise reference)
        power_raw   = np.abs(np.fft.rfft(window - window.mean(), n=BUFFER))
        freqs_coarse = np.fft.rfftfreq(BUFFER, d=1.0 / FPS)
        mask_coarse  = (freqs_coarse >= LOW_HZ) & (freqs_coarse <= HIGH_HZ)
        out_of_band  = power_raw[~mask_coarse]
        noise        = float(out_of_band.mean()) if out_of_band.size else 1e-10
        noise        = noise if noise > 0 else 1e-10
        closest_idx  = int(np.argmin(np.abs(freqs_coarse - freqs[best_idx])))
        peak_power   = float(power_raw[closest_idx])
        confidence   = min(peak_power / noise / 5.0, 1.0)

        if confidence > CONF_THRESHOLD:
            bpm = float(freqs[best_idx] * 60)
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
