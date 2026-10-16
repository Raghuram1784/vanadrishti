"""
VanaDrishti - Wildlife Surveillance & Ranger Decision-Support System
Phase 1: Person / Vehicle / Animal Detection Core Module

This module implements the core WildlifeDetector using Microsoft MegaDetector V6
via the PyTorch-Wildlife framework. It provides a thread-safe singleton pattern
to ensure the model is loaded only once into memory across callers (webcam, video, or FastAPI).
"""

import os
import sys
import logging
import threading
import warnings
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import cv2
import torch

# Suppress minor external library dependency warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*pkg_resources.*")

logger = logging.getLogger("vanadrishti.detector")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [vanadrishti.detector]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Default model version: MDV6-yolov10-c (High performance, fast inference, CPU & edge friendly)
DEFAULT_MODEL_VERSION = "MDV6-yolov10-c"
# DEFAULT_MODEL_VERSION = "MDV6-yolov10-e"
DEFAULT_CONF_THRESHOLD = 0.20

# Class ID to Label mapping from MegaDetector V6
# 0: animal, 1: person, 2: vehicle
CLASS_MAPPING = {
    0: "animal",
    1: "person",
    2: "vehicle"
}

# Class-specific confidence thresholds
# Used to eliminate false low-confidence vehicle alerts (e.g. on spectacles/ceiling fans)
CLASS_THRESHOLDS = {
    "animal": 0.20,
    "person": 0.25,
    "vehicle": 0.50
}


def get_optimal_device(requested_device: Optional[str] = None) -> str:
    """
    Selects the optimal execution device.
    Uses CUDA if available, otherwise falls back to CPU.
    """
    if requested_device:
        device = requested_device.lower()
        if device.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available. Falling back to CPU.")
            return "cpu"
        return device

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info("CUDA detected: Using GPU (%s)", device_name)
        return "cuda"
    else:
        logger.info("CUDA not available: Using CPU")
        return "cpu"


class WildlifeDetector:
    """
    Thread-safe WildlifeDetector utilizing Microsoft MegaDetector V6.
    Ensures model weights are loaded only once into memory.
    """

    _instance: Optional["WildlifeDetector"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        model_version: str = DEFAULT_MODEL_VERSION,
        device: Optional[str] = None,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD
    ):
        """
        Initialize the detector. Recommended to use `WildlifeDetector.get_instance()`
        or `get_detector()` to maintain a single model instance.
        """
        self.model_version = model_version
        self.device = get_optimal_device(device)
        self.default_conf_threshold = conf_threshold

        logger.info("Initializing MegaDetector V6 (version: %s, device: %s)...", self.model_version, self.device)

        try:
            from PytorchWildlife.models import detection as pw_detection
            self._model = pw_detection.MegaDetectorV6(
                device=self.device,
                pretrained=True,
                version=self.model_version
            )
            logger.info("MegaDetector V6 loaded successfully on %s.", self.device)
        except Exception as exc:
            logger.error("Failed to load MegaDetector V6: %s", exc, exc_info=True)
            raise RuntimeError(f"Could not initialize MegaDetector V6: {exc}") from exc

    @classmethod
    def get_instance(
        cls,
        model_version: str = DEFAULT_MODEL_VERSION,
        device: Optional[str] = None,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD
    ) -> "WildlifeDetector":
        """
        Thread-safe singleton accessor. Instantiates the detector only once.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(
                    model_version=model_version,
                    device=device,
                    conf_threshold=conf_threshold
                )
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing/reloading)."""
        with cls._lock:
            cls._instance = None

    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None,
        *, candidate_sink: Optional[list] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform animal, person, and vehicle detection on a single OpenCV BGR frame.

        Args:
            frame: OpenCV image frame as a numpy ndarray (BGR format).
            conf_threshold: Confidence threshold (0.0 to 1.0). If None, uses default.

        Returns:
            List of normalized detection objects matching the schema:
            [
              {
                "class": "person",      # "animal" | "person" | "vehicle"
                "confidence": 0.92,
                "bbox": [x1, y1, x2, y2] # Normalized coordinates [0.0 - 1.0]
              }
            ]
        """
        if frame is None:
            raise ValueError("Input frame cannot be None.")

        if not isinstance(frame, np.ndarray) or frame.ndim != 3:
            raise ValueError(f"Invalid frame format. Expected 3D numpy ndarray, got {type(frame)}")

        height, width = frame.shape[:2]
        if height == 0 or width == 0:
            return []

        global_threshold = conf_threshold if conf_threshold is not None else self.default_conf_threshold

        # Installed PyTorch-Wildlife forwards NumPy arrays unchanged to Ultralytics.
        # Ultralytics expects BGR arrays and converts once to RGB model tensors.
        model_frame = frame

        # Query MegaDetector at minimum threshold to capture candidates across all target classes
        min_class_thresh = min(CLASS_THRESHOLDS.values())
        model_query_thresh = min(global_threshold, min_class_thresh)
        if candidate_sink is not None:
            model_query_thresh = min(model_query_thresh, 0.05)

        # Run inference through PyTorch-Wildlife
        raw_results = self._model.single_image_detection(
            model_frame,
            det_conf_thres=model_query_thresh
        )

        detections: List[Dict[str, Any]] = []
        pw_dets = raw_results.get("detections")

        if pw_dets is None or len(pw_dets) == 0:
            return detections

        # Extract xyxy boxes, confidence scores, and class IDs
        xyxy_boxes = pw_dets.xyxy
        confidences = pw_dets.confidence
        class_ids = pw_dets.class_id

        for idx in range(len(xyxy_boxes)):
            x1_px, y1_px, x2_px, y2_px = xyxy_boxes[idx]
            conf = float(confidences[idx])
            cid = int(class_ids[idx])

            # Map class ID to human-readable string first
            class_name = CLASS_MAPPING.get(cid, "animal")

            # Calculate effective threshold: max(global_threshold, class_specific_threshold)
            class_threshold = CLASS_THRESHOLDS.get(class_name, self.default_conf_threshold)
            effective_threshold = max(global_threshold, class_threshold)

            # Discard detection if confidence is below effective threshold for this class

            # Calculate and clamp normalized coordinates [0.0, 1.0]
            x1_norm = max(0.0, min(1.0, float(x1_px / width)))
            y1_norm = max(0.0, min(1.0, float(y1_px / height)))
            x2_norm = max(0.0, min(1.0, float(x2_px / width)))
            y2_norm = max(0.0, min(1.0, float(y2_px / height)))

            candidate = {
                "class": class_name,
                "confidence": round(conf, 4),
                "bbox": [
                    round(x1_norm, 4),
                    round(y1_norm, 4),
                    round(x2_norm, 4),
                    round(y2_norm, 4)
                ]
            }
            if candidate_sink is not None:
                candidate_sink.append({**candidate, "confidence": conf})
            if conf >= effective_threshold:
                detections.append(candidate)

        raw_count = len(detections)
        detections = suppress_duplicates(detections, iou_threshold=0.45, ios_threshold=0.80)
        logger.debug("Detections before duplicate suppression: %d, after: %d", raw_count, len(detections))

        return detections


def box_iou(a: List[float], b: List[float]) -> float:
    """Intersection over Union between two normalized bounding boxes [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def box_ios(a: List[float], b: List[float]) -> float:
    """Intersection over Smaller box (containment) between two normalized bounding boxes."""
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    min_area = min(area_a, area_b)
    return intersection / min_area if min_area > 0 else 0.0


def suppress_duplicates(
    detections: List[Dict[str, Any]],
    iou_threshold: float = 0.45,
    ios_threshold: float = 0.80,
) -> List[Dict[str, Any]]:
    """
    Class-aware Non-Maximum Suppression (NMS) with containment handling.
    Suppresses redundant detections of the same class when IoU >= iou_threshold
    or containment (IoS) >= ios_threshold.
    """
    if len(detections) <= 1:
        return detections

    by_class: Dict[str, List[Dict[str, Any]]] = {}
    for det in detections:
        by_class.setdefault(det["class"], []).append(det)

    kept: List[Dict[str, Any]] = []
    for cls_name, items in by_class.items():
        items.sort(key=lambda d: d["confidence"], reverse=True)
        cls_kept: List[Dict[str, Any]] = []
        for item in items:
            suppress = False
            for k in cls_kept:
                iou = box_iou(item["bbox"], k["bbox"])
                ios = box_ios(item["bbox"], k["bbox"])
                if iou >= iou_threshold or ios >= ios_threshold:
                    logger.debug(
                        "Suppressed duplicate %s box (conf %.4f) by higher conf box (conf %.4f): iou=%.3f, ios=%.3f",
                        cls_name, item["confidence"], k["confidence"], iou, ios
                    )
                    suppress = True
                    break
            if not suppress:
                cls_kept.append(item)
        kept.extend(cls_kept)

    return kept


def get_detector(
    model_version: str = DEFAULT_MODEL_VERSION,
    device: Optional[str] = None,
    conf_threshold: float = DEFAULT_CONF_THRESHOLD
) -> WildlifeDetector:
    """Convenience getter for the global WildlifeDetector singleton."""
    return WildlifeDetector.get_instance(
        model_version=model_version,
        device=device,
        conf_threshold=conf_threshold
    )


def detect_frame(
    frame: np.ndarray,
    conf_threshold: float = DEFAULT_CONF_THRESHOLD
) -> List[Dict[str, Any]]:
    """Convenience function to run detection on an OpenCV frame."""
    return get_detector().detect(frame, conf_threshold=conf_threshold)


def denormalize_bbox(
    bbox: List[float],
    width: int,
    height: int
) -> Tuple[int, int, int, int]:
    """
    Convert normalized [x1, y1, x2, y2] bounding box back to absolute integer pixel coordinates.
    """
    x1, y1, x2, y2 = bbox
    return (
        round(x1 * width),
        round(y1 * height),
        round(x2 * width),
        round(y2 * height)
    )
