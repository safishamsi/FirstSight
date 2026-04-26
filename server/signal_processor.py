import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional
from scipy.signal import butter, filtfilt

EMA_ALPHA = 0.3        # BPM smoothing weight — lower is smoother, ~1s lag at 30fps
CONF_WINDOW = 60       # sliding window length in compute() calls
CONF_BAD_FRACTION = 0.7  # fraction of window that must be bad to call it no_pulse
CONF_THRESHOLD = 0.2

ALERT_WINDOW = 30      # consecutive compute() calls before an alert fires (~1 s at 30 fps)
ALERT_FRACTION = 0.8   # fraction of alert window that must agree before firing

# Per-mode normal BPM ranges (distinct from bandpass — bandpass is wider to catch edge cases)
NORMAL_RANGES = {
    "adult":   (60, 100),
    "neonate": (100, 160),
}

# Outside these bounds the reading is an emergency, not just out-of-normal.
# Detection requires the SignalProcessor bandpass to cover these frequencies.
CRITICAL_RANGES = {
    "adult":   (40, 180),   # 0.67 Hz – 3.0 Hz
    "neonate": (80, 220),   # 1.33 Hz – 3.67 Hz
}

STATUS_NORMAL     = "normal"
STATUS_BRADYCARDIA = "bradycardia"
STATUS_TACHYCARDIA = "tachycardia"
STATUS_CRITICAL   = "critical"
STATUS_NO_SIGNAL  = "no_signal"
STATUS_NO_PULSE   = "no_pulse"


@dataclass
class HeartRateResult:
    bpm: float
    confidence: float
    status: str


def _classify(bpm: float, confidence: float,
              normal_min: int, normal_max: int,
              critical_min: int, critical_max: int,
              no_pulse: bool) -> str:
    if no_pulse:
        return STATUS_NO_PULSE
    if confidence < CONF_THRESHOLD:
        return STATUS_NO_SIGNAL
    if bpm < critical_min or bpm > critical_max:
        return STATUS_CRITICAL
    if bpm < normal_min:
        return STATUS_BRADYCARDIA
    if bpm > normal_max:
        return STATUS_TACHYCARDIA
    return STATUS_NORMAL


def _chrom_bvp(rgb: np.ndarray) -> np.ndarray:
    """CHROM (de Haan & Jeanne 2013) — calibrated for lighter skin, strong illumination cancellation."""
    B, G, R = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    Rn = R / (R.mean() + 1e-8)
    Gn = G / (G.mean() + 1e-8)
    Bn = B / (B.mean() + 1e-8)
    Xs = 3 * Rn - 2 * Gn
    Ys = 1.5 * Rn + Gn - 1.5 * Bn
    alpha = float(Xs.std() / (Ys.std() + 1e-8))
    return (Xs - alpha * Ys).astype(np.float32)


def _pos_bvp(rgb: np.ndarray) -> np.ndarray:
    """POS (Wang et al. 2017) — skin-tone agnostic via orthogonal-plane projection.

    Projects normalised RGB onto the two axes perpendicular to the skin-colour
    vector, then adaptively combines them.  Works where CHROM's fixed channel
    ratios underfit: darker Fitzpatrick types, mixed lighting, non-standard
    camera white balance.
    """
    B, G, R = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    Rn = R / (R.mean() + 1e-8)
    Gn = G / (G.mean() + 1e-8)
    Bn = B / (B.mean() + 1e-8)
    S1 = Gn - Bn
    S2 = -2 * Rn + Gn + Bn
    alpha = float(S1.std() / (S2.std() + 1e-8))
    return (S1 + alpha * S2).astype(np.float32)


class SignalProcessor:
    def __init__(self, fps: float = 30.0, buffer_size: int = 150,
                 min_freq: float = 1.0, max_freq: float = 2.0,
                 mode: str = "adult", conf_window: int = CONF_WINDOW):
        self.fps = fps
        self.buffer_size = buffer_size
        self.min_freq = min_freq
        self.max_freq = max_freq
        self._normal_min,   self._normal_max   = NORMAL_RANGES.get(mode,   NORMAL_RANGES["adult"])
        self._critical_min, self._critical_max = CRITICAL_RANGES.get(mode, CRITICAL_RANGES["adult"])
        self._bpm_ema: Optional[float] = None
        self._conf_window:  deque = deque(maxlen=conf_window)
        self._alert_window: deque = deque(maxlen=ALERT_WINDOW)

    def _bvp_to_hr(self, signal_1d: np.ndarray) -> tuple[float, float]:
        """Bandpass → FFT → harmonic peak → SNR confidence.  Returns (raw_bpm, confidence)."""
        if signal_1d.std() < 1e-6:
            return 0.0, 0.0

        nyq = self.fps / 2.0
        lo, hi = self.min_freq / nyq, self.max_freq / nyq
        filtered = signal_1d.copy()
        if 0 < lo < 1 and 0 < hi < 1 and lo < hi:
            b, a = butter(2, [lo, hi], btype="band")
            filtered = filtfilt(b, a, signal_1d)

        n_fft = max(self.buffer_size * 4, 512)
        spectrum = np.fft.rfft(filtered, n=n_fft)
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.fps)
        power = np.abs(spectrum)

        mask = (freqs >= self.min_freq) & (freqs <= self.max_freq)
        masked_power = power * mask
        candidates = np.argsort(masked_power)[-5:][::-1]
        best_idx = candidates[0]
        best_score = -1.0
        for c_idx in candidates:
            if masked_power[c_idx] == 0:
                continue
            f = freqs[c_idx]
            h_idx = int(np.argmin(np.abs(freqs - 2 * f)))
            harmonic_ratio = power[h_idx] / (power[c_idx] + 1e-10)
            score = power[c_idx] * 1.5 if harmonic_ratio >= 0.15 else power[c_idx]
            if score > best_score:
                best_score = score
                best_idx = c_idx

        peak_freq = float(freqs[best_idx])
        raw_bpm = peak_freq * 60.0

        # Demeaned rfft for SNR — strips DC offset that would inflate noise floor ~300×
        signal_centered = signal_1d - signal_1d.mean()
        fft_raw = np.abs(np.fft.rfft(signal_centered, n=self.buffer_size))
        freqs_coarse = np.fft.rfftfreq(self.buffer_size, d=1.0 / self.fps)
        mask_coarse = (freqs_coarse >= self.min_freq) & (freqs_coarse <= self.max_freq)
        out_of_band = fft_raw[~mask_coarse]
        noise = float(out_of_band.mean()) if len(out_of_band) > 0 else 1e-10
        noise = max(noise, 1e-10)
        closest_idx = int(np.argmin(np.abs(freqs_coarse - peak_freq)))
        peak_power = float(fft_raw[closest_idx])
        confidence = round(min(float(peak_power / noise) / 5.0, 1.0), 3)

        return raw_bpm, confidence

    def _sustained_status(self, raw_status: str) -> str:
        """Return an alert status only after ALERT_WINDOW consecutive agreeing readings.

        no_pulse already has its own sustained mechanism via _conf_window.
        Normal and no_signal pass through immediately to avoid masking real recovery.
        """
        if raw_status in (STATUS_NORMAL, STATUS_NO_SIGNAL, STATUS_NO_PULSE):
            return raw_status
        if len(self._alert_window) < self._alert_window.maxlen:
            return STATUS_NORMAL
        fraction = self._alert_window.count(raw_status) / len(self._alert_window)
        return raw_status if fraction >= ALERT_FRACTION else STATUS_NORMAL

    def compute(self, buffer: np.ndarray) -> HeartRateResult:
        if buffer.ndim != 4 or len(buffer) < self.buffer_size:
            return HeartRateResult(bpm=0.0, confidence=0.0, status=STATUS_NO_SIGNAL)

        rgb = buffer.mean(axis=(1, 2)).astype(np.float64)  # (N, 3) BGR

        # CHROM/POS ensemble — pick whichever extracts a stronger cardiac signal
        chrom_bpm, chrom_conf = self._bvp_to_hr(_chrom_bvp(rgb))
        pos_bpm,   pos_conf   = self._bvp_to_hr(_pos_bvp(rgb))

        if chrom_conf == 0.0 and pos_conf == 0.0:
            return HeartRateResult(bpm=0.0, confidence=0.0, status=STATUS_NO_SIGNAL)

        raw_bpm, confidence = (pos_bpm, pos_conf) if pos_conf > chrom_conf else (chrom_bpm, chrom_conf)

        # EMA smoothing — prevents BPM jumping by full FFT bin widths frame-to-frame
        if self._bpm_ema is None:
            self._bpm_ema = raw_bpm
        else:
            self._bpm_ema = EMA_ALPHA * raw_bpm + (1 - EMA_ALPHA) * self._bpm_ema
        bpm = round(self._bpm_ema, 1)

        # Sliding window: sustained poor signal → no_pulse
        is_bad = confidence < CONF_THRESHOLD
        self._conf_window.append(is_bad)
        window_full = len(self._conf_window) == self._conf_window.maxlen
        bad_fraction = sum(self._conf_window) / len(self._conf_window)
        no_pulse = window_full and bad_fraction >= CONF_BAD_FRACTION

        raw_status = _classify(bpm, confidence,
                               self._normal_min, self._normal_max,
                               self._critical_min, self._critical_max,
                               no_pulse)
        self._alert_window.append(raw_status)
        status = self._sustained_status(raw_status)

        return HeartRateResult(bpm=bpm, confidence=confidence, status=status)
