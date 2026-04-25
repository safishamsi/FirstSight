import json
from pathlib import Path

import torch
import torchvision.transforms as T
from PIL import Image
from torch.utils.data import Dataset

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transforms(split: str, image_size: int = 224) -> T.Compose:
    """
    Augmentation for train split only.
    IMPORTANT: RandomHorizontalFlip is intentionally absent — flipping swaps the
    droopy side with the normal side, destroying the asymmetry signal.
    """
    if split == "train":
        return T.Compose([
            T.Resize((image_size, image_size)),
            T.RandomRotation(degrees=12),
            T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.1),
            T.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0)),
            T.RandomVerticalFlip(p=0.2),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
    return T.Compose([
        T.Resize((image_size, image_size)),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


class DroopDataset(Dataset):
    """
    Loads face-aligned images from data/processed/ using a splits.json manifest.

    splits.json format:
        {"train": [{"path": "/abs/path.jpg", "label": 0}, ...], "val": [...], "test": [...]}

    Falls back to directory structure if splits.json is absent:
        processed_dir/<split>/positive/*.jpg
        processed_dir/<split>/negative/*.jpg
    """

    def __init__(
        self,
        processed_dir: str,
        split: str,
        splits_json: str | None = None,
        image_size: int = 224,
    ):
        self.split = split
        self.transform = build_transforms(split, image_size)
        self.samples: list[tuple[str, int]] = []

        if splits_json and Path(splits_json).exists():
            self._load_from_manifest(splits_json, split)
        else:
            self._load_from_directory(processed_dir, split)

        if not self.samples:
            raise ValueError(
                f"No samples found for split='{split}'. "
                f"Run scripts/prepare_data.py first."
            )

    def _load_from_manifest(self, splits_json: str, split: str) -> None:
        with open(splits_json) as f:
            manifest = json.load(f)
        for item in manifest.get(split, []):
            self.samples.append((item["path"], int(item["label"])))

    def _load_from_directory(self, processed_dir: str, split: str) -> None:
        base = Path(processed_dir) / split
        for label_name, label in [("positive", 1), ("negative", 0)]:
            label_dir = base / label_name
            if label_dir.exists():
                for p in sorted(label_dir.glob("*.jpg")) + sorted(label_dir.glob("*.png")):
                    self.samples.append((str(p), label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        return self.transform(image), torch.tensor(label, dtype=torch.float32)

    def pos_weight(self) -> torch.Tensor:
        labels = [s[1] for s in self.samples]
        n_pos = sum(labels)
        n_neg = len(labels) - n_pos
        if n_pos == 0:
            return torch.tensor(1.0)
        return torch.tensor(n_neg / n_pos)

    def class_counts(self) -> dict:
        labels = [s[1] for s in self.samples]
        return {"positive": sum(labels), "negative": len(labels) - sum(labels), "total": len(labels)}
