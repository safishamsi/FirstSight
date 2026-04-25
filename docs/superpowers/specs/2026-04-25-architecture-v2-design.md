# DroopDetection Architecture v2

**Date:** 2026-04-25
**Scope:** Three targeted fixes to the v1 implementation. No new features, no new abstractions.

---

## Problems Being Fixed

### 1. Model reloads on every WebSocket connection
`build_pipeline()` in `main.py` instantiates `HeadDetector` on every connection, which loads the 286MB YOLOR model from disk each time (~5–10 seconds on CPU). This makes the server effectively unusable for repeated connections.

### 2. Confidence scoring broken for real video
`SignalProcessor.compute()` uses in-band mean power as the noise denominator, then divides by 10.0. On real compressed video this produces confidence values of ~0.13 — below the 0.3 alert threshold — meaning every real-world reading increments `_no_signal_count` and would trigger a spurious `"no_pulse"` alert after 10 seconds of use.

### 3. Fragile `sys.path` hacks and external directory dependency
`detector.py` and `tracker.py` both call `sys.path.insert(0, ...)` at import time, mutating global Python state. The project also depends on `/home/safi/heart_rate_detection` existing as a sibling directory on the filesystem — anyone cloning the repo gets broken imports immediately.

---

## Fix 1: Model Singleton via FastAPI Lifespan

**File:** `server/main.py`

Replace `build_pipeline()` called per-connection with a FastAPI `lifespan` context manager. The `HeadDetector` and `HeadTracker` are constructed once at server startup and stored on `app.state`. Each WebSocket connection reads from `app.state` and creates a lightweight `HeartRatePipeline` (no model loading, just wires existing objects together).

```
startup
  └── HeadDetector(cfg, weights)  ← loads YOLOR once
  └── HeadTracker(config)         ← loads DeepSort once
  └── stored on app.state

per connection
  └── HeartRatePipeline(app.state.detector, app.state.tracker, mode)
```

`HeartRatePipeline.__init__` does no I/O and is cheap to construct — buffers, signal processors, and prev_rois dicts are all created empty.

---

## Fix 2: Out-of-Band SNR Confidence

**File:** `server/signal_processor.py`

Replace the current in-band mean denominator with out-of-band mean power — the actual noise floor:

```
signal = avg_spectrum[peak_idx]                  # power at dominant frequency
noise  = avg_spectrum[~mask].mean()              # mean power outside HR band
SNR    = signal / noise
confidence = min(SNR / 5.0, 1.0)
```

Out-of-band power is the right noise reference: it measures everything the signal is competing against. A clean pulse standing clearly above the noise floor gives SNR >> 5 → confidence near 1.0. A noisy signal with no dominant peak gives SNR ≈ 1.0 → confidence near 0.2.

The divisor changes from `/10.0` to `/5.0` to account for the fact that out-of-band noise is typically lower than in-band mean, which would otherwise over-deflate the score.

Edge case: if the entire spectrum outside the HR band is zero (synthetic test signal), `noise` would be 0. Guard: `noise = noise if noise > 0 else 1e-10`.

---

## Fix 3: Vendor Source Files

**New directory:** `vendor/`

Copy the three source directories from `heart_rate_detection` directly into the repo:

```
vendor/
├── detector/    ← YOLOR model architecture (darknet.py + dependencies)
├── tracker/     ← DeepSort tracker
└── utils/       ← YOLOR preprocessing utilities
```

**New directory:** `config/`

Copy config files from `heart_rate_detection/config/`:
```
config/
├── yolor_p6_head.cfg
├── deep_sort.yaml
└── class_names.txt
```

**New directory:** `weights/` (gitignored)

Model weights are too large for the repo (286MB). Add to `.gitignore`. Document in `README.md`:
```
To download weights, run:
python3 -c "import gdown; gdown.download(id='1Q8X9z5v-JlmkI2IO-WwqYT5q6GoWPI-Y', output='heart_rate_detection.zip')"
then extract weights/ and config/ from the zip.
```

**Import changes:**

`server/detector.py` — remove `sys.path.insert`, change imports:
```python
# Before
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))
from detector.darknet import Darknet
from utils.general import non_max_suppression, scale_coords
from utils.datasets import letterbox
from utils.torch_utils import select_device

# After
from vendor.detector.darknet import Darknet
from vendor.utils.general import non_max_suppression, scale_coords
from vendor.utils.datasets import letterbox
from vendor.utils.torch_utils import select_device
```

`server/tracker.py` — remove `sys.path.insert`, change import:
```python
# Before
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))
from tracker.deep_sort import DeepSort

# After
from vendor.tracker.deep_sort import DeepSort
```

`server/main.py` — update `BASE` path:
```python
# Before
BASE = Path(__file__).parent.parent.parent / "heart_rate_detection"

# After
BASE = Path(__file__).parent.parent  # droopdetection root
```

Config and weights are now at `BASE / "config/..."` and `BASE / "weights/..."`.

---

## What Does Not Change

- EVM algorithm (Gaussian pyramid + FFT + bandpass)
- Rolling 150-frame buffer with sliding window
- Motion rejection via optical flow
- Per-track signal processors
- WebSocket JSON output schema: `{track_id, bpm, confidence, alert}`
- All existing tests (unit tests pass unchanged; integration test confidence threshold adjusts to match new scoring)

---

## File Change Summary

| File | Change |
|---|---|
| `server/main.py` | Add `lifespan`, remove per-connection model load |
| `server/signal_processor.py` | 2-line SNR formula fix |
| `server/detector.py` | Remove `sys.path.insert`, import from `vendor.*` |
| `server/tracker.py` | Remove `sys.path.insert`, import from `vendor.*` |
| `vendor/` | New — copy of detector/, tracker/, utils/ |
| `config/` | New — copy of YOLOR + DeepSort config files |
| `weights/` | New directory, gitignored |
| `.gitignore` | New — ignore `weights/` |
