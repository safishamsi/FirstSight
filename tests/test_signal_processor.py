import numpy as np
import pytest
from server.signal_processor import (SignalProcessor, HeartRateResult, CONF_WINDOW,
                                      STATUS_NO_PULSE, STATUS_NO_SIGNAL, STATUS_NORMAL)


def make_buffer(fps: float, n: int, target_hz: float, h: int = 8, w: int = 15) -> np.ndarray:
    t = np.linspace(0, n / fps, n)
    signal = np.sin(2 * np.pi * target_hz * t)
    buf = np.zeros((n, h, w, 3), dtype=np.float32)
    for i in range(n):
        buf[i] = signal[i]
    return buf


def test_detects_known_frequency():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)  # 72 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert abs(result.bpm - 72.0) < 1.0


# 150 frames @ 30fps → FFT bin width = 0.2 Hz = 12 BPM.
# These frequencies sit exactly on a bin, so the algorithm must nail them to within 1 BPM.
@pytest.mark.parametrize("hz,expected_bpm", [
    (1.2, 72.0),
    (1.6, 96.0),
    (1.8, 108.0),
])
def test_bpm_accuracy_adult(hz, expected_bpm):
    buf = make_buffer(fps=30.0, n=150, target_hz=hz)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert abs(result.bpm - expected_bpm) < 1.0, f"Expected {expected_bpm} BPM, got {result.bpm:.1f}"


def test_bpm_accuracy_neonate():
    # 2.2 Hz = 132 BPM, exactly on a bin
    buf = make_buffer(fps=30.0, n=150, target_hz=2.2)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=2.0, max_freq=2.67)
    result = p.compute(buf)
    assert abs(result.bpm - 132.0) < 1.0, f"Expected 132.0 BPM, got {result.bpm:.1f}"


def test_confidence_high_for_clean_signal():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert result.confidence > 0.5


def test_returns_zero_for_incomplete_buffer():
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    small = np.zeros((50, 8, 15, 3), dtype=np.float32)
    result = p.compute(small)
    assert result.bpm == 0.0
    assert result.confidence == 0.0


def test_no_pulse_after_sustained_low_confidence():
    # conf_window=1 so a single bad reading fills the window immediately
    noise = np.random.rand(150, 8, 15, 3).astype(np.float32) * 0.001
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0, conf_window=1)
    result = p.compute(noise)
    assert result.status == STATUS_NO_PULSE


def test_no_pulse_not_triggered_by_single_bad_frame():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)
    noise = np.random.rand(150, 8, 15, 3).astype(np.float32) * 0.001
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    for _ in range(CONF_WINDOW - 1):
        p.compute(buf)
    result = p.compute(noise)
    assert result.status != STATUS_NO_PULSE


def test_normal_status_for_clean_signal():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)  # 72 BPM — adult normal
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0, mode="adult")
    result = p.compute(buf)
    assert result.status == STATUS_NORMAL


def test_bradycardia_status():
    buf = make_buffer(fps=30.0, n=150, target_hz=0.8)  # 48 BPM — below adult normal
    # Use wide bandpass so 0.8 Hz is reachable
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=0.5, max_freq=2.0, mode="adult")
    result = p.compute(buf)
    assert result.status == "bradycardia"


def test_bpm_smoothing_does_not_jump():
    # Alternate between two valid frequencies — EMA should not jump the full bin width
    buf_72 = make_buffer(fps=30.0, n=150, target_hz=1.2)   # 72 BPM
    buf_84 = make_buffer(fps=30.0, n=150, target_hz=1.4)   # 84 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    p.compute(buf_72)
    result = p.compute(buf_84)
    # Without EMA this would jump straight to 84; with EMA it stays between
    assert result.bpm < 84.0


def test_result_is_heartrate_result_dataclass():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert isinstance(result, HeartRateResult)
    assert hasattr(result, "bpm")
    assert hasattr(result, "confidence")
    assert hasattr(result, "status")


def test_flat_spectrum_gives_low_confidence():
    # Equal power at all frequencies → no dominant peak → low confidence
    buf = np.ones((150, 8, 15, 3), dtype=np.float32)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert result.confidence < 0.5


# SNR robustness: spatial averaging over 120 pixels in the Gaussian pyramid
# means the algorithm stays accurate well beyond 1:1 signal/noise ratio.
# Confidence degrades gracefully as the signal gets weaker.
@pytest.mark.parametrize("noise_amp,min_confidence", [
    (0.1,  0.8),   # low noise  — high confidence
    (1.0,  0.5),   # 1:1 ratio  — still detected, confidence drops
    (5.0,  0.1),   # 5x noise   — BPM still correct, confidence low
])
def test_snr_robustness(noise_amp, min_confidence):
    rng = np.random.default_rng(42)
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)   # 72 BPM clean signal
    noisy = buf + rng.normal(0, noise_amp, buf.shape).astype(np.float32)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(noisy)
    # Spatial averaging over 120 pixels recovers the signal even at high noise
    assert abs(result.bpm - 72.0) < 6.0, f"Expected ~72 BPM at noise={noise_amp}, got {result.bpm:.1f}"
    assert result.confidence >= min_confidence, f"Confidence {result.confidence:.3f} below {min_confidence} at noise={noise_amp}"
