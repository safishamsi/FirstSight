"""
Two-phase training:
  Phase 1 (epochs 1..unfreeze_epoch): backbone frozen, head only
  Phase 2 (epochs unfreeze_epoch+1..epochs): full fine-tune with lower LR
"""
import argparse
import logging
from pathlib import Path

import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader

from src.dataset import DroopDataset
from src.model import build_model, freeze_backbone, unfreeze_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def train_one_epoch(model, loader, optimizer, criterion, device) -> float:
    model.train()
    total_loss = 0.0
    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device).unsqueeze(1)
        optimizer.zero_grad()
        loss = criterion(model(images), labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model, loader, device) -> dict:
    model.eval()
    probs, labels = [], []
    for images, lbls in loader:
        logits = model(images.to(device)).squeeze(1).cpu()
        probs.extend(torch.sigmoid(logits).tolist())
        labels.extend(lbls.tolist())
    auroc = roc_auc_score(labels, probs) if len(set(labels)) > 1 else 0.0
    return {"auroc": auroc, "probs": probs, "labels": labels}


def run_phase(model, loader, val_loader, optimizer, criterion, scheduler,
              device, epochs_range, checkpoint_dir, best_auroc):
    for epoch in epochs_range:
        loss = train_one_epoch(model, loader, optimizer, criterion, device)
        metrics = evaluate(model, val_loader, device)
        scheduler.step()
        logger.info("Epoch %03d | loss %.4f | val_auroc %.4f", epoch, loss, metrics["auroc"])
        if metrics["auroc"] > best_auroc:
            best_auroc = metrics["auroc"]
            path = Path(checkpoint_dir) / "best.pth"
            torch.save({"epoch": epoch, "model_state": model.state_dict(),
                        "val_auroc": best_auroc}, path)
            logger.info("  → saved best (auroc=%.4f)", best_auroc)
    return best_auroc


def main(args):
    device = get_device()
    logger.info("Device: %s", device)

    train_ds = DroopDataset(args.processed_dir, "train", splits_json=args.splits_json)
    val_ds = DroopDataset(args.processed_dir, "val", splits_json=args.splits_json)
    logger.info("Train %s | Val %s", train_ds.class_counts(), val_ds.class_counts())

    workers = 0 if device.type == "mps" else args.workers
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=workers, pin_memory=(device.type == "cuda"))
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=workers)

    model = build_model(pretrained=True).to(device)
    if args.pos_weight is not None:
        pos_weight = torch.tensor(args.pos_weight)
        logger.info("Using manual pos_weight=%.2f (favours recall)", args.pos_weight)
    else:
        pos_weight = train_ds.pos_weight()
        logger.info("Computed pos_weight=%.4f from class counts", pos_weight.item())
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))
    Path(args.checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # --- Phase 1: head only ---
    freeze_backbone(model)
    opt1 = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()), lr=1e-3, weight_decay=1e-4
    )
    sched1 = torch.optim.lr_scheduler.CosineAnnealingLR(opt1, T_max=args.unfreeze_epoch)
    best = run_phase(model, train_loader, val_loader, opt1, criterion, sched1,
                     device, range(1, args.unfreeze_epoch + 1),
                     args.checkpoint_dir, best_auroc=0.0)

    # --- Phase 2: full fine-tune ---
    unfreeze_all(model)
    opt2 = torch.optim.AdamW([
        {"params": model.classifier.parameters(), "lr": 1e-4},
        {"params": [p for n, p in model.named_parameters() if "classifier" not in n], "lr": 1e-5},
    ], weight_decay=1e-4)
    remaining = args.epochs - args.unfreeze_epoch
    sched2 = torch.optim.lr_scheduler.CosineAnnealingLR(opt2, T_max=remaining)
    best = run_phase(model, train_loader, val_loader, opt2, criterion, sched2,
                     device, range(args.unfreeze_epoch + 1, args.epochs + 1),
                     args.checkpoint_dir, best_auroc=best)

    logger.info("Done. Best val AUROC: %.4f", best)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--processed-dir", default="data/processed")
    p.add_argument("--splits-json", default="data/splits.json")
    p.add_argument("--checkpoint-dir", default="checkpoints")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--unfreeze-epoch", type=int, default=6)
    p.add_argument("--pos-weight", type=float, default=None,
                   help="Manual BCEWithLogitsLoss pos_weight. Set >1 to boost sensitivity.")
    main(p.parse_args())
