"""Lazy SAM3 model wrapper."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from .config import AnnotationConfig, ClassConfig
from .frames import compress_for_inference
from .geometry import Box, Detection, nms
from .weights import ensure_weights


class Sam3Annotator:
    """Annotate PIL images with text prompts using Ultralytics SAM3."""

    def __init__(self, config: AnnotationConfig) -> None:
        if config.auto_download_weights:
            ensure_weights(
                config.weights_path,
                config.hf_repo_id,
                config.hf_filename,
                config.hf_token,
            )
        try:
            from ultralytics.models.sam import SAM3SemanticPredictor
        except ImportError as exc:
            raise RuntimeError(
                "SAM3 requires ultralytics and the Ultralytics CLIP fork. "
                "Install sam3_studio_lib/requirements.txt."
            ) from exc

        overrides = {
            "conf": config.confidence,
            "task": "segment",
            "mode": "predict",
            "model": str(config.weights_path),
            "device": config.device,
            "half": config.half,
            "save": False,
            "verbose": False,
        }
        self._predictor: Any = SAM3SemanticPredictor(overrides=overrides)
        self._config = config

    def _detect_prompt(self, prompt: str) -> list[tuple[Box, float]]:
        results = self._predictor(text=[prompt])
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return []
        result = results[0]
        boxes = result.boxes.xyxy.detach().cpu().numpy()
        scores = result.boxes.conf.detach().cpu().numpy()
        return [(tuple(float(value) for value in box), float(score)) for box, score in zip(boxes, scores)]

    def annotate(self, image: Image.Image) -> list[Detection]:
        compressed, scale = compress_for_inference(
            image, self._config.inference_max_side, self._config.inference_jpeg_quality
        )
        self._predictor.set_image(np.asarray(compressed))
        detections: list[Detection] = []
        for class_id, class_config in enumerate(self._config.classes):
            boxes: list[Box] = []
            scores: list[float] = []
            for prompt in class_config.prompts:
                for box, score in self._detect_prompt(prompt):
                    restored = tuple(value / scale for value in box)
                    if self._box_area(restored) >= self._config.min_box_area_px:
                        boxes.append(restored)
                        scores.append(score)
            for index in nms(
                boxes, scores, self._config.nms_iou_threshold, self._config.nms_ios_threshold
            ):
                detections.append(Detection(class_id, boxes[index], scores[index]))
        return detections

    @staticmethod
    def _box_area(box: Box) -> float:
        return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
