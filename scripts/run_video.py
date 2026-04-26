"""
Quick test script — run any video through the full pipeline and print BPM readings.

Usage:
    python3 scripts/run_video.py <video_path> [--fps 60] [--mode adult|neonate]
"""
import sys
import argparse
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "vendor"))
sys.path.insert(0, str(BASE))

import cv2
from server.detector import HeadDetector
from server.tracker import HeadTracker
from server.pipeline import HeartRatePipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--fps", type=float, default=None, help="Override FPS (auto-detected if omitted)")
    parser.add_argument("--mode", default="adult", choices=["adult", "neonate"])
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = args.fps or cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {args.video}")
    print(f"Frames: {total} @ {fps:.1f}fps = {total/fps:.1f}s | mode: {args.mode}")

    detector = HeadDetector(
        cfg_path=str(BASE / "config/yolor_p6_head.cfg"),
        weights_path=str(BASE / "weights/yolor_head.pt"),
        device="cpu",
    )
    tracker = HeadTracker(config_path=str(BASE / "config/deep_sort.yaml"))
    pipeline = HeartRatePipeline(detector=detector, tracker=tracker, fps=fps, mode=args.mode)

    readings = []
    try:
        for i in range(total):
            ret, frame = cap.read()
            if not ret:
                break
            for result in pipeline.process_frame(frame):
                readings.append(result)
                print(f"  frame {i:4d} | track {result.track_id} | "
                      f"BPM={result.bpm:5.1f} | conf={result.confidence:.3f} | {result.status}")
    finally:
        cap.release()

    if not readings:
        print("No readings — buffer did not fill or no face detected")
        return

    bpms = [r.bpm for r in readings]
    confs = [r.confidence for r in readings]
    statuses = {}
    for r in readings:
        statuses[r.status] = statuses.get(r.status, 0) + 1

    print(f"\nSummary: {len(readings)} readings")
    print(f"  avg BPM:        {sum(bpms)/len(bpms):.1f}")
    print(f"  avg confidence: {sum(confs)/len(confs):.3f}")
    print(f"  status counts:  {statuses}")


if __name__ == "__main__":
    main()
