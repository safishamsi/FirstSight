"""
Export trained PyTorch model to ONNX and apply INT8 dynamic quantization.
Output: model/droop_model.onnx

Usage:
    python scripts/export_onnx.py --checkpoint checkpoints/best.pth
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.model import build_model

    device = torch.device("cpu")  # export from CPU for portability
    model = build_model(pretrained=False).to(device)
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    logger.info("Loaded checkpoint: epoch %d, val_auroc %.4f",
                ckpt.get("epoch", -1), ckpt.get("val_auroc", -1))

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    fp32_path = str(Path(args.output_dir) / "droop_model_fp32.onnx")
    quant_path = str(Path(args.output_dir) / "droop_model.onnx")

    dummy = torch.zeros(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy,
        fp32_path,
        input_names=["image"],
        output_names=["logit"],
        dynamic_axes={"image": {0: "batch"}, "logit": {0: "batch"}},
        opset_version=17,
        dynamo=False,  # legacy TorchScript exporter; dynamo export breaks ort quantizer
    )
    logger.info("FP32 ONNX exported to %s", fp32_path)

    # INT8 dynamic quantization (weights only; activations stay FP32 — safe for CPU)
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(fp32_path, quant_path, weight_type=QuantType.QInt8)
    logger.info("INT8 quantized model saved to %s", quant_path)

    # Verify output shape
    import onnxruntime as ort
    sess = ort.InferenceSession(quant_path, providers=["CPUExecutionProvider"])
    dummy_np = np.zeros((1, 3, 224, 224), dtype=np.float32)
    out = sess.run(None, {"image": dummy_np})
    assert out[0].shape == (1, 1), f"Unexpected output shape: {out[0].shape}"
    logger.info("Verification passed. Output shape: %s", out[0].shape)
    logger.info("Export complete → %s", quant_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default="checkpoints/best.pth")
    p.add_argument("--output-dir", default="model")
    main(p.parse_args())
