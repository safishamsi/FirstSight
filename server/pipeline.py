import cv2
import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

from server.signal_processor import SignalProcessor, HeartRateResult, STATUS_NO_SIGNAL

PYRAMID_LEVELS = 3
BUFFER_SIZE = 150
ROI_W, ROI_H = 320, 240
FOREHEAD_FRAC = 0.40  # top 40% of face height — flat skin, minimal expression artifacts
MOTION_THRESHOLD = 5.0
MOTION_GRACE_FRAMES = 10  # brief motion keeps buffer; beyond this, buffer is stale and cleared
WHOLE_FRAME_TRACK_ID = 0  # synthetic track when no face detected (neonate top-down camera)

FREQ_RANGES = {
    "adult": (1.0, 2.0),
    "neonate": (2.0, 2.67),
}


@dataclass
class PipelineResult:
    track_id: int
    bpm: float
    confidence: float
    status: str


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
        if mode not in FREQ_RANGES:
            raise ValueError(f"Unknown mode {mode!r}. Valid: {list(FREQ_RANGES)}")
        self.mode = mode
        self.min_freq, self.max_freq = FREQ_RANGES[mode]
        self.buffers: dict[int, deque] = defaultdict(lambda: deque(maxlen=BUFFER_SIZE))
        self.signal_processors: dict[int, SignalProcessor] = {}
        self.prev_rois: dict[int, np.ndarray] = {}
        self._motion_streak: dict[int, int] = defaultdict(int)
        self._frame_count = 0
        self._detect_interval = 10  # run YOLOR every 10th frame; tracker fills in between

    def _crop_roi(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> Optional[np.ndarray]:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        bw, bh = x2 - x1, y2 - y1
        # Forehead: top 40% of face height, 10% horizontal margin each side
        fx1 = max(0, x1 + bw // 10)
        fx2 = min(w, x2 - bw // 10)
        fy2 = min(h, y1 + int(bh * FOREHEAD_FRAC))
        crop = frame[y1:fy2, fx1:fx2]
        if crop.size == 0:
            return None
        return cv2.resize(crop, (ROI_W, ROI_H), interpolation=cv2.INTER_AREA)

    def _motion_too_high(self, track_id: int, roi: np.ndarray) -> bool:
        prev = self.prev_rois.get(track_id)
        if prev is None or prev.shape != roi.shape:
            self.prev_rois[track_id] = roi
            return False
        flow = cv2.calcOpticalFlowFarneback(
            cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY),
            None, 0.5, 3, 15, 3, 5, 1.2, 0,
        )
        if float(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2).mean()) > MOTION_THRESHOLD:
            return True
        self.prev_rois[track_id] = roi
        return False

    def _get_processor(self, track_id: int) -> SignalProcessor:
        if track_id not in self.signal_processors:
            self.signal_processors[track_id] = SignalProcessor(
                fps=self.fps, buffer_size=BUFFER_SIZE,
                min_freq=self.min_freq, max_freq=self.max_freq,
                mode=self.mode,
            )
        return self.signal_processors[track_id]

    def process_frame(self, frame: np.ndarray) -> list[PipelineResult]:
        if frame is None or frame.ndim != 3:
            return []
        self._frame_count += 1
        if self._frame_count % self._detect_interval == 0:
            detections = self.detector.detect(frame)
        else:
            detections = []
        tracks = self.tracker.update(detections, frame)

        # Neonate cameras are top-down: face detectors miss upward-facing babies.
        # When no track is found, use the full frame as a single synthetic ROI.
        if not tracks and self.mode == "neonate":
            h, w = frame.shape[:2]
            tracks = [(0, 0, w, h, WHOLE_FRAME_TRACK_ID)]

        results = []

        for x1, y1, x2, y2, track_id in tracks:
            roi = self._crop_roi(frame, (x1, y1, x2, y2))
            if roi is None:
                continue

            if self._motion_too_high(track_id, roi):
                self._motion_streak[track_id] += 1
                if self._motion_streak[track_id] > MOTION_GRACE_FRAMES:
                    # Sustained movement — buffer contains a mix of before/after motion frames
                    self.buffers[track_id].clear()
                continue

            self._motion_streak[track_id] = 0

            # Blur removes JPEG block artifacts before pyramid decomposition
            roi_smooth = cv2.GaussianBlur(roi, (3, 3), 0)
            gauss = build_gaussian_pyramid(roi_smooth, PYRAMID_LEVELS + 1)[PYRAMID_LEVELS]
            self.buffers[track_id].append(gauss)  # raw BGR; CHROM normalises per-channel in compute()

            if len(self.buffers[track_id]) == BUFFER_SIZE:
                buf = np.array(self.buffers[track_id], dtype=np.float32)
                hr = self._get_processor(track_id).compute(buf)
                results.append(PipelineResult(
                    track_id=track_id,
                    bpm=hr.bpm,
                    confidence=hr.confidence,
                    status=hr.status,
                ))

        return results
