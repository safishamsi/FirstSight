"""
Reprocess existing YFP palsy images (label=1) through MediaPipe mouth crop
so training and inference use the same preprocessing pipeline.

Previously YFP images were just resized; LFW normals were MediaPipe-cropped.
This fixes that inconsistency by running MediaPipe on all YFP images in-place.

Usage:
    python scripts/reprocess_yfp_with_mediapipe.py
"""
import json
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preprocess import crop_mouth_region

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def reprocess(splits_json: str = "data/splits.json", image_size: int = 224) -> None:
    with open(splits_json) as f:
        manifest = json.load(f)

    total, converted, skipped = 0, 0, 0

    for split in ("train", "val", "test"):
        for entry in manifest[split]:
            if entry["label"] != 1:
                continue  # only reprocess positive (YFP palsy) images
            if entry.get("patient_id") == "normal":
                continue

            path = Path(entry["path"])
            if not path.exists():
                logger.warning("Missing file: %s", path)
                skipped += 1
                continue

            total += 1
            img = np.array(Image.open(path).convert("RGB"))
            crop = crop_mouth_region(img, target_size=image_size)

            if crop is None:
                logger.debug("No face detected in %s, keeping original", path.name)
                skipped += 1
                continue

            # Overwrite in-place with the MediaPipe mouth crop
            cv2.imwrite(str(path), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
            converted += 1

            if converted % 200 == 0:
                logger.info("Progress: %d/%d converted", converted, total)

    logger.info(
        "Done. %d positive images reprocessed, %d skipped (no face / missing).",
        converted, skipped,
    )
    logger.info("Next: python train.py --pos-weight 1.5")


if __name__ == "__main__":
    reprocess()
