import sys
import cv2
import numpy as np
import pytest
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "vendor"))

from server.detector import HeadDetector
from server.tracker import HeadTracker
from server.pipeline import HeartRatePipeline, BUFFER_SIZE

WEIGHTS_PATH = BASE.parent / "weights/yolor_head.pt"
DEMO_DIR = Path("/home/safi/heart_rate_detection/demo")


def _run_video(video_path: Path, mode: str) -> list[float]:
    detector = HeadDetector(
        cfg_path=str(BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(WEIGHTS_PATH),
        device="cpu",
    )
    tracker = HeadTracker(config_path=str(BASE / "config/deep_sort.yaml"))
    pipeline = HeartRatePipeline(detector=detector, tracker=tracker, fps=30.0, mode=mode)

    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    bpm_readings = []

    try:
        for _ in range(total):
            ret, frame = cap.read()
            if not ret:
                break
            for result in pipeline.process_frame(frame):
                if result.confidence > 0.1:
                    bpm_readings.append(result.bpm)
    finally:
        cap.release()

    return bpm_readings


@pytest.mark.skipif(
    not WEIGHTS_PATH.exists() or not (DEMO_DIR / "baby.mp4").exists(),
    reason="Weights or test video not present"
)
def test_neonatal_bpm_in_expected_range():
    readings = _run_video(DEMO_DIR / "baby.mp4", mode="neonate")
    assert len(readings) > 0, "No BPM readings produced — check head detection"
    avg_bpm = sum(readings) / len(readings)
    # Neonate bandpass cap is 2.67 Hz = 160.2 BPM — upper bound reflects pipeline limit
    assert 100 <= avg_bpm <= 160, f"BPM {avg_bpm:.1f} outside expected neonatal range"


@pytest.mark.skipif(
    not WEIGHTS_PATH.exists() or not (DEMO_DIR / "baby2.mp4").exists(),
    reason="Weights or baby2.mp4 not present"
)
def test_neonatal_bpm_baby2_in_expected_range():
    readings = _run_video(DEMO_DIR / "baby2.mp4", mode="neonate")
    assert len(readings) > 0, "No BPM readings from baby2.mp4 — check head detection"
    avg_bpm = sum(readings) / len(readings)
    assert 100 <= avg_bpm <= 160, f"BPM {avg_bpm:.1f} outside expected neonatal range"
