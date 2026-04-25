"""
ONNX Runtime inference wrapper for mouth droop detection.

Combines two signals:
  1. CNN probability  — EfficientNet-B0 on MediaPipe mouth crop
  2. Asymmetry score  — landmark-based left/right facial symmetry (mouth corners,
                        eye openings, brow heights) from the same MediaPipe pass
"""
import io
import json
import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from preprocess import detect_face_features

logger = logging.getLogger(__name__)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)

# Asymmetry score below this → face is symmetric → not drooping regardless of CNN.
# Calibrated from test videos: doctor=0.023, minor stroke=0.050, severe stroke=0.073.
_ASYM_GATE = 0.030

# When asymmetry is above the gate, blend CNN and asymmetry:
#   adjusted = cnn_prob * asym_weight   (asym_weight ∈ [0.5, 1.0])
# This softens CNN overconfidence on symmetric talking faces.
_ASYM_SCALE = 0.08   # asymmetry at which asym_weight reaches 1.0


class DroopModel:
    def __init__(self, model_path: str, threshold_path: str, image_size: int = 224):
        self.image_size = image_size

        sess_options = ort.SessionOptions()
        sess_options.inter_op_num_threads = 2
        sess_options.intra_op_num_threads = 4
        self.session = ort.InferenceSession(
            model_path,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

        with open(threshold_path) as f:
            data = json.load(f)
        self.threshold: float = data["threshold"]
        self.sensitivity: float = data.get("sensitivity", 0.0)
        self.specificity: float = data.get("specificity", 0.0)
        logger.info("Model loaded. Threshold=%.4f", self.threshold)

    def _run_cnn(self, mouth_crop: np.ndarray) -> float:
        """Run the ONNX CNN on a (H, W, 3) uint8 RGB mouth crop."""
        tensor = mouth_crop.transpose(2, 0, 1).astype(np.float32) / 255.0
        tensor = (tensor - IMAGENET_MEAN) / IMAGENET_STD
        logit = self.session.run(None, {self.input_name: tensor[np.newaxis]})[0][0, 0]
        return float(1 / (1 + np.exp(-logit)))

    def _adjust_prob(self, cnn_prob: float, asymmetry: float) -> float:
        """Blend CNN probability with asymmetry signal.

        - asymmetry < gate  → scale toward 0 (symmetric face = not drooping)
        - asymmetry >= gate → weight up to 1.0 (asymmetric face = trust CNN more)
        """
        if asymmetry < _ASYM_GATE:
            # Linearly scale down CNN prob when face is very symmetric
            asym_weight = 0.5 * (asymmetry / _ASYM_GATE)
        else:
            # Ramp from 0.5 → 1.0 as asymmetry increases from gate → scale
            t = min((asymmetry - _ASYM_GATE) / (_ASYM_SCALE - _ASYM_GATE), 1.0)
            asym_weight = 0.5 + 0.5 * t
        return cnn_prob * asym_weight

    def predict(self, image_bytes: bytes) -> dict:
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        rgb = np.array(pil, dtype=np.uint8)

        features = detect_face_features(rgb, target_size=self.image_size)

        if not features.face_detected or features.mouth_crop is None:
            return {
                "droop_probability": None,
                "is_drooping": None,
                "severity": None,
                "confidence": None,
                "face_detected": False,
                "asymmetry_score": None,
                "mouth_asymmetry": None,
                "eye_asymmetry": None,
                "brow_asymmetry": None,
            }

        cnn_prob = self._run_cnn(features.mouth_crop)
        adjusted = self._adjust_prob(cnn_prob, features.asymmetry_score)

        is_drooping = adjusted >= self.threshold

        if adjusted < self.threshold:
            severity = "none"
        elif adjusted < self.threshold + 0.15:
            severity = "mild"
        else:
            severity = "severe"

        distance = abs(adjusted - self.threshold)
        max_distance = max(self.threshold, 1 - self.threshold)
        confidence = float(min(distance / max_distance, 1.0))

        return {
            "droop_probability": round(adjusted, 4),
            "is_drooping": is_drooping,
            "severity": severity,
            "confidence": round(confidence, 4),
            "face_detected": True,
            "asymmetry_score": round(features.asymmetry_score, 4),
            "mouth_asymmetry": round(features.mouth_asymmetry, 4),
            "eye_asymmetry": round(features.eye_asymmetry, 4),
            "brow_asymmetry": round(features.brow_asymmetry, 4),
        }
