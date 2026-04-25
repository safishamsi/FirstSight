"""
Dataset and preprocessing unit tests.
Key test: RandomHorizontalFlip must NOT be present in any transform.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
import torchvision.transforms as T

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dataset import build_transforms, IMAGENET_MEAN, IMAGENET_STD


def _flatten_transforms(transform) -> list:
    """Recursively collect all transform objects."""
    out = []
    if isinstance(transform, T.Compose):
        for t in transform.transforms:
            out.extend(_flatten_transforms(t))
    else:
        out.append(transform)
    return out


@pytest.mark.parametrize("split", ["train", "val", "test"])
def test_no_horizontal_flip(split):
    """
    Horizontal flip is forbidden for asymmetry-dependent tasks.
    It swaps the droopy side with the normal side, corrupting labels.
    """
    transforms = build_transforms(split)
    all_transforms = _flatten_transforms(transforms)
    flip_types = [type(t) for t in all_transforms if isinstance(t, T.RandomHorizontalFlip)]
    assert len(flip_types) == 0, (
        f"RandomHorizontalFlip found in '{split}' transforms. "
        "This destroys the asymmetry signal — remove it."
    )


def test_train_has_augmentation():
    train_t = build_transforms("train")
    all_t = _flatten_transforms(train_t)
    aug_types = {type(t) for t in all_t}
    assert T.RandomRotation in aug_types, "Train transforms should include RandomRotation"
    assert T.ColorJitter in aug_types, "Train transforms should include ColorJitter"


def test_val_has_no_augmentation():
    val_t = build_transforms("val")
    all_t = _flatten_transforms(val_t)
    aug_types = {type(t) for t in all_t}
    assert T.RandomRotation not in aug_types
    assert T.ColorJitter not in aug_types
    assert T.GaussianBlur not in aug_types


def test_both_splits_have_normalize():
    for split in ["train", "val", "test"]:
        all_t = _flatten_transforms(build_transforms(split))
        norm = [t for t in all_t if isinstance(t, T.Normalize)]
        assert len(norm) == 1, f"Expected exactly one Normalize in '{split}' transforms"
        assert norm[0].mean == IMAGENET_MEAN
        assert norm[0].std == IMAGENET_STD


def test_output_tensor_shape():
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (300, 250, 3), dtype=np.uint8))
    for split in ["train", "val", "test"]:
        t = build_transforms(split, image_size=224)
        tensor = t(img)
        assert tensor.shape == (3, 224, 224), f"Wrong shape for split={split}: {tensor.shape}"
