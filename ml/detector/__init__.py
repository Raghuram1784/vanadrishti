"""
VanaDrishti ML Wildlife Detector Package
Phase 1: Person / Vehicle / Animal Detection using Microsoft MegaDetector V6
"""

from ml.detector.detector import (
    WildlifeDetector,
    get_detector,
    detect_frame,
    denormalize_bbox,
    DEFAULT_MODEL_VERSION,
    DEFAULT_CONF_THRESHOLD,
    CLASS_MAPPING,
    CLASS_THRESHOLDS
)

from ml.detector.visualization import (
    draw_detections,
    draw_bounding_box,
    draw_hud,
    CLASS_COLORS
)

__all__ = [
    "WildlifeDetector",
    "get_detector",
    "detect_frame",
    "denormalize_bbox",
    "draw_detections",
    "draw_bounding_box",
    "draw_hud",
    "DEFAULT_MODEL_VERSION",
    "DEFAULT_CONF_THRESHOLD",
    "CLASS_MAPPING",
    "CLASS_THRESHOLDS",
    "CLASS_COLORS"
]
