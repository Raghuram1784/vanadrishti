"""
VanaDrishti - Test Suite for Phase 1 Wildlife Detection Subsystem
Verifies:
- Detector loading and singleton behavior
- Automatic CUDA/CPU device selection
- Empty frame / false alert immunity
- Coordinate normalization and denormalization
- Class-specific confidence thresholds:
    animal: 0.20
    person: 0.25
    vehicle: 0.50
- Filtering of low-confidence vehicle detections (e.g. false alarms on spectacles/fans)
- Retention of valid high-confidence vehicles, persons, and animals
- CLI / global minimum threshold override: max(global, class_specific)
"""

import os
import unittest
from unittest.mock import MagicMock
import numpy as np
import cv2

from ml.detector import (
    WildlifeDetector,
    get_detector,
    detect_frame,
    denormalize_bbox,
    draw_detections,
    CLASS_THRESHOLDS,
    CLASS_MAPPING
)
from ml.detector.detector import get_optimal_device


class TestWildlifeDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize detector singleton once for tests
        cls.detector = get_detector(conf_threshold=0.20)

    def test_singleton_behavior(self):
        """Verify detector is loaded only once and returns the exact same instance."""
        d1 = get_detector()
        d2 = get_detector()
        self.assertIs(d1, d2)
        self.assertIs(d1, self.detector)

    def test_optimal_device_selection(self):
        """Verify optimal device selection uses cuda if available, otherwise cpu."""
        device = get_optimal_device()
        self.assertIn(device, ["cuda", "cpu"])

    def test_empty_frame_no_false_alerts(self):
        """
        Test B: Empty room / empty forest footage.
        Expected: 0 detections, no false alerts.
        """
        blank_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        detections = self.detector.detect(blank_frame)
        self.assertIsInstance(detections, list)
        self.assertEqual(len(detections), 0)

    def test_input_validation(self):
        """Verify that invalid inputs raise appropriate ValueErrors."""
        with self.assertRaises(ValueError):
            self.detector.detect(None)  # type: ignore

        with self.assertRaises(ValueError):
            self.detector.detect(np.zeros((100, 100), dtype=np.uint8))  # 2D instead of 3D

    def test_denormalize_bbox(self):
        """Verify coordinate conversion from normalized [0, 1] to pixel integers."""
        norm_bbox = [0.1, 0.2, 0.5, 0.8]
        x1, y1, x2, y2 = denormalize_bbox(norm_bbox, width=1000, height=500)
        self.assertEqual((x1, y1, x2, y2), (100, 100, 500, 400))

    def test_class_thresholds_values(self):
        """Verify configured class-specific thresholds match requirements."""
        self.assertEqual(CLASS_THRESHOLDS.get("animal"), 0.20)
        self.assertEqual(CLASS_THRESHOLDS.get("person"), 0.25)
        self.assertEqual(CLASS_THRESHOLDS.get("vehicle"), 0.50)

    def test_low_confidence_vehicle_filtered_on_real_image(self):
        """
        Real image test: zidane.jpg produces a low-confidence vehicle candidate (~0.23).
        With vehicle threshold set to 0.50, the false vehicle detection must be discarded.
        """
        import ultralytics
        zidane_path = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "zidane.jpg")
        self.assertTrue(os.path.exists(zidane_path), f"Asset {zidane_path} not found")

        frame = cv2.imread(zidane_path)
        self.assertIsNotNone(frame)

        detections = self.detector.detect(frame, conf_threshold=0.20)
        classes = [d["class"] for d in detections]

        # Persons must still be detected
        self.assertIn("person", classes)
        # Low-confidence false vehicle (< 0.50) must NOT be present
        self.assertNotIn("vehicle", classes)

    def test_class_specific_filtering_and_retention(self):
        """
        Controlled test with synthetic candidate detections:
        - animal 0.22 -> KEPT (>= 0.20)
        - animal 0.15 -> DISCARDED (< 0.20)
        - person 0.30 -> KEPT (>= 0.25)
        - person 0.22 -> DISCARDED (< 0.25)
        - vehicle 0.65 -> KEPT (>= 0.50)
        - vehicle 0.35 -> DISCARDED (< 0.50)
        """
        mock_dets = MagicMock()
        mock_dets.__len__.return_value = 6
        mock_dets.xyxy = np.array([
            [10, 10, 50, 50],
            [20, 20, 60, 60],
            [30, 30, 70, 70],
            [40, 40, 80, 80],
            [50, 50, 90, 90],
            [60, 60, 100, 100]
        ], dtype=np.float32)
        mock_dets.confidence = np.array([0.22, 0.15, 0.30, 0.22, 0.65, 0.35], dtype=np.float32)
        # Class IDs: 0 = animal, 1 = person, 2 = vehicle
        mock_dets.class_id = np.array([0, 0, 1, 1, 2, 2], dtype=np.int64)
        mock_result = {"detections": mock_dets}

        orig_fn = self.detector._model.single_image_detection
        try:
            self.detector._model.single_image_detection = MagicMock(return_value=mock_result)
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

            # Global threshold at 0.20
            results = self.detector.detect(dummy_frame, conf_threshold=0.20)

            # Exactly 3 detections should remain: animal (0.22), person (0.30), vehicle (0.65)
            self.assertEqual(len(results), 3)

            classes = [r["class"] for r in results]
            confs = [r["confidence"] for r in results]

            self.assertEqual(classes, ["animal", "person", "vehicle"])
            self.assertAlmostEqual(confs[0], 0.22, places=2)
            self.assertAlmostEqual(confs[1], 0.30, places=2)
            self.assertAlmostEqual(confs[2], 0.65, places=2)
        finally:
            self.detector._model.single_image_detection = orig_fn

    def test_global_minimum_threshold_override(self):
        """
        Verify that CLI --conf-threshold acts as a global minimum:
        effective_threshold = max(global_threshold, class_specific_threshold)

        When global_threshold = 0.40:
        - animal effective: max(0.40, 0.20) = 0.40 (animal 0.22 is discarded)
        - person effective: max(0.40, 0.25) = 0.40 (person 0.30 is discarded)
        - vehicle effective: max(0.40, 0.50) = 0.50 (vehicle 0.65 is kept)
        """
        mock_dets = MagicMock()
        mock_dets.__len__.return_value = 3
        mock_dets.xyxy = np.array([
            [10, 10, 50, 50],
            [30, 30, 70, 70],
            [50, 50, 90, 90]
        ], dtype=np.float32)
        mock_dets.confidence = np.array([0.22, 0.30, 0.65], dtype=np.float32)
        mock_dets.class_id = np.array([0, 1, 2], dtype=np.int64)
        mock_result = {"detections": mock_dets}

        orig_fn = self.detector._model.single_image_detection
        try:
            self.detector._model.single_image_detection = MagicMock(return_value=mock_result)
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

            results = self.detector.detect(dummy_frame, conf_threshold=0.40)

            # Only vehicle (0.65 >= 0.50) should remain; animal 0.22 and person 0.30 are below 0.40
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["class"], "vehicle")
            self.assertAlmostEqual(results[0]["confidence"], 0.65, places=2)
        finally:
            self.detector._model.single_image_detection = orig_fn

    def test_valid_high_confidence_vehicle_remains(self):
        """
        Verify that a valid vehicle detection with confidence >= 0.50 is retained.
        """
        mock_dets = MagicMock()
        mock_dets.__len__.return_value = 2
        mock_dets.xyxy = np.array([
            [10, 10, 100, 100],
            [20, 20, 120, 120]
        ], dtype=np.float32)
        mock_dets.confidence = np.array([0.78, 0.42], dtype=np.float32)
        mock_dets.class_id = np.array([2, 2], dtype=np.int64)
        mock_result = {"detections": mock_dets}

        orig_fn = self.detector._model.single_image_detection
        try:
            self.detector._model.single_image_detection = MagicMock(return_value=mock_result)
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

            results = self.detector.detect(dummy_frame, conf_threshold=0.20)

            # Only the 0.78 vehicle is retained; 0.42 is discarded (< 0.50)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["class"], "vehicle")
            self.assertAlmostEqual(results[0]["confidence"], 0.78, places=2)
        finally:
            self.detector._model.single_image_detection = orig_fn

    def test_animal_detection_works(self):
        """
        Verify that an animal detection with confidence >= 0.20 is retained.
        """
        mock_dets = MagicMock()
        mock_dets.__len__.return_value = 2
        mock_dets.xyxy = np.array([
            [15, 15, 80, 80],
            [25, 25, 90, 90]
        ], dtype=np.float32)
        mock_dets.confidence = np.array([0.85, 0.18], dtype=np.float32)
        mock_dets.class_id = np.array([0, 0], dtype=np.int64)
        mock_result = {"detections": mock_dets}

        orig_fn = self.detector._model.single_image_detection
        try:
            self.detector._model.single_image_detection = MagicMock(return_value=mock_result)
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

            results = self.detector.detect(dummy_frame, conf_threshold=0.20)

            # Only the 0.85 animal is retained; 0.18 is discarded (< 0.20)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["class"], "animal")
            self.assertAlmostEqual(results[0]["confidence"], 0.85, places=2)
        finally:
            self.detector._model.single_image_detection = orig_fn

    def test_person_detection_still_works(self):
        """
        Real image test: verify person detection works on real images containing humans.
        """
        import ultralytics
        bus_path = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
        self.assertTrue(os.path.exists(bus_path), f"Asset {bus_path} not found")

        frame = cv2.imread(bus_path)
        self.assertIsNotNone(frame)

        detections = self.detector.detect(frame, conf_threshold=0.25)
        self.assertGreater(len(detections), 0)

        classes = [d["class"] for d in detections]
        self.assertIn("person", classes)

        # Verify normalized bounding box bounds
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            self.assertLessEqual(x1, x2)
            self.assertLessEqual(y1, y2)
            self.assertGreaterEqual(d["confidence"], 0.25)

    def test_visualization_drawing(self):
        """Verify visualization overlay draws without modifying shape."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_dets = [
            {"class": "animal", "confidence": 0.88, "bbox": [0.1, 0.1, 0.4, 0.4]},
            {"class": "person", "confidence": 0.93, "bbox": [0.5, 0.2, 0.8, 0.9]}
        ]
        annotated = draw_detections(frame, mock_dets, fps=28.5)
        self.assertEqual(annotated.shape, frame.shape)


if __name__ == "__main__":
    unittest.main()
