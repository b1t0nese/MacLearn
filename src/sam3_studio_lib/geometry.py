"""Bounding-box types and duplicate suppression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

Box = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Detection:
    """One detected object in absolute ``(x1, y1, x2, y2)`` pixels."""

    class_id: int
    box_xyxy: Box
    score: float


def _area(box: Box) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _intersection(a: Box, b: Box) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou_xyxy(a: Box, b: Box) -> float:
    intersection = _intersection(a, b)
    union = _area(a) + _area(b) - intersection
    return intersection / union if union else 0.0


def nms(
    boxes: Sequence[Box],
    scores: Sequence[float],
    iou_threshold: float,
    ios_threshold: float = 0.5,
) -> list[int]:
    """Keep highest-scoring boxes, including nested duplicate suppression."""

    if len(boxes) != len(scores):
        raise ValueError("boxes and scores must have the same length.")
    order = sorted(range(len(boxes)), key=lambda index: scores[index], reverse=True)
    kept: list[int] = []
    while order:
        current = order.pop(0)
        kept.append(current)
        remaining: list[int] = []
        for index in order:
            intersection = _intersection(boxes[current], boxes[index])
            smaller = min(_area(boxes[current]), _area(boxes[index]))
            duplicate = iou_xyxy(boxes[current], boxes[index]) >= iou_threshold
            duplicate = duplicate or (smaller > 0 and intersection / smaller >= ios_threshold)
            if not duplicate:
                remaining.append(index)
        order = remaining
    return kept


def apply_detection_limit(detections: Sequence[Detection], one_per_class: bool) -> list[Detection]:
    if not one_per_class:
        return list(detections)
    best: dict[int, Detection] = {}
    for detection in detections:
        old = best.get(detection.class_id)
        if old is None or detection.score > old.score:
            best[detection.class_id] = detection
    return [best[class_id] for class_id in sorted(best)]
