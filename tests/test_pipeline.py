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
    # Constant-value frame: zero texture → zero gradient → Farneback gives provably
    # exact-zero flow, not just approximately-zero (random frames can exceed threshold).
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    results = []
    for _ in range(150):
        results = pipeline.process_frame(frame)
    assert len(results) == 1
    assert results[0].track_id == 1
    assert isinstance(results[0].bpm, float)
    assert isinstance(results[0].confidence, float)
