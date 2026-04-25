"""
Download normal talking-face videos, extract mouth-crop frames via MediaPipe,
and add as label=0 negatives.

Fixes the false-positive problem where static LFW portrait negatives
don't cover normal speech mouth movements.

Usage:
    python scripts/add_talking_faces.py
"""
import argparse
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preprocess import crop_mouth_region

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Normal healthy people talking to camera.
# (url, skip_seconds) — skip_seconds bypasses intros/title cards.
TALKING_VIDEOS = [
    # Doctor explaining stroke (known false positive — normal face, lots of mouth movement)
    ("https://www.youtube.com/watch?v=Ioujf38UnaU", 10),
    # TED talks — skip past animated intros
    ("https://www.youtube.com/watch?v=8jPQjjsBbIc", 120),
    ("https://www.youtube.com/watch?v=arj7oStGLkU", 90),
    ("https://www.youtube.com/watch?v=6wXkI4t7nuc", 90),
    ("https://www.youtube.com/watch?v=RcGyVTAoXEU", 90),
    ("https://www.youtube.com/watch?v=Unzc731iCUY", 90),
    ("https://www.youtube.com/watch?v=iG9CE55wbtY", 90),
    ("https://www.youtube.com/watch?v=UF8uR6Z6KLc", 90),
    ("https://www.youtube.com/watch?v=D1R-jKKp3NA", 90),
    ("https://www.youtube.com/watch?v=0e0U5XaUNhI", 90),
]

# Total samples to add per split across all videos
TARGETS = {"train": 800, "val": 100, "test": 160}


def download_video(url: str, out_path: Path) -> bool:
    """Download at ≤360p with yt-dlp (applies HLS fixup automatically)."""
    cmd = ["yt-dlp", "-f", "best[height<=360]/bestvideo[height<=360]+bestaudio/best",
           "--no-playlist", "-o", str(out_path), url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        logger.warning("Download failed for %s: %s", url, result.stderr[-300:])
        return False
    logger.info("Downloaded %.1f MB", out_path.stat().st_size / 1e6)
    return True


def extract_frames_ffmpeg(video_path: Path, skip_s: int, fps: float = 2.0) -> list[np.ndarray]:
    """Use ffmpeg to extract frames at `fps` starting from `skip_s` seconds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_pattern = str(Path(tmpdir) / "frame_%05d.jpg")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(skip_s),
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "3",
            "-frames:v", "600",  # cap at 300s worth at 2fps
            out_pattern,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("ffmpeg failed: %s", result.stderr[-200:])
            return []

        frames = []
        for jpg in sorted(Path(tmpdir).glob("frame_*.jpg")):
            frame = cv2.imread(str(jpg))
            if frame is not None:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        logger.info("Extracted %d frames", len(frames))
        return frames


def frames_to_mouth_crops(frames: list[np.ndarray], image_size: int = 224) -> list[np.ndarray]:
    crops = []
    for frame in frames:
        crop = crop_mouth_region(frame, target_size=image_size)
        if crop is not None:
            crops.append(crop)
    return crops


def main(args):
    processed_dir = Path(args.processed_dir)
    splits_json = Path(args.splits_json)

    with open(splits_json) as f:
        manifest = json.load(f)

    total_added = {s: 0 for s in TARGETS}

    for url, skip_s in TALKING_VIDEOS:
        if all(total_added[s] >= TARGETS[s] for s in TARGETS):
            break

        video_id = url.split("watch?v=")[-1]
        tmp_video = Path(f"/tmp/talking_{video_id}.mp4")

        logger.info("Downloading %s (skip %ds)…", video_id, skip_s)
        if not download_video(url, tmp_video):
            continue

        try:
            frames = extract_frames_ffmpeg(tmp_video, skip_s=skip_s, fps=2.0)
            if not frames:
                continue

            crops = frames_to_mouth_crops(frames, image_size=args.image_size)
            logger.info("%s: %d/%d frames yielded mouth crops", video_id, len(crops), len(frames))

            if not crops:
                continue

            # Distribute crops across splits proportionally
            crop_idx = 0
            for split in ("train", "val", "test"):
                need = TARGETS[split] - total_added[split]
                if need <= 0 or crop_idx >= len(crops):
                    continue

                # Take proportional share of this video's crops
                alloc = min(need, max(1, int(len(crops) * TARGETS[split] / sum(TARGETS.values()))))
                alloc = min(alloc, len(crops) - crop_idx)

                out_dir = processed_dir / split / "negative"
                out_dir.mkdir(parents=True, exist_ok=True)

                for i in range(alloc):
                    crop = crops[crop_idx + i]
                    fname = f"talking_{video_id}_{split}_{total_added[split]+i:04d}.jpg"
                    out_path = out_dir / fname
                    cv2.imwrite(str(out_path), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
                    manifest[split].append({
                        "path": str(out_path),
                        "label": 0,
                        "patient_id": "talking_normal",
                        "severity_folder": "talking_normal",
                    })

                total_added[split] += alloc
                crop_idx += alloc
                logger.info("%s %s: +%d (total %d/%d)", video_id, split, alloc,
                            total_added[split], TARGETS[split])
        finally:
            tmp_video.unlink(missing_ok=True)

    with open(splits_json, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Done. Added talking-face negatives: %s", total_added)
    for split in ("train", "val", "test"):
        pos = sum(1 for e in manifest[split] if e["label"] == 1)
        neg = sum(1 for e in manifest[split] if e["label"] == 0)
        logger.info("%s — positive: %d, negative: %d", split, pos, neg)
    logger.info("Next: python train.py --pos-weight 1.5")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--processed-dir", default="data/processed")
    p.add_argument("--splits-json", default="data/splits.json")
    p.add_argument("--image-size", type=int, default=224)
    main(p.parse_args())
