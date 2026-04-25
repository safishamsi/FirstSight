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
