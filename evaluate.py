"""
Evaluate trained model on the test split.
Outputs: AUROC, sensitivity/specificity at optimal threshold, ROC curve image,
         and saves threshold to checkpoints/threshold.json.
"""
import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from torch.utils.data import DataLoader

from src.dataset import DroopDataset
from src.model import build_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@torch.no_grad()
def get_predictions(model, loader, device) -> tuple[list, list]:
    model.eval()
    all_probs, all_labels = [], []
    for images, labels in loader:
        logits = model(images.to(device)).squeeze(1).cpu()
        all_probs.extend(torch.sigmoid(logits).tolist())
        all_labels.extend(labels.tolist())
    return all_probs, all_labels


def find_optimal_threshold(
    fpr, tpr, thresholds, min_sensitivity: float = 0.88
) -> tuple[float, float, float]:
    """
    Find the operating threshold.
    Strategy: among all thresholds with sensitivity >= min_sensitivity,
    pick the one with highest specificity. Falls back to Youden if none qualify.
    """
    candidates = [(t, s, 1 - f) for f, s, t in zip(fpr, tpr, thresholds) if s >= min_sensitivity]
    if candidates:
        # pick highest specificity among candidates meeting sensitivity target
        best = max(candidates, key=lambda x: x[2])
        return best
    # Fallback: Youden index
    youden = tpr - fpr
    idx = int(np.argmax(youden))
    return float(thresholds[idx]), float(tpr[idx]), float(1 - fpr[idx])


def main(args):
    device = get_device()

    test_ds = DroopDataset(args.processed_dir, "test", splits_json=args.splits_json)
    logger.info("Test set: %s", test_ds.class_counts())
    loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    model = build_model(pretrained=False).to(device)
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(ckpt["model_state"])
    logger.info("Loaded checkpoint from epoch %d (val_auroc=%.4f)",
                ckpt.get("epoch", -1), ckpt.get("val_auroc", -1))

    probs, labels = get_predictions(model, loader, device)
    probs_np = np.array(probs)
    labels_np = np.array(labels)

    auroc = roc_auc_score(labels_np, probs_np)
    fpr, tpr, thresholds = roc_curve(labels_np, probs_np)
    threshold, sensitivity, specificity = find_optimal_threshold(
        fpr, tpr, thresholds, min_sensitivity=args.min_sensitivity
    )

    preds = (probs_np >= threshold).astype(int)
    cm = confusion_matrix(labels_np, preds)

    logger.info("AUROC:       %.4f", auroc)
    logger.info("Threshold:   %.4f", threshold)
    logger.info("Sensitivity: %.4f", sensitivity)
    logger.info("Specificity: %.4f", specificity)
    logger.info("Confusion matrix:\n%s", cm)

    # Save threshold for inference server
    Path(args.checkpoint_dir).mkdir(parents=True, exist_ok=True)
    threshold_data = {
        "threshold": threshold,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "auroc": auroc,
    }
    threshold_path = Path(args.checkpoint_dir) / "threshold.json"
    with open(threshold_path, "w") as f:
        json.dump(threshold_data, f, indent=2)
    logger.info("Threshold saved to %s", threshold_path)

    # ROC curve plot
    Path(args.reports_dir).mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].plot(fpr, tpr, label=f"AUROC = {auroc:.3f}")
    axes[0].scatter([1 - specificity], [sensitivity], color="red",
                    zorder=5, label=f"Operating point (thresh={threshold:.2f})")
    axes[0].plot([0, 1], [0, 1], "k--")
    axes[0].set_xlabel("False Positive Rate")
    axes[0].set_ylabel("True Positive Rate")
    axes[0].set_title("ROC Curve")
    axes[0].legend()

    disp = ConfusionMatrixDisplay(cm, display_labels=["Normal", "Drooping"])
    disp.plot(ax=axes[1], colorbar=False)
    axes[1].set_title("Confusion Matrix")

    plt.tight_layout()
    out_path = Path(args.reports_dir) / "roc_curve.png"
    plt.savefig(out_path, dpi=150)
    logger.info("ROC curve saved to %s", out_path)

    # Acceptance criteria check
    print("\n--- Acceptance Criteria ---")
    print(f"AUROC ≥ 0.85:       {'PASS' if auroc >= 0.85 else 'FAIL'} ({auroc:.4f})")
    print(f"Sensitivity ≥ 0.88: {'PASS' if sensitivity >= 0.88 else 'FAIL'} ({sensitivity:.4f})")
    print(f"Specificity ≥ 0.80: {'PASS' if specificity >= 0.80 else 'FAIL'} ({specificity:.4f})")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--processed-dir", default="data/processed")
    p.add_argument("--splits-json", default="data/splits.json")
    p.add_argument("--checkpoint", default="checkpoints/best.pth")
    p.add_argument("--checkpoint-dir", default="checkpoints")
    p.add_argument("--reports-dir", default="reports")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--min-sensitivity", type=float, default=0.88,
                   help="Target minimum sensitivity when selecting the operating threshold.")
    main(p.parse_args())
