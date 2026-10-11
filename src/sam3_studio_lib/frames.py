"""Image and video preparation helpers."""

from __future__ import annotations

import io
from pathlib import Path

import cv2
from PIL import Image


def compress_for_inference(image: Image.Image, max_side: int, jpeg_quality: int) -> tuple[Image.Image, float]:
    width, height = image.size
    scale = min(1.0, max_side / max(width, height)) if max_side else 1.0
    resized = image if scale == 1.0 else image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.BILINEAR,
    )
    buffer = io.BytesIO()
    resized.convert("RGB").save(buffer, format="JPEG", quality=jpeg_quality)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB"), scale


def extract_video_frames(
    video_path: str | Path,
    output_dir: str | Path,
    fps: float,
    jpeg_quality: int = 95,
    max_frames: int | None = None,
    resize: tuple[int, int] | None = None,
) -> list[Path]:
    """Extract approximately ``fps`` frames per second as JPEG files."""

    if fps <= 0:
        raise ValueError("fps must be greater than zero.")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    interval = max(1, round(source_fps / fps))
    paths: list[Path] = []
    frame_index = 0
    try:
        while max_frames is None or len(paths) < max_frames:
            success, frame = capture.read()
            if not success:
                break
            if frame_index % interval == 0:
                if resize:
                    frame = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)
                path = output / f"{Path(video_path).stem}_frame{len(paths):06d}.jpg"
                if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]):
                    raise OSError(f"Cannot write extracted frame: {path}")
                paths.append(path)
            frame_index += 1
    finally:
        capture.release()
    return paths
