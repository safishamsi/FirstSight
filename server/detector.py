import os
import urllib.request
from pathlib import Path
import torch
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from detector.darknet import Darknet
from utils.general import non_max_suppression, scale_coords
from utils.datasets import letterbox
from utils.torch_utils import select_device

_MP_MODEL_PATH = "/tmp/blaze_face_short_range.tflite"
_MP_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def _ensure_mp_model() -> None:
    if not os.path.exists(_MP_MODEL_PATH):
        urllib.request.urlretrieve(_MP_MODEL_URL, _MP_MODEL_PATH)


class HeadDetector:
    def __init__(self, cfg_path: str, weights_path: str,
                 device: str = "0", img_size: int = 1280,
                 conf_thres: float = 0.3, iou_thres: float = 0.4):
        self.device = select_device(device)
        self.img_size = img_size
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self._mp_detector = None  # lazy-init: only created if YOLOR misses

        self.model = Darknet(cfg_path, img_size).to(self.device)
        state = torch.load(weights_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(state["model"] if "model" in state else state)
        self.model.eval()
        if self.device.type != "cpu":
            self.model.half()

    def _get_mp_detector(self):
        if self._mp_detector is None:
            _ensure_mp_model()
            base_options = mp_python.BaseOptions(model_asset_path=_MP_MODEL_PATH)
            options = mp_vision.FaceDetectorOptions(
                base_options=base_options, min_detection_confidence=0.4
            )
            self._mp_detector = mp_vision.FaceDetector.create_from_options(options)
        return self._mp_detector

    def _mediapipe_detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._get_mp_detector().detect(mp_image)
        detections = []
        for det in result.detections:
            bb = det.bounding_box
            x1 = max(0, bb.origin_x)
            y1 = max(0, bb.origin_y)
            x2 = min(w, bb.origin_x + bb.width)
            y2 = min(h, bb.origin_y + bb.height)
            detections.append((x1, y1, x2, y2, det.categories[0].score))
        return detections

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """
        frame: BGR numpy array (H, W, 3)
        Returns list of (x1, y1, x2, y2, confidence)
        Falls back to MediaPipe when YOLOR finds nothing — handles rotated/top-down faces.
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

        if not results:
            results = self._mediapipe_detect(frame)

        return results
