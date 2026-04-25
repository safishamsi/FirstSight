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

WEIGHTS_PATH = BASE / "weights/yolor_head.pt"
VIDEO_PATH = Path("/home/safi/heart_rate_detection/demo/baby.mp4")


@pytest.mark.skipif(
    not WEIGHTS_PATH.exists() or not VIDEO_PATH.exists(),
    reason="Weights or test video not present"
)
def test_neonatal_bpm_in_expected_range():
    detector = HeadDetector(
        cfg_path=str(BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(WEIGHTS_PATH),
        device="cpu",
    )
    tracker = HeadTracker(config_path=str(BASE / "config/deep_sort.yaml"))
    pipeline = HeartRatePipeline(detector=detector, tracker=tracker,
                                  fps=30.0, mode="neonate")

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    bpm_readings = []

    try:
        for _ in range(BUFFER_SIZE + 30):
            ret, frame = cap.read()
            if not ret:
                break
            for result in pipeline.process_frame(frame):
                if result.confidence > 0.1:
                    bpm_readings.append(result.bpm)
    finally:
        cap.release()

    assert len(bpm_readings) > 0, "No BPM readings produced — check head detection"
    avg_bpm = sum(bpm_readings) / len(bpm_readings)
    # Neonate bandpass cap is 2.67 Hz = 160.2 BPM — upper bound reflects pipeline limit
    assert 100 <= avg_bpm <= 160, f"BPM {avg_bpm:.1f} outside expected neonatal range"
