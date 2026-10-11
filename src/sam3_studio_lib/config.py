"""Configuration objects for the SAM3 annotation library."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Device = int | Literal["cpu", "mps"]


@dataclass(frozen=True, slots=True)
class ClassConfig:
    """Dataset class and one or more natural-language SAM3 prompts."""

    name: str
    prompts: tuple[str, ...]

    def __post_init__(self) -> None:
        name = self.name.strip()
        prompts = tuple(prompt.strip() for prompt in self.prompts if prompt.strip())
        if not name:
            raise ValueError("Class name cannot be empty.")
        if not prompts:
            raise ValueError(f"Class '{name}' must have at least one prompt.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "prompts", prompts)

    @classmethod
    def from_values(cls, name: str, prompts: list[str] | tuple[str, ...]) -> "ClassConfig":
        return cls(name=name, prompts=tuple(prompts))


@dataclass(frozen=True, slots=True)
class AnnotationConfig:
    """Inference, filtering and export settings.

    ``device`` accepts a CUDA device index, ``"mps"`` or ``"cpu"``.
    """

    classes: tuple[ClassConfig, ...]
    weights_path: Path
    device: Device = "cpu"
    half: bool = False
    confidence: float = 0.15
    inference_max_side: int = 1008
    inference_jpeg_quality: int = 80
    min_box_area_px: float = 100.0
    nms_iou_threshold: float = 0.35
    nms_ios_threshold: float = 0.5
    one_detection_per_class: bool = False
    skip_images_without_objects: bool = False
    auto_download_weights: bool = True
    hf_repo_id: str = "1038lab/sam3"
    hf_filename: str = "sam3.pt"
    hf_token: str | None = None
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1
    seed: int = 42

    def __post_init__(self) -> None:
        if not self.classes:
            raise ValueError("At least one dataset class is required.")
        if len({item.name for item in self.classes}) != len(self.classes):
            raise ValueError("Dataset class names must be unique.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")
        if self.inference_max_side < 0 or not 1 <= self.inference_jpeg_quality <= 100:
            raise ValueError("Invalid inference image settings.")
        if self.min_box_area_px < 0:
            raise ValueError("min_box_area_px cannot be negative.")
        if self.train_split + self.val_split + self.test_split > 1.0 + 1e-6:
            raise ValueError("train_split + val_split + test_split must not exceed 1.")

    @classmethod
    def for_classes(
        cls,
        classes: list[ClassConfig] | tuple[ClassConfig, ...],
        weights_path: str | Path,
        **kwargs: object,
    ) -> "AnnotationConfig":
        return cls(classes=tuple(classes), weights_path=Path(weights_path), **kwargs)
