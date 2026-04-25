"""
Temporal aggregation for video-based droop detection.

Strategy:
  - Sample frames at a fixed rate (default 6 fps)
  - Run per-frame inference (CNN probability + landmark asymmetry)
  - Aggregate into droop_likelihood score
  - Apply video-level median asymmetry gate: if the face is consistently
    symmetric across frames, it is not drooping regardless of CNN output
"""
from __future__ import annotations

import io
import logging
import tempfile
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from app.inference import DroopModel

logger = logging.getLogger(__name__)

_SEVERITY_THRESHOLDS = {"mild": 0.3, "severe": 0.6}

# Video-level asymmetry gate: if median combined asymmetry across frames is
# below this value the face is consistently symmetric → not drooping.
# Calibrated from test videos:
#   normal doctor = 0.027, minor stroke = 0.065, severe stroke = 0.123
_VIDEO_ASYM_GATE = 0.040


def severity_from_likelihood(likelihood: float, threshold: float) -> str:
    if likelihood < threshold:
        return "none"
    if likelihood < threshold + _SEVERITY_THRESHOLDS["severe"]:
        return "mild"
    return "severe"


class VideoAggregator:
    """
    Collect per-frame droop probabilities + asymmetry scores, compute temporal score.

    Usage:
        agg = VideoAggregator(model, window=60)
        agg.add_frame_bytes(jpeg_bytes)
        result = agg.aggregate()
    """

    def __init__(self, model: DroopModel, window: int = 60):
        self.model = model
        self._probs: deque[float] = deque(maxlen=window)
        self._asym_scores: deque[float] = deque(maxlen=window)
        self._faces_missed = 0
        self._frames_seen = 0

    def add_frame_bytes(self, image_bytes: bytes) -> None:
        self._frames_seen += 1
        result = self.model.predict(image_bytes)
        if not result["face_detected"] or result["droop_probability"] is None:
            self._faces_missed += 1
            return
        self._probs.append(result["droop_probability"])
        if result.get("asymmetry_score") is not None:
            self._asym_scores.append(result["asymmetry_score"])

    def aggregate(self) -> dict:
        n = len(self._probs)
        if n == 0:
            return {
                "droop_likelihood": None,
                "fraction_frames_flagged": None,
                "peak_probability": None,
                "temporal_consistency": None,
                "is_drooping": None,
                "severity": None,
                "frames_analyzed": 0,
                "frames_skipped": self._faces_missed,
                "median_asymmetry": None,
            }

        probs = list(self._probs)
        threshold = self.model.threshold

        mean_prob = float(np.mean(probs))
        fraction_flagged = float(np.mean([p >= threshold for p in probs]))
        peak = float(np.max(probs))
        std = float(np.std(probs))
        consistency = float(max(0.0, 1.0 - std * 4))
        droop_likelihood = round(0.4 * mean_prob + 0.6 * fraction_flagged, 4)

        # Video-level asymmetry gate
        median_asym: float | None = None
        if self._asym_scores:
            median_asym = float(np.median(list(self._asym_scores)))
            if median_asym < _VIDEO_ASYM_GATE:
                # Face is consistently symmetric across frames → not drooping
                is_drooping = False
                severity = "none"
            else:
                is_drooping = droop_likelihood >= threshold
                severity = severity_from_likelihood(droop_likelihood, threshold)
        else:
            is_drooping = droop_likelihood >= threshold
            severity = severity_from_likelihood(droop_likelihood, threshold)

        return {
            "droop_likelihood": droop_likelihood,
            "fraction_frames_flagged": round(fraction_flagged, 4),
            "peak_probability": round(peak, 4),
            "temporal_consistency": round(consistency, 4),
            "is_drooping": is_drooping,
            "severity": severity,
            "frames_analyzed": n,
            "frames_skipped": self._faces_missed,
            "median_asymmetry": round(median_asym, 4) if median_asym is not None else None,
        }

    def reset(self) -> None:
        self._probs.clear()
        self._asym_scores.clear()
        self._faces_missed = 0
        self._frames_seen = 0


def analyze_video_file(
    video_bytes: bytes,
    model: DroopModel,
    sample_fps: float = 6.0,
    max_frames: int = 90,
) -> dict:
    """Extract frames from a video file and return aggregated droop assessment."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file. Ensure it is a valid MP4/MOV/AVI.")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(
            "Video: %.1f fps, %d total frames, sampling every %d frames",
            video_fps, total_frames, frame_interval,
        )

        agg = VideoAggregator(model, window=max_frames)
        frame_idx = 0
        processed = 0

        while processed < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                buf = io.BytesIO()
                from PIL import Image
                Image.fromarray(rgb).save(buf, format="JPEG", quality=85)
                agg.add_frame_bytes(buf.getvalue())
                processed += 1
            frame_idx += 1

        cap.release()
        result = agg.aggregate()
        result["video_duration_s"] = round(total_frames / video_fps, 2)
        return result

    finally:
        Path(tmp_path).unlink(missing_ok=True)
