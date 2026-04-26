import numpy as np
import pytest
from server.signal_processor import (SignalProcessor, HeartRateResult, CONF_WINDOW,
                                      STATUS_NO_PULSE, STATUS_NO_SIGNAL, STATUS_NORMAL,
                                      STATUS_CRITICAL, ALERT_WINDOW,
                                      _chrom_bvp, _pos_bvp)


def make_buffer(fps: float, n: int, target_hz: float, h: int = 8, w: int = 15) -> np.ndarray:
    t = np.linspace(0, n / fps, n)
    signal = np.sin(2 * np.pi * target_hz * t)
    buf = np.zeros((n, h, w, 3), dtype=np.float32)
    # BGR channels with different amplitudes — required for CHROM to extract a non-zero BVP.
    # Blood pulse affects green most (haemoglobin absorption), then red, then blue.
    for i in range(n):
        buf[i, :, :, 0] = 128.0 + 0.3 * signal[i]   # B — small
        buf[i, :, :, 1] = 128.0 + 1.5 * signal[i]   # G — dominant
        buf[i, :, :, 2] = 128.0 + 0.8 * signal[i]   # R — moderate
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
    # Seed 5 produces a random buffer with no dominant cardiac peak (conf reliably < 0.2).
    # After CONF_WINDOW consecutive low-confidence readings the window fills → no_pulse.
    rng = np.random.default_rng(5)
    noise = (rng.standard_normal((150, 8, 15, 3)) * 0.1 + 128.0).astype(np.float32)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = None
    for _ in range(CONF_WINDOW):
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
    # Wide bandpass so 0.8 Hz is reachable; ALERT_WINDOW reads needed before alert fires
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=0.5, max_freq=2.0, mode="adult")
    result = None
    for _ in range(ALERT_WINDOW):
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


# ── POS algorithm tests ───────────────────────────────────────────────────────

def make_dark_skin_buffer(fps: float, n: int, target_hz: float,
                          h: int = 8, w: int = 15) -> np.ndarray:
    """Simulate darker Fitzpatrick skin: lower overall reflectance, compressed channel
    ratios due to broad melanin absorption.

    Amplitudes are chosen so that CHROM's fixed skin-colour coefficients nearly cancel
    the BVP (Xs ≈ 0), while POS's adaptive projection still recovers it — demonstrating
    the motivation for running both algorithms.

    Normalised amplitudes: bn=0.00667, gn=0.01286, rn=0.00909
      CHROM: Xs = 3*rn - 2*gn ≈ 0.00156  (near-zero, poorly conditioned)
      POS:   S1 = gn - bn     ≈ 0.00619  (clearly non-zero)
    """
    t = np.linspace(0, n / fps, n)
    signal = np.sin(2 * np.pi * target_hz * t)
    buf = np.zeros((n, h, w, 3), dtype=np.float32)
    for i in range(n):
        buf[i, :, :, 0] = 60.0 + 0.4 * signal[i]   # B  bn_amp = 0.4/60  = 0.00667
        buf[i, :, :, 1] = 70.0 + 0.9 * signal[i]   # G  gn_amp = 0.9/70  = 0.01286
        buf[i, :, :, 2] = 55.0 + 0.5 * signal[i]   # R  rn_amp = 0.5/55  = 0.00909
    return buf


def test_pos_extracts_nonzero_bvp():
    # Use the same dark-skin channel amplitudes: bn≠gn in normalised space → S1 ≠ 0
    t = np.linspace(0, 5.0, 150)
    signal = np.sin(2 * np.pi * 1.2 * t)
    rgb = np.column_stack([
        60.0 + 0.4 * signal,   # B
        70.0 + 0.9 * signal,   # G
        55.0 + 0.5 * signal,   # R
    ])
    bvp = _pos_bvp(rgb)
    assert bvp.std() > 1e-4, "POS BVP should have measurable variance for a pulsatile signal"


def test_chrom_and_pos_agree_on_clean_light_skin():
    """On a well-separated-channel signal both algorithms should find the same BPM."""
    buf = make_buffer(fps=30.0, n=150, target_hz=1.2)  # 72 BPM, green-dominant
    rgb = buf.mean(axis=(1, 2)).astype(np.float64)
    t = np.linspace(0, 150 / 30.0, 150)
    chrom = _chrom_bvp(rgb)
    pos   = _pos_bvp(rgb)
    # Both BVPs should be correlated with the ground-truth sine
    gt = np.sin(2 * np.pi * 1.2 * t).astype(np.float32)
    assert abs(np.corrcoef(chrom, gt)[0, 1]) > 0.5, "CHROM BVP poorly correlated with GT"
    assert abs(np.corrcoef(pos,   gt)[0, 1]) > 0.5, "POS BVP poorly correlated with GT"


def test_dark_skin_chrom_gets_wrong_bpm():
    """CHROM's fixed skin-colour model misfits dark skin — peaks on a wrong harmonic."""
    buf = make_dark_skin_buffer(fps=30.0, n=150, target_hz=1.2)  # true = 72 BPM
    rgb = buf.mean(axis=(1, 2)).astype(np.float64)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    chrom_bpm, chrom_conf = p._bvp_to_hr(_chrom_bvp(rgb))
    # CHROM locks onto a wrong peak — BPM is measurably off and confidence is low
    assert abs(chrom_bpm - 72.0) > 10.0, (
        f"Expected CHROM to misread on dark skin, but got {chrom_bpm:.1f} BPM"
    )
    assert chrom_conf < 0.5, f"Expected low CHROM confidence on dark skin, got {chrom_conf:.3f}"


def test_dark_skin_pos_correct_bpm():
    """POS adapts to the actual skin-colour vector and recovers the true BPM."""
    buf = make_dark_skin_buffer(fps=30.0, n=150, target_hz=1.2)  # true = 72 BPM
    rgb = buf.mean(axis=(1, 2)).astype(np.float64)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    pos_bpm, pos_conf = p._bvp_to_hr(_pos_bvp(rgb))
    assert abs(pos_bpm - 72.0) < 3.0, f"Expected POS ≈72 BPM on dark skin, got {pos_bpm:.1f}"
    assert pos_conf > 0.8, f"Expected high POS confidence on dark skin, got {pos_conf:.3f}"


def test_ensemble_fixes_dark_skin_misread():
    """Ensemble selects POS (higher confidence) and corrects the CHROM misread."""
    buf = make_dark_skin_buffer(fps=30.0, n=150, target_hz=1.2)  # true = 72 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = p.compute(buf)
    assert abs(result.bpm - 72.0) < 3.0, (
        f"Ensemble should recover 72 BPM on dark skin (CHROM alone would misread), got {result.bpm:.1f}"
    )
    assert result.confidence > 0.8, f"Ensemble confidence too low: {result.confidence:.3f}"


# ── Alert system tests ────────────────────────────────────────────────────────

def test_critical_status_extreme_high_bpm():
    # 3.1 Hz = 186 BPM — above adult critical max (180). Wide bandpass needed.
    buf = make_buffer(fps=30.0, n=150, target_hz=3.1)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=3.5, mode="adult")
    result = None
    for _ in range(ALERT_WINDOW):
        result = p.compute(buf)
    assert result.status == STATUS_CRITICAL, f"Expected critical, got {result.status}"


def test_critical_status_extreme_low_bpm():
    # 0.6 Hz = 36 BPM — below adult critical min (40). Wide bandpass needed.
    buf = make_buffer(fps=30.0, n=150, target_hz=0.6)
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=0.4, max_freq=2.0, mode="adult")
    result = None
    for _ in range(ALERT_WINDOW):
        result = p.compute(buf)
    assert result.status == STATUS_CRITICAL, f"Expected critical, got {result.status}"


def test_no_premature_alert_on_single_tachycardia_reading():
    # ALERT_WINDOW - 1 normal readings followed by one tachycardia — should NOT alert yet
    buf_normal = make_buffer(fps=30.0, n=150, target_hz=1.2)   # 72 BPM
    buf_tachy  = make_buffer(fps=30.0, n=150, target_hz=1.8)   # 108 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    for _ in range(ALERT_WINDOW - 1):
        p.compute(buf_normal)
    result = p.compute(buf_tachy)
    assert result.status != "tachycardia", (
        f"Alert fired too early on a single reading: {result.status}"
    )


def test_tachycardia_fires_after_sustained_window():
    buf = make_buffer(fps=30.0, n=150, target_hz=1.8)  # 108 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    result = None
    for _ in range(ALERT_WINDOW):
        result = p.compute(buf)
    assert result.status == "tachycardia", f"Expected tachycardia after sustained window, got {result.status}"


def test_alert_clears_immediately_on_normal():
    buf_tachy  = make_buffer(fps=30.0, n=150, target_hz=1.8)  # 108 BPM
    buf_normal = make_buffer(fps=30.0, n=150, target_hz=1.2)  # 72 BPM
    p = SignalProcessor(fps=30.0, buffer_size=150, min_freq=1.0, max_freq=2.0)
    for _ in range(ALERT_WINDOW):
        p.compute(buf_tachy)
    result = p.compute(buf_normal)
    assert result.status == STATUS_NORMAL, (
        f"Alert should clear immediately on normal reading, got {result.status}"
    )
