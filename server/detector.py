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
        self.model.load_state_dict(state["model"] if "model" in state else state)
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
