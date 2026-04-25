"""
Benchmark ONNX model inference latency on CPU.
Reports p50 and p99 over N runs with a real image or a synthetic one.

Usage:
    python scripts/benchmark_latency.py
    python scripts/benchmark_latency.py --image path/to/face.jpg --n 200
"""
import argparse
import logging
import time

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(args):
    import onnxruntime as ort

    sess = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name

    if args.image:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from preprocess import align_and_crop_face
        face = align_and_crop_face(args.image, target_size=224)
        if face is None:
            raise ValueError("No face detected in the provided image.")
        inp = face.transpose(2, 0, 1).astype(np.float32)[np.newaxis] / 255.0
    else:
        inp = np.random.rand(1, 3, 224, 224).astype(np.float32)
        logger.info("No image provided — using random noise input")

    # Warm-up
    for _ in range(10):
        sess.run(None, {input_name: inp})

    latencies_ms = []
    for _ in range(args.n):
        t0 = time.perf_counter()
        sess.run(None, {input_name: inp})
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    latencies_ms.sort()
    p50 = latencies_ms[int(args.n * 0.50)]
    p95 = latencies_ms[int(args.n * 0.95)]
    p99 = latencies_ms[int(args.n * 0.99)]

    print(f"\nLatency over {args.n} runs:")
    print(f"  p50:  {p50:.1f} ms")
    print(f"  p95:  {p95:.1f} ms")
    print(f"  p99:  {p99:.1f} ms")
    print(f"  mean: {sum(latencies_ms)/len(latencies_ms):.1f} ms")

    target_ms = 300
    status = "PASS" if p99 < target_ms else "FAIL"
    print(f"\np99 < {target_ms} ms: {status}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="model/droop_model.onnx")
    p.add_argument("--image", default=None, help="Optional real image path for realistic benchmark")
    p.add_argument("--n", type=int, default=100)
    main(p.parse_args())
