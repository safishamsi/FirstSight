# DroopDetection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time heartbeat detection server that accepts video frames over WebSocket, runs the Eulerian Video Magnification pipeline, and returns live BPM + confidence + emergency alerts.

**Architecture:** The existing `heart_rate_detection` Colab project (YOLOR + DeepSort + Gaussian Pyramid FFT) is downloaded as a dependency and wrapped by our clean server modules. A FastAPI WebSocket endpoint accepts JPEG frames from any client (webcam, Meta glasses mobile bridge), processes them through the pipeline, and emits JSON heartbeat readings per tracked person.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, OpenCV, PyTorch, NumPy, SciPy, YOLOR, DeepSort, gdown

---

## File Map

| File | Responsibility |
|---|---|
| `server/signal_processor.py` | FFT, bandpass filter, BPM, confidence score, alert logic |
| `server/detector.py` | YOLOR head detection wrapper — takes a frame, returns bboxes |
| `server/tracker.py` | DeepSort tracking wrapper — takes bboxes + frame, returns tracked bboxes with IDs |
| `server/pipeline.py` | Orchestrator — ROI crop, Gaussian pyramid, rolling buffer, motion check, calls signal_processor |
| `server/main.py` | FastAPI app — WebSocket endpoint, decodes JPEG frames, calls pipeline |
| `tests/test_signal_processor.py` | Unit tests for FFT/bandpass/alert logic |
| `tests/test_pipeline.py` | Unit tests for pipeline helpers (pyramid, motion, buffering) |
| `tests/test_integration.py` | End-to-end test: stream baby.mp4 frames → expect BPM in 120–160 range |
| `requirements.txt` | Project dependencies |

---

## Task 1: Environment Setup

**Files:**
- Create: `requirements.txt`
- Create: `server/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Install missing system dependencies**

```bash
pip install opencv-python uvicorn gdown websockets pytest pytest-asyncio
```

Expected: `Successfully installed` lines, no errors.

- [ ] **Step 2: Download the heart_rate_detection project from Google Drive**

```bash
cd /home/safi
pip install -q gdown
python3 -c "
import gdown, os
if not os.path.exists('heart_rate_detection'):
    gdown.download(id='1Q8X9z5v-JlmkI2IO-WwqYT5q6GoWPI-Y', output='heart_rate_detection.zip')
    import zipfile
    with zipfile.ZipFile('heart_rate_detection.zip', 'r') as z:
        z.extractall('.')
    print('Done')
else:
    print('Already exists')
"
```

Expected: `Done` or `Already exists`. Verify with:
```bash
ls /home/safi/heart_rate_detection/weights/
```
Expected: `yolor_head.pt  deepsort_reid.t7`

- [ ] **Step 3: Download the demo video**

```bash
cd /home/safi/heart_rate_detection
mkdir -p demo
[ -f demo/baby.mp4 ] || wget -q https://people.csail.mit.edu/mrub/evm/video/baby2.mp4 -O demo/baby.mp4
python3 -c "
import cv2
cap = cv2.VideoCapture('demo/baby.mp4')
print(f'FPS: {cap.get(cv2.CAP_PROP_FPS)}, Frames: {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}')
cap.release()
"
```

Expected: `FPS: 30.0, Frames: 300`

- [ ] **Step 4: Create requirements.txt**

```
fastapi>=0.100.0
uvicorn>=0.23.0
numpy>=1.24.0
scipy>=1.11.0
opencv-python>=4.8.0
torch>=2.0.0
pyyaml>=6.0
gdown>=4.7.0
websockets>=11.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

- [ ] **Step 5: Create package init files**

```bash
mkdir -p /home/safi/droopdetection/server
mkdir -p /home/safi/droopdetection/tests
touch /home/safi/droopdetection/server/__init__.py
touch /home/safi/droopdetection/tests/__init__.py
```

- [ ] **Step 6: Commit**

```bash
cd /home/safi/droopdetection
git add requirements.txt server/__init__.py tests/__init__.py
git commit -m "Add project scaffold and requirements"
```

---

## Task 2: Signal Processor

**Files:**
- Create: `server/signal_processor.py`
- Create: `tests/test_signal_processor.py`

The signal processor is pure NumPy/SciPy with no external model dependencies — test it first.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signal_processor.py`:

```python
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
    assert abs(result.bpm - 72.0) < 5.0


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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/test_signal_processor.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'server.signal_processor'`

- [ ] **Step 3: Implement signal_processor.py**

Create `server/signal_processor.py`:

```python
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class HeartRateResult:
    bpm: float
    confidence: float
    alert: Optional[str]


class SignalProcessor:
    def __init__(self, fps: float = 30.0, buffer_size: int = 150,
                 min_freq: float = 1.0, max_freq: float = 2.0):
        self.fps = fps
        self.buffer_size = buffer_size
        self.min_freq = min_freq
        self.max_freq = max_freq
        self._no_signal_count = 0
        self._no_signal_threshold = int(10 * fps)

    def compute(self, buffer: np.ndarray) -> HeartRateResult:
        if len(buffer) < self.buffer_size:
            return HeartRateResult(bpm=0.0, confidence=0.0, alert=None)

        fft_result = np.fft.fft(buffer, axis=0)
        avg_spectrum = np.abs(fft_result).mean(axis=(1, 2, 3))

        frequencies = (self.fps * np.arange(self.buffer_size)) / self.buffer_size
        mask = (frequencies >= self.min_freq) & (frequencies <= self.max_freq)

        bandpass = avg_spectrum.copy()
        bandpass[~mask] = 0
        peak_idx = int(np.argmax(bandpass))
        peak_freq = frequencies[peak_idx]
        bpm = round(float(peak_freq * 60), 1)

        peak_power = avg_spectrum[peak_idx]
        bg_mean = avg_spectrum[mask].mean()
        bg_mean = bg_mean if bg_mean > 0 else 1e-10
        confidence = round(min(float(peak_power / bg_mean) / 10.0, 1.0), 3)

        if bpm < 40 or bpm > 180 or confidence < 0.3:
            self._no_signal_count += 1
        else:
            self._no_signal_count = 0

        alert = "no_pulse" if self._no_signal_count >= self._no_signal_threshold else None
        return HeartRateResult(bpm=bpm, confidence=confidence, alert=alert)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/test_signal_processor.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd /home/safi/droopdetection
git add server/signal_processor.py tests/test_signal_processor.py
git commit -m "Add signal processor with FFT, bandpass, confidence, and alert logic"
```

---

## Task 3: Head Detector Wrapper

**Files:**
- Create: `server/detector.py`

The detector wraps YOLOR from `heart_rate_detection/`. It has no meaningful unit tests without the GPU model — we test its interface in the integration test. Here we just verify it initialises and its `detect()` method returns the right type.

- [ ] **Step 1: Implement detector.py**

Create `server/detector.py`:

```python
import sys
from pathlib import Path
import torch
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))

from detector.darknet import Darknet
from utils.general import non_max_suppression, scale_coords
from utils.datasets import letterbox
from utils.torch_utils import select_device


class HeadDetector:
    def __init__(self, cfg_path: str, weights_path: str,
                 device: str = "0", img_size: int = 1280,
                 conf_thres: float = 0.3, iou_thres: float = 0.4):
        self.device = select_device(device)
        self.img_size = img_size
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

        self.model = Darknet(cfg_path, img_size).to(self.device)
        state = torch.load(weights_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(state["model"])
        self.model.eval()
        if self.device.type != "cpu":
            self.model.half()

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """
        frame: BGR numpy array (H, W, 3)
        Returns list of (x1, y1, x2, y2, confidence)
        """
        img = letterbox(frame, new_shape=self.img_size, auto_size=64)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img)
        t = torch.from_numpy(img).to(self.device)
        t = (t.half() if self.device.type != "cpu" else t.float()) / 255.0
        t = t.unsqueeze(0)

        with torch.no_grad():
            pred = self.model(t)[0]
            pred = non_max_suppression(pred, conf_thres=self.conf_thres,
                                       iou_thres=self.iou_thres)

        results = []
        det = pred[0]
        if det is not None and len(det):
            det[:, :4] = scale_coords(t.shape[2:], det[:, :4], frame.shape).round()
            for *xyxy, conf, _ in det:
                x1, y1, x2, y2 = (int(v) for v in xyxy)
                results.append((x1, y1, x2, y2, float(conf)))
        return results
```

- [ ] **Step 2: Smoke-test the detector loads without errors**

```bash
cd /home/safi/droopdetection
python3 -c "
import sys; sys.path.insert(0, '/home/safi/heart_rate_detection')
from server.detector import HeadDetector
d = HeadDetector(
    cfg_path='/home/safi/heart_rate_detection/config/yolor_p6_head.cfg',
    weights_path='/home/safi/heart_rate_detection/weights/yolor_head.pt',
)
print('Detector loaded OK')
"
```

Expected: `Detector loaded OK`

- [ ] **Step 3: Commit**

```bash
cd /home/safi/droopdetection
git add server/detector.py
git commit -m "Add YOLOR head detector wrapper"
```

---

## Task 4: Head Tracker Wrapper

**Files:**
- Create: `server/tracker.py`

- [ ] **Step 1: Implement tracker.py**

Create `server/tracker.py`:

```python
import sys
from pathlib import Path
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))

from tracker.deep_sort import DeepSort


class HeadTracker:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)["DEEPSORT"]
        self.tracker = DeepSort(
            cfg["REID_CKPT"],
            max_dist=cfg["MAX_DIST"],
            max_age=cfg["MAX_AGE"],
            n_init=cfg["N_INIT"],
            nn_budget=cfg["NN_BUDGET"],
            use_cuda=True,
        )

    def update(self, detections: list[tuple[int, int, int, int, float]],
               frame: np.ndarray) -> list[tuple[int, int, int, int, int]]:
        """
        detections: list of (x1, y1, x2, y2, conf)
        frame: BGR numpy array
        Returns list of (x1, y1, x2, y2, track_id)
        """
        if not detections:
            return []

        bbox_xywh = np.array([
            [(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1]
            for x1, y1, x2, y2, _ in detections
        ])
        confidences = np.array([c for *_, c in detections])
        oids = np.zeros(len(detections), dtype=int)

        outputs = self.tracker.update(bbox_xywh, confidences, oids, frame)
        return [(int(o[0]), int(o[1]), int(o[2]), int(o[3]), int(o[4]))
                for o in outputs]
```

- [ ] **Step 2: Smoke-test the tracker loads**

```bash
cd /home/safi/droopdetection
python3 -c "
import sys; sys.path.insert(0, '/home/safi/heart_rate_detection')
from server.tracker import HeadTracker
t = HeadTracker('/home/safi/heart_rate_detection/config/deep_sort.yaml')
print('Tracker loaded OK')
"
```

Expected: `Tracker loaded OK`

- [ ] **Step 3: Commit**

```bash
cd /home/safi/droopdetection
git add server/tracker.py
git commit -m "Add DeepSort head tracker wrapper"
```

---

## Task 5: Pipeline Orchestrator

**Files:**
- Create: `server/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
import numpy as np
import pytest
from unittest.mock import MagicMock
from server.pipeline import HeartRatePipeline, build_gaussian_pyramid


def test_pyramid_returns_correct_number_of_levels():
    frame = np.random.randint(0, 255, (120, 240, 3), dtype=np.uint8)
    pyramid = build_gaussian_pyramid(frame, 3)
    assert len(pyramid) == 4  # original + 3 downsampled


def test_pyramid_each_level_is_smaller():
    frame = np.random.randint(0, 255, (120, 240, 3), dtype=np.uint8)
    pyramid = build_gaussian_pyramid(frame, 3)
    for i in range(1, len(pyramid)):
        assert pyramid[i].shape[0] < pyramid[i - 1].shape[0]


def make_pipeline():
    detector = MagicMock()
    tracker = MagicMock()
    return HeartRatePipeline(detector=detector, tracker=tracker, fps=30.0, mode="adult"), detector, tracker


def test_empty_frame_returns_no_results():
    pipeline, detector, tracker = make_pipeline()
    detector.detect.return_value = []
    tracker.update.return_value = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert pipeline.process_frame(frame) == []


def test_single_track_accumulates_in_buffer():
    pipeline, detector, tracker = make_pipeline()
    frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
    detector.detect.return_value = [(100, 100, 300, 300, 0.9)]
    tracker.update.return_value = [(100, 100, 300, 300, 1)]
    pipeline.process_frame(frame)
    assert len(pipeline.buffers[1]) == 1


def test_no_result_until_buffer_is_full():
    pipeline, detector, tracker = make_pipeline()
    detector.detect.return_value = [(100, 100, 300, 300, 0.9)]
    tracker.update.return_value = [(100, 100, 300, 300, 1)]
    for _ in range(149):
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        results = pipeline.process_frame(frame)
        assert results == []


def test_result_returned_once_buffer_is_full():
    pipeline, detector, tracker = make_pipeline()
    detector.detect.return_value = [(100, 100, 300, 300, 0.9)]
    tracker.update.return_value = [(100, 100, 300, 300, 1)]
    results = []
    for _ in range(150):
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        results = pipeline.process_frame(frame)
    assert len(results) == 1
    assert results[0].track_id == 1
    assert isinstance(results[0].bpm, float)
    assert isinstance(results[0].confidence, float)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/test_pipeline.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'server.pipeline'`

- [ ] **Step 3: Implement pipeline.py**

Create `server/pipeline.py`:

```python
import cv2
import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

from server.signal_processor import SignalProcessor, HeartRateResult

PYRAMID_LEVELS = 3
BUFFER_SIZE = 150
ROI_W, ROI_H = 320, 240
H_PAD, W_PAD = 60, 40
MOTION_THRESHOLD = 5.0

FREQ_RANGES = {
    "adult": (1.0, 2.0),
    "neonate": (2.0, 2.67),
}


@dataclass
class PipelineResult:
    track_id: int
    bpm: float
    confidence: float
    alert: Optional[str]


def build_gaussian_pyramid(frame: np.ndarray, levels: int) -> list[np.ndarray]:
    pyramid = [frame]
    for _ in range(levels):
        frame = cv2.pyrDown(frame)
        pyramid.append(frame)
    return pyramid


class HeartRatePipeline:
    def __init__(self, detector, tracker, fps: float = 30.0, mode: str = "adult"):
        self.detector = detector
        self.tracker = tracker
        self.fps = fps
        self.min_freq, self.max_freq = FREQ_RANGES.get(mode, FREQ_RANGES["adult"])
        self.buffers: dict[int, deque] = defaultdict(lambda: deque(maxlen=BUFFER_SIZE))
        self.signal_processors: dict[int, SignalProcessor] = {}
        self.prev_rois: dict[int, np.ndarray] = {}

    def _crop_roi(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> Optional[np.ndarray]:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        xc, yc = (x1 + x2) // 2, (y1 + y2) // 2
        bw, bh = x2 - x1, y2 - y1
        xmin, xmax = max(0, xc - bw // 2), min(w, xc + bw // 2)
        ymin, ymax = max(0, yc - bh // 2), min(h, yc + bh // 2)
        crop = frame[ymin:ymax, xmin:xmax]
        if crop.size == 0:
            return None
        crop = cv2.resize(crop, (ROI_W, ROI_H), interpolation=cv2.INTER_AREA)
        return crop[H_PAD:ROI_H - H_PAD, W_PAD:ROI_W - W_PAD]

    def _motion_too_high(self, track_id: int, roi: np.ndarray) -> bool:
        prev = self.prev_rois.get(track_id)
        self.prev_rois[track_id] = roi
        if prev is None or prev.shape != roi.shape:
            return False
        flow = cv2.calcOpticalFlowFarneback(
            cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY),
            None, 0.5, 3, 15, 3, 5, 1.2, 0,
        )
        return float(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2).mean()) > MOTION_THRESHOLD

    def _get_processor(self, track_id: int) -> SignalProcessor:
        if track_id not in self.signal_processors:
            self.signal_processors[track_id] = SignalProcessor(
                fps=self.fps, buffer_size=BUFFER_SIZE,
                min_freq=self.min_freq, max_freq=self.max_freq,
            )
        return self.signal_processors[track_id]

    def process_frame(self, frame: np.ndarray) -> list[PipelineResult]:
        detections = self.detector.detect(frame)
        tracks = self.tracker.update(detections, frame)
        results = []

        for x1, y1, x2, y2, track_id in tracks:
            roi = self._crop_roi(frame, (x1, y1, x2, y2))
            if roi is None or self._motion_too_high(track_id, roi):
                continue

            gauss = build_gaussian_pyramid(roi, PYRAMID_LEVELS + 1)[PYRAMID_LEVELS]
            self.buffers[track_id].append(gauss)

            if len(self.buffers[track_id]) == BUFFER_SIZE:
                buf = np.array(self.buffers[track_id], dtype=np.float32)
                hr = self._get_processor(track_id).compute(buf)
                results.append(PipelineResult(
                    track_id=track_id,
                    bpm=hr.bpm,
                    confidence=hr.confidence,
                    alert=hr.alert,
                ))

        return results
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/test_pipeline.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
cd /home/safi/droopdetection
git add server/pipeline.py tests/test_pipeline.py
git commit -m "Add pipeline orchestrator with rolling buffer, pyramid, and motion rejection"
```

---

## Task 6: FastAPI WebSocket Server

**Files:**
- Create: `server/main.py`

- [ ] **Step 1: Implement main.py**

Create `server/main.py`:

```python
import sys
import json
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))

from server.detector import HeadDetector
from server.tracker import HeadTracker
from server.pipeline import HeartRatePipeline

BASE = Path(__file__).parent.parent.parent / "heart_rate_detection"

app = FastAPI()


def build_pipeline(mode: str = "adult") -> HeartRatePipeline:
    detector = HeadDetector(
        cfg_path=str(BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(BASE / "weights/yolor_head.pt"),
    )
    tracker = HeadTracker(config_path=str(BASE / "config/deep_sort.yaml"))
    return HeartRatePipeline(detector=detector, tracker=tracker, mode=mode)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    mode = websocket.query_params.get("mode", "adult")
    pipeline = build_pipeline(mode=mode)

    try:
        while True:
            data = await websocket.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            for result in pipeline.process_frame(frame):
                await websocket.send_text(json.dumps({
                    "track_id": result.track_id,
                    "bpm": result.bpm,
                    "confidence": result.confidence,
                    "alert": result.alert,
                }))
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 2: Verify the server starts without errors**

```bash
cd /home/safi/droopdetection
timeout 5 python3 server/main.py 2>&1 | head -5 || true
```

Expected output contains: `Uvicorn running on http://0.0.0.0:8000`

- [ ] **Step 3: Commit**

```bash
cd /home/safi/droopdetection
git add server/main.py
git commit -m "Add FastAPI WebSocket server endpoint"
```

---

## Task 7: Integration Test (End-to-End)

**Files:**
- Create: `tests/test_integration.py`

Streams the `baby.mp4` frames through the full pipeline and asserts a BPM reading in the neonatal range (120–160 BPM) is returned.

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration.py`:

```python
import sys
import cv2
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "heart_rate_detection"))

from server.detector import HeadDetector
from server.tracker import HeadTracker
from server.pipeline import HeartRatePipeline, BUFFER_SIZE

WEIGHTS_BASE = Path("/home/safi/heart_rate_detection")
VIDEO_PATH = WEIGHTS_BASE / "demo/baby.mp4"


@pytest.mark.skipif(
    not WEIGHTS_BASE.exists(),
    reason="heart_rate_detection project not downloaded"
)
def test_neonatal_bpm_in_expected_range():
    detector = HeadDetector(
        cfg_path=str(WEIGHTS_BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(WEIGHTS_BASE / "weights/yolor_head.pt"),
    )
    tracker = HeadTracker(config_path=str(WEIGHTS_BASE / "config/deep_sort.yaml"))
    pipeline = HeartRatePipeline(detector=detector, tracker=tracker,
                                  fps=30.0, mode="neonate")

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    bpm_readings = []

    for _ in range(BUFFER_SIZE + 30):
        ret, frame = cap.read()
        if not ret:
            break
        for result in pipeline.process_frame(frame):
            if result.confidence > 0.3:
                bpm_readings.append(result.bpm)

    cap.release()

    assert len(bpm_readings) > 0, "No BPM readings were produced"
    avg_bpm = sum(bpm_readings) / len(bpm_readings)
    assert 100 <= avg_bpm <= 175, f"BPM {avg_bpm:.1f} outside expected neonatal range"
```

- [ ] **Step 2: Run the integration test**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/test_integration.py -v -s
```

Expected: `1 passed` with BPM printed in range 100–175.

If it fails with BPM out of range, check:
1. The baby.mp4 was downloaded correctly (should be 960x544, 30fps, 10s)
2. The head was detected — add `print(result)` inside the loop to debug

- [ ] **Step 3: Run the full test suite**

```bash
cd /home/safi/droopdetection
python3 -m pytest tests/ -v
```

Expected: all tests pass (`test_signal_processor`: 6, `test_pipeline`: 7, `test_integration`: 1)

- [ ] **Step 4: Final commit**

```bash
cd /home/safi/droopdetection
git add tests/test_integration.py
git commit -m "Add end-to-end integration test against neonatal demo video"
```

---

## Self-Review Notes

- All spec requirements covered: EVM pipeline, sliding window, WebSocket ingestion, motion rejection, confidence scoring, emergency alert, structured project layout
- No TBDs or placeholders
- `HeartRateResult` defined in Task 2 and imported consistently in Tasks 5 and 6
- `PipelineResult` defined in Task 5 and used in Task 6
- `build_gaussian_pyramid` defined in `pipeline.py` and tested in `test_pipeline.py`
- `BUFFER_SIZE` constant imported in integration test from `pipeline.py` — consistent
- Phase 2 (Meta glasses mobile bridge) is explicitly out of scope for this plan
