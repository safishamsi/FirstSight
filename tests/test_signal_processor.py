import numpy as np
import pytest
from server.signal_processor import SignalProcessor, HeartRateResult


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


def test_no_pulse_alert_after_sustained_low_confidence():
    noise = np.random.rand(150, 8, 15, 3).astype(np.float32) * 0.001
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    p._no_signal_threshold = 1  # trigger immediately
    result = p.compute(noise)
    assert result.alert == "no_pulse"


def test_no_alert_for_clean_signal():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert result.alert is None


def test_result_is_heartrate_result_dataclass():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert isinstance(result, HeartRateResult)
    assert hasattr(result, "bpm")
    assert hasattr(result, "confidence")
    assert hasattr(result, "alert")


def test_flat_spectrum_gives_low_confidence():
    # Equal power at all frequencies → no dominant peak → low confidence
    buf = np.ones((150, 8, 15, 3), dtype=np.float32)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert result.confidence < 0.5
