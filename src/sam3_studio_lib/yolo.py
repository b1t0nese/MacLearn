"""YOLO dataset export independent of MacLearn's database."""

from __future__ import annotations

import random
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .config import ClassConfig
from .geometry import Detection


@dataclass(frozen=True, slots=True)
class ImageAnnotations:
    image_path: Path
    detections: tuple[Detection, ...]
    width: int
    height: int


def xyxy_to_yolo(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (max(0.0, min(value, limit)) for value, limit in zip(box, (width, height, width, height)))
    return ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height, (x2 - x1) / width, (y2 - y1) / height)


def export_yolo(
    items: list[ImageAnnotations],
    classes: tuple[ClassConfig, ...],
    output_dir: str | Path,
    train_split: float = 0.8,
    val_split: float = 0.1,
    test_split: float = 0.1,
    seed: int = 42,
) -> Path:
    """Write ``train/val/test`` images, labels and ``data.yaml``."""

    if train_split + val_split + test_split > 1.0 + 1e-6:
        raise ValueError("Dataset split values must not exceed 1.")
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    rng = random.Random(seed)
    indices = list(range(len(items)))
    rng.shuffle(indices)
    counts = [round(len(items) * value) for value in (train_split, val_split, test_split)]
    splits: dict[str, list[int]] = {}
    cursor = 0
    for name, count in zip(("train", "val", "test"), counts):
        splits[name] = indices[cursor:cursor + min(count, len(indices) - cursor)]
        cursor += len(splits[name])
        (output / name / "images").mkdir(parents=True, exist_ok=True)
        (output / name / "labels").mkdir(parents=True, exist_ok=True)
    for split, split_indices in splits.items():
        for index in split_indices:
            item = items[index]
            shutil.copy2(item.image_path, output / split / "images" / item.image_path.name)
            lines = []
            for detection in item.detections:
                xc, yc, width, height = xyxy_to_yolo(detection.box_xyxy, item.width, item.height)
                if width > 0 and height > 0:
                    lines.append(f"{detection.class_id} {xc:.6f} {yc:.6f} {width:.6f} {height:.6f}")
            (output / split / "labels" / f"{item.image_path.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    yaml_lines = [
        f"path: {output.resolve()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        f"nc: {len(classes)}",
        "names:",
        *(f"  {index}: {item.name}" for index, item in enumerate(classes)),
    ]
    (output / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    return output


def zip_dataset(dataset_dir: str | Path, zip_path: str | Path) -> Path:
    destination = Path(zip_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in Path(dataset_dir).rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(Path(dataset_dir).parent))
    return destination
