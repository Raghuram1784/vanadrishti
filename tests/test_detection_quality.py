"""Focused tests for C-18 duplicate detection suppression and person/animal conflict handling."""
import unittest
import numpy as np
from unittest.mock import MagicMock

from ml.detector.detector import (
    WildlifeDetector,
    box_iou,
    box_ios,
    suppress_duplicates
)
from backend.services.vision_service import VisionService


class TestDetectionQuality(unittest.TestCase):
    def test_box_iou_and_ios_metrics(self):
        # Case 1: Identical boxes
        b1 = [0.1, 0.1, 0.5, 0.5]
        self.assertAlmostEqual(box_iou(b1, b1), 1.0)
        self.assertAlmostEqual(box_ios(b1, b1), 1.0)

        # Case 2: Disjoint boxes
        b2 = [0.6, 0.6, 0.9, 0.9]
        self.assertEqual(box_iou(b1, b2), 0.0)
        self.assertEqual(box_ios(b1, b2), 0.0)

        # Case 3: Box A fully contained inside Box B
        inner = [0.2, 0.2, 0.4, 0.4]  # area = 0.04
        outer = [0.1, 0.1, 0.5, 0.5]  # area = 0.16
        # IoS should be 1.0 (100% of inner is contained)
        self.assertAlmostEqual(box_ios(inner, outer), 1.0)
        # IoU should be 0.04 / 0.16 = 0.25
        self.assertAlmostEqual(box_iou(inner, outer), 0.25)

    def test_duplicate_person_suppression_iou_and_containment(self):
        """Simulate real C-18 duplicate person detections (upper body vs full body)."""
        dets = [
            {"class": "person", "confidence": 0.6088, "bbox": [0.4036, 0.2889, 0.6532, 0.902]},
            {"class": "person", "confidence": 0.3207, "bbox": [0.4186, 0.3366, 0.8899, 1.0]},
        ]
        result = suppress_duplicates(dets, iou_threshold=0.45, ios_threshold=0.80)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 0.6088)

    def test_two_nearby_people_remain_separate(self):
        """Two people standing side-by-side or walking together must NOT be suppressed."""
        dets = [
            {"class": "person", "confidence": 0.85, "bbox": [0.10, 0.20, 0.35, 0.80]},
            {"class": "person", "confidence": 0.82, "bbox": [0.30, 0.22, 0.55, 0.82]},
        ]
        # Overlap is small (x from 0.30 to 0.35 = 0.05 width)
        result = suppress_duplicates(dets, iou_threshold=0.45, ios_threshold=0.80)
        self.assertEqual(len(result), 2)
        confs = {d["confidence"] for d in result}
        self.assertEqual(confs, {0.85, 0.82})

    def test_different_classes_not_suppressed_by_class_aware_nms(self):
        """An animal and a person in the frame are not suppressed by class-aware NMS."""
        dets = [
            {"class": "person", "confidence": 0.75, "bbox": [0.10, 0.10, 0.50, 0.90]},
            {"class": "animal", "confidence": 0.70, "bbox": [0.12, 0.15, 0.48, 0.88]},
        ]
        result = suppress_duplicates(dets, iou_threshold=0.45, ios_threshold=0.80)
        self.assertEqual(len(result), 2)

    def test_person_animal_conflict_flags_uncertainty_via_containment(self):
        """When a human candidate is contained inside an animal box, flag uncertainty."""
        service = VisionService(species_min_detector_score=0.35)
        mock_detector = MagicMock()
        mock_species = MagicMock()

        # Detector returns an animal box that encloses a candidate person box
        def detect(frame, conf_threshold=0.20, candidate_sink=None):
            if candidate_sink is not None:
                candidate_sink.append({"class": "person", "confidence": 0.28, "bbox": [0.35, 0.30, 0.55, 0.85]})
            return [{"class": "animal", "confidence": 0.52, "bbox": [0.30, 0.25, 0.65, 0.95]}]

        mock_detector.detect.side_effect = detect
        service._detector = mock_detector
        service._species = mock_species

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = service.analyze(dummy_frame)

        self.assertEqual(len(results), 1)
        # Must be marked uncertain due to competing person signal
        self.assertTrue(results[0].get("uncertain"))
        self.assertIn("Competing animal and person signals", results[0].get("uncertainty_reason", ""))
        # BioCLIP must NOT be called on this ambiguous crop
        mock_species.classify_animal_detection.assert_not_called()

    def test_valid_animal_without_conflict_routes_to_bioclip(self):
        """A valid animal detection with no conflicting human candidate routes to BioCLIP."""
        service = VisionService(species_min_detector_score=0.35)
        mock_detector = MagicMock()
        mock_species = MagicMock()

        mock_detector.detect.return_value = [{"class": "animal", "confidence": 0.65, "bbox": [0.2, 0.2, 0.7, 0.7]}]
        mock_species.classify_animal_detection.return_value = {
            "species": "tiger",
            "confidence": 0.91,
            "top_k": [{"species": "tiger", "confidence": 0.91}, {"species": "leopard", "confidence": 0.05}]
        }

        service._detector = mock_detector
        service._species = mock_species

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = service.analyze(dummy_frame)

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].get("uncertain", False))
        self.assertIsNotNone(results[0]["species"])
        self.assertEqual(results[0]["species"]["top1"], "tiger")
        mock_species.classify_animal_detection.assert_called_once()


if __name__ == "__main__":
    unittest.main()
