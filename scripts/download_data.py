"""
Download the YFP dataset from Kaggle and print its directory structure.
Run this first to understand the dataset layout before running prepare_data.py.
"""
import os
from pathlib import Path


def print_tree(root: Path, max_depth: int = 3, max_files: int = 5, _depth: int = 0):
    if _depth > max_depth:
        return
    indent = "  " * _depth
    entries = sorted(root.iterdir())
    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]

    for d in dirs:
        print(f"{indent}📁 {d.name}/")
        print_tree(d, max_depth, max_files, _depth + 1)

    shown = files[:max_files]
    for f in shown:
        print(f"{indent}  {f.name}")
    if len(files) > max_files:
        print(f"{indent}  ... ({len(files) - max_files} more files)")


def main():
    import kagglehub

    print("Downloading YFP dataset from Kaggle...")
    path = kagglehub.dataset_download("dohaeid/yfp-dataset-updated")
    print(f"\nDataset downloaded to: {path}\n")

    root = Path(path)
    print("Directory structure:")
    print(f"📁 {root.name}/")
    print_tree(root, max_depth=3, max_files=5, _depth=1)

    # Count total images
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    images = [f for f in root.rglob("*") if f.suffix.lower() in exts]
    print(f"\nTotal images found: {len(images)}")

    # Look for annotation files
    annotations = [f for f in root.rglob("*") if f.suffix in {".csv", ".json", ".txt", ".xlsx"}]
    if annotations:
        print("\nAnnotation files found:")
        for f in annotations:
            print(f"  {f.relative_to(root)}")
    else:
        print("\nNo annotation files found — labels will be inferred from directory/filename structure.")

    print(f"\nNext step: python scripts/prepare_data.py --raw-dir {path}")


if __name__ == "__main__":
    main()
