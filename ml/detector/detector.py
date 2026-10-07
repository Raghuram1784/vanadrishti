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
DEFAULT_CONF_THRESHOLD = 0.25

# Class ID to Label mapping from MegaDetector V6
# 0: animal, 1: person, 2: vehicle
CLASS_MAPPING = {
    0: "animal",
    1: "person",
    2: "vehicle"
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
        conf_threshold: Optional[float] = None
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

        threshold = conf_threshold if conf_threshold is not None else self.default_conf_threshold

        # MegaDetector expects RGB image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Run inference through PyTorch-Wildlife
        raw_results = self._model.single_image_detection(
            rgb_frame,
            det_conf_thres=threshold
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

            # Map class ID to human-readable string
            class_name = CLASS_MAPPING.get(cid, "animal")

            # Calculate and clamp normalized coordinates [0.0, 1.0]
            x1_norm = max(0.0, min(1.0, float(x1_px / width)))
            y1_norm = max(0.0, min(1.0, float(y1_px / height)))
            x2_norm = max(0.0, min(1.0, float(x2_px / width)))
            y2_norm = max(0.0, min(1.0, float(y2_px / height)))

            detections.append({
                "class": class_name,
                "confidence": round(conf, 4),
                "bbox": [
                    round(x1_norm, 4),
                    round(y1_norm, 4),
                    round(x2_norm, 4),
                    round(y2_norm, 4)
                ]
            })

        return detections


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
        int(round(x1 * width)),
        int(round(y1 * height)),
        int(round(x2 * width)),
        int(round(y2 * height))
    )
