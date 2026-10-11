"""Reusable SAM3 annotation tools for MacLearn.

The package deliberately contains no Qt or Gradio code.  MacLearn can use the
typed service API from any worker thread and keep ownership of its own UI.
"""

from .annotator import Sam3Annotator
from .config import AnnotationConfig, ClassConfig, Device
from .geometry import Detection, apply_detection_limit, iou_xyxy, nms
from .pipeline import AnnotationResult, annotate_images, annotate_video
from .yolo import ImageAnnotations, export_yolo, xyxy_to_yolo, zip_dataset

__all__ = [
    "AnnotationConfig",
    "AnnotationResult",
    "ClassConfig",
    "Detection",
    "Device",
    "ImageAnnotations",
    "Sam3Annotator",
    "annotate_images",
    "annotate_video",
    "apply_detection_limit",
    "export_yolo",
    "iou_xyxy",
    "nms",
    "xyxy_to_yolo",
    "zip_dataset",
]
