"""
Download the LFW face dataset, crop mouth regions with MediaPipe,
and add them as label=0 (normal / no significant droop) to the existing
data/splits.json manifest.

Target: ~1300 normal mouth crops added across train/val/test.

Usage:
    python scripts/add_normal_faces.py
"""
import argparse
import json
import logging
import random
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preprocess import crop_mouth_region

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# How many normal samples to add per split
TARGETS = {"train": 1000, "val": 100, "test": 200}


def download_lfw() -> Path:
    import kagglehub
    logger.info("Downloading LFW face dataset (~170 MB)…")
    path = kagglehub.dataset_download("jessicali9530/lfw-dataset")
    logger.info("Dataset at: %s", path)
    return Path(path)


def collect_face_images(lfw_root: Path) -> list[Path]:
    images = list(lfw_root.rglob("*.jpg")) + list(lfw_root.rglob("*.png"))
    random.shuffle(images)
    logger.info("Found %d face images in LFW", len(images))
    return images


def process_normal_faces(
    face_images: list[Path],
    processed_dir: Path,
    targets: dict,
    image_size: int = 224,
) -> dict[str, list[dict]]:
    """Crop mouth regions and save; return manifest entries per split."""
    new_entries: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    added = {k: 0 for k in targets}

    for img_path in face_images:
        # Determine which split still needs samples
        split = next(
            (s for s in ("train", "val", "test") if added[s] < targets[s]),
            None,
        )
        if split is None:
            break  # all splits full

        mouth = crop_mouth_region(str(img_path), target_size=image_size)
        if mouth is None:
            continue  # no face detected

        out_dir = processed_dir / split / "negative"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"normal_{img_path.stem}.jpg"
        out_path = out_dir / out_name
        cv2.imwrite(str(out_path), cv2.cvtColor(mouth, cv2.COLOR_RGB2BGR))

        new_entries[split].append({
            "path": str(out_path),
            "label": 0,
            "patient_id": "normal",
            "severity_folder": "normal",
        })
        added[split] += 1

        if sum(added.values()) % 100 == 0:
            logger.info("Progress: %s", added)

    for split, count in added.items():
        logger.info("%s: added %d normal samples (target %d)", split, count, targets[split])

    return new_entries


def update_manifest(splits_json: Path, new_entries: dict) -> None:
    with open(splits_json) as f:
        manifest = json.load(f)

    for split, entries in new_entries.items():
        manifest[split].extend(entries)

    with open(splits_json, "w") as f:
        json.dump(manifest, f, indent=2)

    for split in ("train", "val", "test"):
        pos = sum(1 for e in manifest[split] if e["label"] == 1)
        neg = sum(1 for e in manifest[split] if e["label"] == 0)
        logger.info("%s — positive: %d, negative: %d", split, pos, neg)


def main(args):
    random.seed(args.seed)
    lfw_root = download_lfw()
    face_images = collect_face_images(lfw_root)

    processed_dir = Path(args.processed_dir)
    new_entries = process_normal_faces(
        face_images,
        processed_dir,
        targets=TARGETS,
        image_size=args.image_size,
    )

    splits_json = Path(args.splits_json)
    update_manifest(splits_json, new_entries)
    logger.info("Manifest updated → %s", splits_json)
    logger.info("Done. Now retrain: python train.py --pos-weight 1.5")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--processed-dir", default="data/processed")
    p.add_argument("--splits-json", default="data/splits.json")
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--seed", type=int, default=42)
    main(p.parse_args())
