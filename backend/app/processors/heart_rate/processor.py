from __future__ import annotations

import asyncio
import logging
import os
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image
from scipy.ndimage import gaussian_filter
from vision_agents.core.processors import VideoProcessor

from .signal_processor import CONF_THRESHOLD, SignalProcessor

if TYPE_CHECKING:
    import aiortc
    from av import VideoFrame
    from vision_agents.core import Agent
    from vision_agents.core.utils.video_forwarder import VideoForwarder

logger = logging.getLogger(__name__)

_MP_MODEL_PATH = "/tmp/blaze_face_short_range.tflite"
_MP_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)

FREQ_RANGES: dict[str, tuple[float, float]] = {
    "adult": (1.0, 2.0),
    "neonate": (2.0, 2.67),
}
FOREHEAD_FRAC = 0.40
ROI_W, ROI_H = 320, 240
PYRAMID_LEVELS = 3
MOTION_THRESHOLD = 15.0  # mean abs pixel diff threshold (grayscale, 0-255)
MOTION_GRACE_FRAMES = 10
TRACK_MAX_DIST = 150
ALERT_STATUSES = {"bradycardia", "tachycardia", "critical"}


def _bgr_to_rgb(arr: np.ndarray) -> np.ndarray:
    return arr[:, :, ::-1].copy()


def _bgr_to_gray(arr: np.ndarray) -> np.ndarray:
    """BT.601 luma from BGR."""
    return (0.1140 * arr[:, :, 0] + 0.5870 * arr[:, :, 1] + 0.2989 * arr[:, :, 2]).astype(np.uint8)


def _resize(arr: np.ndarray, w: int, h: int) -> np.ndarray:
    img = Image.fromarray(arr)
    img = img.resize((w, h), Image.LANCZOS)
    return np.array(img)


def _pyr_down(arr: np.ndarray) -> np.ndarray:
    """Halve spatial resolution via 2× subsampling."""
    return arr[::2, ::2]


@dataclass(slots=True)
class HeartRateSignal:
    message: str
    score: float
    threshold: float
    over_threshold: bool


class _CentroidTracker:
    """Nearest-neighbour tracker — no external model weights needed."""

    def __init__(self, max_dist: float = TRACK_MAX_DIST, max_age: int = 30) -> None:
        self._next_id = 1
        self._centroids: dict[int, tuple[float, float]] = {}
        self._ages: dict[int, int] = {}
        self._max_dist = max_dist
        self._max_age = max_age

    def update(
        self, detections: list[tuple[int, int, int, int, float]]
    ) -> list[tuple[int, int, int, int, int]]:
        for tid in list(self._ages):
            self._ages[tid] += 1
            if self._ages[tid] > self._max_age:
                del self._centroids[tid]
                del self._ages[tid]

        results: list[tuple[int, int, int, int, int]] = []
        used: set[int] = set()

        for x1, y1, x2, y2, _ in detections:
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            best_id, best_dist = None, self._max_dist
            for tid, (tx, ty) in self._centroids.items():
                if tid in used:
                    continue
                d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                if d < best_dist:
                    best_dist, best_id = d, tid
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
            self._centroids[best_id] = (cx, cy)
            self._ages[best_id] = 0
            used.add(best_id)
            results.append((x1, y1, x2, y2, best_id))

        return results


class HeartRateProcessor(VideoProcessor):
    name = "heart_rate_processor"

    def __init__(self, fps: float = 10.0, mode: str = "adult") -> None:
        self.fps = fps
        self.mode = mode
        self._buffer_size = max(30, int(fps * 5))
        min_freq, max_freq = FREQ_RANGES.get(mode, FREQ_RANGES["adult"])
        self._min_freq = min_freq
        self._max_freq = max_freq

        self._mp_detector: mp_vision.FaceDetector | None = None
        self._tracker = _CentroidTracker()
        self._buffers: dict[int, deque] = defaultdict(
            lambda: deque(maxlen=self._buffer_size)
        )
        self._signal_procs: dict[int, SignalProcessor] = {}
        self._prev_gray: dict[int, np.ndarray] = {}
        self._motion_streak: dict[int, int] = defaultdict(int)

        self.latest_signal = HeartRateSignal(
            message="Heart rate processor initialised. Waiting for video.",
            score=0.0,
            threshold=CONF_THRESHOLD,
            over_threshold=False,
        )

    def _ensure_detector(self) -> None:
        if self._mp_detector is not None:
            return
        if not os.path.exists(_MP_MODEL_PATH):
            logger.info("Downloading MediaPipe face detector model (~1 MB)…")
            urllib.request.urlretrieve(_MP_MODEL_URL, _MP_MODEL_PATH)
        base_options = mp_python.BaseOptions(model_asset_path=_MP_MODEL_PATH)
        options = mp_vision.FaceDetectorOptions(
            base_options=base_options, min_detection_confidence=0.4
        )
        self._mp_detector = mp_vision.FaceDetector.create_from_options(options)

    def _detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        self._ensure_detector()
        h, w = frame.shape[:2]
        rgb = _bgr_to_rgb(frame)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._mp_detector.detect(mp_image)  # type: ignore[union-attr]
        boxes: list[tuple[int, int, int, int, float]] = []
        for det in result.detections:
            bb = det.bounding_box
            x1, y1 = max(0, bb.origin_x), max(0, bb.origin_y)
            x2, y2 = min(w, bb.origin_x + bb.width), min(h, bb.origin_y + bb.height)
            boxes.append((x1, y1, x2, y2, det.categories[0].score))
        return boxes

    def _crop_forehead(
        self, frame: np.ndarray, bbox: tuple[int, int, int, int]
    ) -> np.ndarray | None:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        bw, bh = x2 - x1, y2 - y1
        fx1 = max(0, x1 + bw // 10)
        fx2 = min(w, x2 - bw // 10)
        fy2 = min(h, y1 + int(bh * FOREHEAD_FRAC))
        crop = frame[y1:fy2, fx1:fx2]
        if crop.size == 0:
            return None
        return _resize(crop, ROI_W, ROI_H)

    def _motion_too_high(self, track_id: int, roi: np.ndarray) -> bool:
        gray = _bgr_to_gray(roi)
        prev = self._prev_gray.get(track_id)
        if prev is None or prev.shape != gray.shape:
            self._prev_gray[track_id] = gray
            return False
        diff = float(np.abs(gray.astype(np.int16) - prev.astype(np.int16)).mean())
        if diff > MOTION_THRESHOLD:
            return True
        self._prev_gray[track_id] = gray
        return False

    def _get_signal_proc(self, track_id: int) -> SignalProcessor:
        if track_id not in self._signal_procs:
            self._signal_procs[track_id] = SignalProcessor(
                fps=self.fps,
                buffer_size=self._buffer_size,
                min_freq=self._min_freq,
                max_freq=self._max_freq,
                mode=self.mode,
            )
        return self._signal_procs[track_id]

    def _process_frame_sync(self, frame_bgr: np.ndarray) -> None:
        detections = self._detect(frame_bgr)
        tracks = self._tracker.update(detections)

        messages: list[str] = []
        max_conf = 0.0
        any_alert = False

        for x1, y1, x2, y2, track_id in tracks:
            roi = self._crop_forehead(frame_bgr, (x1, y1, x2, y2))
            if roi is None:
                continue

            if self._motion_too_high(track_id, roi):
                self._motion_streak[track_id] += 1
                if self._motion_streak[track_id] > MOTION_GRACE_FRAMES:
                    self._buffers[track_id].clear()
                continue

            self._motion_streak[track_id] = 0
            roi_smooth = gaussian_filter(roi.astype(np.float32), sigma=1.0).astype(np.uint8)
            g = roi_smooth
            for _ in range(PYRAMID_LEVELS):
                g = _pyr_down(g)
            self._buffers[track_id].append(g)

            buf = self._buffers[track_id]
            if len(buf) < self._buffer_size:
                remaining = self._buffer_size - len(buf)
                messages.append(f"Person {track_id}: collecting signal ({remaining} frames remaining)")
                continue

            arr = np.array(buf, dtype=np.float32)
            hr = self._get_signal_proc(track_id).compute(arr)

            if hr.confidence > max_conf:
                max_conf = hr.confidence
            if hr.status in ALERT_STATUSES:
                any_alert = True

            if hr.confidence >= CONF_THRESHOLD:
                messages.append(
                    f"Person {track_id}: {hr.bpm:.0f} BPM — {hr.status} (confidence {hr.confidence:.2f})"
                )
            else:
                messages.append(f"Person {track_id}: {hr.status}")

        if not tracks:
            msg = "Heart rate: no face detected."
        elif not messages:
            msg = "Heart rate: measuring…"
        else:
            msg = "Heart rate (rPPG) — " + "; ".join(messages)

        self.latest_signal = HeartRateSignal(
            message=msg,
            score=max_conf,
            threshold=CONF_THRESHOLD,
            over_threshold=any_alert,
        )

    def attach_agent(self, agent: "Agent") -> None:
        pass

    async def process_video(
        self,
        track: "aiortc.VideoStreamTrack",
        participant_id: str | None,
        shared_forwarder: "VideoForwarder | None" = None,
    ) -> None:
        del track, participant_id
        if shared_forwarder is None:
            return
        shared_forwarder.add_frame_handler(
            self._handle_frame,
            fps=float(self.fps),
            name=self.name,
        )

    async def stop_processing(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def _handle_frame(self, frame: "VideoFrame") -> None:
        arr = frame.to_ndarray(format="bgr24")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_frame_sync, arr)
