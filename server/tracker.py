from pathlib import Path
import numpy as np
import yaml

from tracker.deep_sort import DeepSort


class HeadTracker:
    def __init__(self, config_path: str):
        config_path = Path(config_path)
        with open(config_path) as f:
            cfg = yaml.safe_load(f)["DEEPSORT"]
        reid_ckpt = str(config_path.parent.parent / cfg["REID_CKPT"])
        if not Path(reid_ckpt).exists():
            raise FileNotFoundError(f"DeepSort ReID weights not found: {reid_ckpt}")
        self.tracker = DeepSort(
            reid_ckpt,
            max_dist=cfg["MAX_DIST"],
            max_age=cfg["MAX_AGE"],
            n_init=cfg["N_INIT"],
            nn_budget=cfg["NN_BUDGET"],
            use_cuda=False,
        )

    def update(self, detections: list[tuple[int, int, int, int, float]],
               frame: np.ndarray) -> list[tuple[int, int, int, int, int]]:
        """
        detections: list of (x1, y1, x2, y2, conf)
        frame: BGR numpy array
        Returns list of (x1, y1, x2, y2, track_id)
        """
        if not detections:
            return []

        bbox_xywh = np.array([
            [(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1]
            for x1, y1, x2, y2, _ in detections
        ])
        confidences = np.array([c for *_, c in detections])
        oids = np.zeros(len(detections), dtype=int)

        outputs = self.tracker.update(bbox_xywh, confidences, oids, frame)
        return [(int(o[0]), int(o[1]), int(o[2]), int(o[3]), int(o[4]))
                for o in outputs]
