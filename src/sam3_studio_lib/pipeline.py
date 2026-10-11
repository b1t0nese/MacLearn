"""High-level, UI-agnostic annotation functions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image

from .annotator import Sam3Annotator
from .config import AnnotationConfig
from .frames import extract_video_frames
from .geometry import Detection, apply_detection_limit
from .yolo import ImageAnnotations, export_yolo, zip_dataset

ProgressCallback = Callable[[int, int, Path], None]


@dataclass(frozen=True, slots=True)
class AnnotationResult:
    processed: int
    images_with_objects: int
    images_without_objects: int
    annotations: dict[Path, tuple[Detection, ...]]
    dataset_dir: Path | None = None
    zip_path: Path | None = None


def annotate_images(
    image_paths: Iterable[str | Path],
    config: AnnotationConfig,
    progress: ProgressCallback | None = None,
    dataset_dir: str | Path | None = None,
    zip_path: str | Path | None = None,
) -> AnnotationResult:
    """Annotate images and optionally export the result as a YOLO dataset."""

    annotator = Sam3Annotator(config)
    annotations: dict[Path, tuple[Detection, ...]] = {}
    items: list[ImageAnnotations] = []
    paths = [Path(path) for path in image_paths]
    without_objects = 0
    for index, path in enumerate(paths, start=1):
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            detections = tuple(apply_detection_limit(annotator.annotate(rgb), config.one_detection_per_class))
            width, height = rgb.size
        if not detections:
            without_objects += 1
        if detections or not config.skip_images_without_objects:
            annotations[path] = detections
            items.append(ImageAnnotations(path, detections, width, height))
        if progress:
            progress(index, len(paths), path)
    exported_dir = export_yolo(
        items, config.classes, dataset_dir, config.train_split, config.val_split, config.test_split, config.seed
    ) if dataset_dir is not None else None
    exported_zip = zip_dataset(exported_dir, zip_path) if exported_dir and zip_path else None
    return AnnotationResult(len(paths), len(paths) - without_objects, without_objects, annotations, exported_dir, exported_zip)


def annotate_video(
    video_path: str | Path,
    frames_dir: str | Path,
    config: AnnotationConfig,
    fps: float,
    resize: tuple[int, int] | None = None,
    max_frames: int | None = None,
    progress: ProgressCallback | None = None,
    dataset_dir: str | Path | None = None,
    zip_path: str | Path | None = None,
) -> AnnotationResult:
    """Extract a video and pass its frames through :func:`annotate_images`."""

    paths = extract_video_frames(video_path, frames_dir, fps, max_frames=max_frames, resize=resize)
    return annotate_images(
        paths,
        config,
        progress=progress,
        dataset_dir=dataset_dir,
        zip_path=zip_path,
    )
