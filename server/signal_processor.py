import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional
from scipy.signal import butter, filtfilt

EMA_ALPHA = 0.3        # BPM smoothing weight — lower is smoother, ~1s lag at 30fps
CONF_WINDOW = 60       # sliding window length in compute() calls
CONF_BAD_FRACTION = 0.7  # fraction of window that must be bad to call it no_pulse
CONF_THRESHOLD = 0.2

# Per-mode normal BPM ranges (distinct from bandpass — bandpass is wider to catch edge cases)
NORMAL_RANGES = {
    "adult":   (60, 100),
    "neonate": (100, 160),
}

STATUS_NORMAL = "normal"
STATUS_BRADYCARDIA = "bradycardia"
STATUS_TACHYCARDIA = "tachycardia"
STATUS_NO_SIGNAL = "no_signal"
STATUS_NO_PULSE = "no_pulse"


@dataclass
class HeartRateResult:
    bpm: float
    confidence: float
    status: str


def _classify(bpm: float, confidence: float, normal_min: int, normal_max: int,
              no_pulse: bool) -> str:
    if no_pulse:
        return STATUS_NO_PULSE
    if confidence < CONF_THRESHOLD:
        return STATUS_NO_SIGNAL
    if bpm < normal_min:
        return STATUS_BRADYCARDIA
    if bpm > normal_max:
        return STATUS_TACHYCARDIA
    return STATUS_NORMAL


class SignalProcessor:
    def __init__(self, fps: float = 30.0, buffer_size: int = 150,
                 min_freq: float = 1.0, max_freq: float = 2.0,
                 mode: str = "adult", conf_window: int = CONF_WINDOW):
        self.fps = fps
        self.buffer_size = buffer_size
        self.min_freq = min_freq
        self.max_freq = max_freq
        self._normal_min, self._normal_max = NORMAL_RANGES.get(mode, NORMAL_RANGES["adult"])
        self._bpm_ema: Optional[float] = None
        self._conf_window: deque = deque(maxlen=conf_window)

    def compute(self, buffer: np.ndarray) -> HeartRateResult:
        if buffer.ndim != 4 or len(buffer) < self.buffer_size:
            return HeartRateResult(bpm=0.0, confidence=0.0, status=STATUS_NO_SIGNAL)

        # Step 1: Compute spatial+channel mean → 1D signal
        signal_1d = buffer.mean(axis=(1, 2, 3))

        # Step 2: Apply Butterworth bandpass to isolate cardiac frequencies
        nyq = self.fps / 2.0
        lo = self.min_freq / nyq
        hi = self.max_freq / nyq
        filtered = signal_1d.copy()
        if 0 < lo < 1 and 0 < hi < 1 and lo < hi:
            b, a = butter(2, [lo, hi], btype="band")
            filtered = filtfilt(b, a, signal_1d)

        # Step 3: Zero-padded rfft for spectral interpolation (peak detection)
        n_fft = max(self.buffer_size * 4, 512)
        spectrum = np.fft.rfft(filtered, n=n_fft)
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.fps)
        power = np.abs(spectrum)

        # Step 4: Frequency mask
        mask = (freqs >= self.min_freq) & (freqs <= self.max_freq)

        # Step 5: Harmonic-weighted peak selection
        masked_power = power * mask
        candidates = np.argsort(masked_power)[-5:][::-1]
        best_idx = candidates[0]
        best_score = -1.0
        for c_idx in candidates:
            if masked_power[c_idx] == 0:
                continue
            f = freqs[c_idx]
            # Find bin closest to 2*f (second harmonic)
            h_idx = int(np.argmin(np.abs(freqs - 2 * f)))
            harmonic_ratio = power[h_idx] / (power[c_idx] + 1e-10)
            if harmonic_ratio >= 0.15:
                score = power[c_idx] * 1.5
            else:
                score = power[c_idx]
            if score > best_score:
                best_score = score
                best_idx = c_idx

        peak_freq = float(freqs[best_idx])
        raw_bpm = peak_freq * 60.0

        # Step 6: SNR confidence — computed on unfiltered signal's coarse FFT to preserve
        # broadband noise reference (avoids inflated SNR after bandpass filtering)
        fft_raw = np.abs(np.fft.fft(signal_1d, n=self.buffer_size))
        freqs_coarse = (self.fps * np.arange(self.buffer_size)) / self.buffer_size
        mask_coarse = (freqs_coarse >= self.min_freq) & (freqs_coarse <= self.max_freq)
        out_of_band = fft_raw[~mask_coarse]
        noise = float(out_of_band.mean()) if len(out_of_band) > 0 else 0.0
        noise = noise if noise > 0 else 1e-10
        closest_idx = int(np.argmin(np.abs(freqs_coarse - peak_freq)))
        peak_power = float(fft_raw[closest_idx])
        confidence = round(min(float(peak_power / noise) / 5.0, 1.0), 3)

        # Step 7: EMA smoothing — prevents BPM jumping by full FFT bin widths frame-to-frame
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

        status = _classify(bpm, confidence, self._normal_min, self._normal_max, no_pulse)
        return HeartRateResult(bpm=bpm, confidence=confidence, status=status)
