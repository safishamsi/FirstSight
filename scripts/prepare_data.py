"""
Prepare the YFP Mouth dataset for training:
  1. Collect mouth images from Mouth/Mouth/{Mild,Moderate,Moderate severe,Severe} mouth/
  2. Assign binary labels: Mild+Moderate=0 (not concerning), ModSev+Severe=1 (significant droop)
  3. Extract group keys from filenames (strip aug prefixes) for leakage-safe splitting
  4. GroupShuffleSplit 70/15/15 by group key
  5. Resize images to 224×224 and save to data/processed/
  6. Write data/splits.json manifest

Usage:
    python scripts/prepare_data.py --raw-dir <path/from/download_data.py>
"""
import argparse
import json
import logging
import random
import re
import sys
from pathlib import Path

import cv2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEVERITY_TO_LABEL = {
    "Mild mouth": 0,
    "Moderate mouth": 0,
    "Moderate severe mouth": 1,
    "Severe mouth": 1,
}

# Augmentation prefixes to strip when extracting base identity for group splitting
_AUG_PATTERNS = [
    re.compile(r"^rotated_?(?:minus)?\d+_"),
    re.compile(r"^noisy_\d+dB_"),
    re.compile(r"^cropped\d*_"),
    re.compile(r"^translated\w+_"),
    re.compile(r"^flipped_"),
]


def base_identity(filename: str) -> str:
    """Strip augmentation prefix to get the base frame identity for grouping."""
    stem = Path(filename).stem
    for pattern in _AUG_PATTERNS:
        m = pattern.match(stem)
        if m:
            return stem[m.end():]
    return stem


def patient_id_from_base(base: str) -> str:
    """Extract patient number from base identity string (e.g. '14_M.S_mouth23' → 'P014')."""
    m = re.match(r"^(\d+)_", base)
    if m:
        return f"P{int(m.group(1)):03d}"
    # Fall back to the whole base string (some files have no leading number)
    return base


def collect_samples(raw_dir: Path) -> list[dict]:
    mouth_root = raw_dir / "Mouth" / "Mouth"
    if not mouth_root.exists():
        raise FileNotFoundError(f"Mouth directory not found: {mouth_root}")

    samples = []
    for folder_name, label in SEVERITY_TO_LABEL.items():
        folder = mouth_root / folder_name
        if not folder.exists():
            logger.warning("Folder not found: %s", folder)
            continue
        files = list(folder.glob("*.bmp")) + list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
        for f in files:
            base = base_identity(f.name)
            pid = patient_id_from_base(base)
            samples.append({
                "path": str(f),
                "label": label,
                "severity_folder": folder_name,
                "base_identity": base,
                "patient_id": pid,
            })

    logger.info("Collected %d mouth images", len(samples))
    pos = sum(s["label"] for s in samples)
    logger.info("Label distribution: positive=%d (%.1f%%), negative=%d (%.1f%%)",
                pos, 100 * pos / len(samples),
                len(samples) - pos, 100 * (1 - pos / len(samples)))
    return samples


def group_split(samples: list[dict], val_frac=0.15, test_frac=0.15, seed=42) -> dict:
    """Split by patient_id to prevent data leakage."""
    patients = sorted({s["patient_id"] for s in samples})
    logger.info("Unique patient/group IDs: %d", len(patients))

    random.seed(seed)
    shuffled = list(patients)
    random.shuffle(shuffled)

    n = len(shuffled)
    n_test = max(1, int(n * test_frac))
    n_val = max(1, int(n * val_frac))

    test_set = set(shuffled[:n_test])
    val_set = set(shuffled[n_test:n_test + n_val])
    train_set = set(shuffled[n_test + n_val:])

    assert not (train_set & val_set), "Patient leakage: train/val"
    assert not (train_set & test_set), "Patient leakage: train/test"
    assert not (val_set & test_set), "Patient leakage: val/test"

    splits = {"train": [], "val": [], "test": []}
    for s in samples:
        pid = s["patient_id"]
        if pid in test_set:
            splits["test"].append(s)
        elif pid in val_set:
            splits["val"].append(s)
        else:
            splits["train"].append(s)

    for name, items in splits.items():
        pos = sum(i["label"] for i in items)
        logger.info("%s: %d images, %d positive (%.1f%%)",
                    name, len(items), pos, 100 * pos / max(len(items), 1))
    return splits


def resize_and_save(splits: dict, output_dir: Path, image_size: int = 224) -> dict:
    manifest = {"train": [], "val": [], "test": []}

    for split_name, items in splits.items():
        skipped = 0
        for item in items:
            img = cv2.imread(item["path"])
            if img is None:
                skipped += 1
                continue

            img_resized = cv2.resize(img, (image_size, image_size), interpolation=cv2.INTER_AREA)

            label_dir = "positive" if item["label"] == 1 else "negative"
            out_dir = output_dir / split_name / label_dir
            out_dir.mkdir(parents=True, exist_ok=True)

            # Prefix with patient ID to ensure uniqueness across patients
            fname = f"{item['patient_id']}_{Path(item['path']).name}"
            out_path = out_dir / fname
            cv2.imwrite(str(out_path), img_resized)

            manifest[split_name].append({
                "path": str(out_path),
                "label": item["label"],
                "patient_id": item["patient_id"],
                "severity_folder": item["severity_folder"],
            })

        logger.info("%s: saved %d, skipped %d", split_name,
                    len(manifest[split_name]), skipped)

    return manifest


def main(args):
    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    output_dir = Path(args.output_dir)
    samples = collect_samples(raw_dir)
    splits = group_split(samples, seed=args.seed)
    manifest = resize_and_save(splits, output_dir, image_size=args.image_size)

    manifest_path = Path(args.splits_json)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest saved → %s", manifest_path)
    logger.info("Done. Next: python train.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", required=True)
    p.add_argument("--output-dir", default="data/processed")
    p.add_argument("--splits-json", default="data/splits.json")
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--seed", type=int, default=42)
    main(p.parse_args())
