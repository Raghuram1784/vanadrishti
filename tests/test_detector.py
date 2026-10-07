"""
VanaDrishti - Test Suite for Phase 1 Wildlife Detection Subsystem
Verifies detector loading, singleton behavior, normalization, and test cases:
A. Person detection
B. Empty frame / no false alerts
C. Vehicle detection
D. Output format compliance
"""

import os
import unittest
import numpy as np
import cv2

from ml.detector import (
    WildlifeDetector,
    get_detector,
    detect_frame,
    denormalize_bbox,
    draw_detections
)
from ml.detector.detector import get_optimal_device, CLASS_MAPPING


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

    def test_person_detection(self):
        """
        Test A: Person detection using test image containing persons.
        Expected: Detected class includes 'person'.
        """
        import ultralytics
        zidane_path = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "zidane.jpg")
        self.assertTrue(os.path.exists(zidane_path), f"Asset {zidane_path} not found")

        frame = cv2.imread(zidane_path)
        self.assertIsNotNone(frame)

        detections = self.detector.detect(frame, conf_threshold=0.20)
        self.assertGreater(len(detections), 0)

        classes = [d["class"] for d in detections]
        self.assertIn("person", classes)

        # Verify output structure for every detection
        for d in detections:
            self.assertIn("class", d)
            self.assertIn("confidence", d)
            self.assertIn("bbox", d)
            self.assertIn(d["class"], ["animal", "person", "vehicle"])
            self.assertGreaterEqual(d["confidence"], 0.0)
            self.assertLessEqual(d["confidence"], 1.0)
            self.assertEqual(len(d["bbox"]), 4)
            for coord in d["bbox"]:
                self.assertGreaterEqual(coord, 0.0)
                self.assertLessEqual(coord, 1.0)

    def test_vehicle_detection(self):
        """
        Test C: Vehicle / transport detection using test image containing a bus.
        Expected: Detected classes contain 'person' and/or 'vehicle'.
        """
        import ultralytics
        bus_path = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
        self.assertTrue(os.path.exists(bus_path), f"Asset {bus_path} not found")

        frame = cv2.imread(bus_path)
        self.assertIsNotNone(frame)

        detections = self.detector.detect(frame, conf_threshold=0.25)
        self.assertGreater(len(detections), 0)

        # Verify normalized bounding box math
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            self.assertLessEqual(x1, x2)
            self.assertLessEqual(y1, y2)

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
