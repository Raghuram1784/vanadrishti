"""
Unit tests for VanaDrishti Phase 2B: End-to-End Wildlife Detection and Species Recognition.

Tests:
- Predicted crop extraction & coordinate clipping
- Animal-only pipeline routing
- Target-group normalization
- Detector miss & low-IoU handling
- Matched detection classification & failure categorization
- Metric calculations (distinction between accuracy-on-detected vs true end-to-end success)

All tests use mocking to isolate logic and prevent model reload overhead.
"""

from dataclasses import dataclass
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from ml.species import normalize_to_target_group
from scripts.test_end_to_end_ntlnp import (
    calculate_iou,
    extract_predicted_crop,
)


@dataclass
class MockDetection:
    class_name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2) normalized


class TestEndToEndPipeline(unittest.TestCase):
    """Test suite for Phase 2B End-to-End Detection + Species Recognition."""

    def test_target_group_normalization(self) -> None:
        """Verify fine-grained and dataset species names normalize to standard target groups."""
        # Tiger group
        self.assertEqual(normalize_to_target_group("Bengal tiger"), "tiger")
        self.assertEqual(normalize_to_target_group("AmurTiger"), "tiger")
        self.assertEqual(normalize_to_target_group("Panthera tigris"), "tiger")

        # Leopard group
        self.assertEqual(normalize_to_target_group("Indian leopard"), "leopard")
        self.assertEqual(normalize_to_target_group("Leopard"), "leopard")
        self.assertEqual(normalize_to_target_group("Panthera pardus"), "leopard")

        # Wild Boar group
        self.assertEqual(normalize_to_target_group("wild boar"), "wild_boar")
        self.assertEqual(normalize_to_target_group("WildBoar"), "wild_boar")
        self.assertEqual(normalize_to_target_group("Sus scrofa"), "wild_boar")

        # Other Tadoba species groups
        self.assertEqual(normalize_to_target_group("sloth bear"), "sloth_bear")
        self.assertEqual(normalize_to_target_group("gaur"), "gaur")
        self.assertEqual(normalize_to_target_group("chital / spotted deer"), "chital")
        self.assertEqual(normalize_to_target_group("sambar deer"), "sambar")
        self.assertEqual(normalize_to_target_group("dhole / Indian wild dog"), "dhole")
        self.assertEqual(normalize_to_target_group("nilgai"), "nilgai")
        self.assertEqual(normalize_to_target_group("Indian peafowl"), "peafowl")

    def test_predicted_crop_extraction(self) -> None:
        """Verify crop extraction using MegaDetector predicted pixel coordinates."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 120

        # Normal valid crop
        crop = extract_predicted_crop(image, (10, 10, 50, 60))
        self.assertIsNotNone(crop)
        self.assertEqual(crop.shape, (50, 40, 3))

        # Coordinates extending beyond frame boundaries should be clipped
        crop_oob = extract_predicted_crop(image, (-10, -5, 120, 110))
        self.assertIsNotNone(crop_oob)
        self.assertEqual(crop_oob.shape, (100, 100, 3))

        # Too small crop (< 5 px in either dimension)
        crop_tiny = extract_predicted_crop(image, (10, 10, 13, 13))
        self.assertIsNone(crop_tiny)

        # Inverted / degenerate coordinates
        crop_invalid = extract_predicted_crop(image, (50, 50, 20, 20))
        self.assertIsNone(crop_invalid)

    def test_animal_only_routing_and_iou(self) -> None:
        """Verify detector filtering routes animal detections and ignores human/vehicle."""
        gt_box = (100.0, 100.0, 300.0, 300.0)

        # 3 candidate detections from MegaDetector
        det_person = MockDetection(class_name="person", confidence=0.9, bbox=(0.1, 0.1, 0.3, 0.3))
        det_vehicle = MockDetection(class_name="vehicle", confidence=0.8, bbox=(0.1, 0.1, 0.3, 0.3))
        det_animal = MockDetection(class_name="animal", confidence=0.85, bbox=(0.1, 0.1, 0.3, 0.3))

        raw_detections = [det_person, det_vehicle, det_animal]

        # Pipeline filters for animal detections only
        animals_only = [d for d in raw_detections if d.class_name == "animal"]
        self.assertEqual(len(animals_only), 1)
        self.assertEqual(animals_only[0].class_name, "animal")

        # Test IoU calculation
        # Normalized bbox (0.1, 0.1, 0.3, 0.3) on 1000x1000 image is (100, 100, 300, 300)
        pixel_box = (100.0, 100.0, 300.0, 300.0)
        iou = calculate_iou(gt_box, pixel_box)
        self.assertAlmostEqual(iou, 1.0, places=4)

    def test_detector_miss_handling(self) -> None:
        """Verify categorization when detector fails to reach IoU threshold."""
        gt_box = (100.0, 100.0, 300.0, 300.0)

        # Case A: Partial overlap with IoU < 0.50 (e.g. 0.25)
        poor_pred_box = (250.0, 250.0, 350.0, 350.0)
        iou_poor = calculate_iou(gt_box, poor_pred_box)
        self.assertGreater(iou_poor, 0.0)
        self.assertLess(iou_poor, 0.50)

        is_detected_poor = (iou_poor >= 0.50)
        self.assertFalse(is_detected_poor)
        failure_reason_poor = "detector_iou_below_threshold" if iou_poor > 0 else "detector_miss"
        self.assertEqual(failure_reason_poor, "detector_iou_below_threshold")

        # Case B: Zero overlap
        zero_pred_box = (500.0, 500.0, 600.0, 600.0)
        iou_zero = calculate_iou(gt_box, zero_pred_box)
        self.assertEqual(iou_zero, 0.0)
        failure_reason_zero = "detector_iou_below_threshold" if iou_zero > 0 else "detector_miss"
        self.assertEqual(failure_reason_zero, "detector_miss")

    def test_matched_detection_classification_scenarios(self) -> None:
        """Verify classification failure categorization when detection is matched (IoU >= 0.50)."""
        gt_group = "tiger"

        # Scenario 1: Top-1 Correct -> success
        pred_top1_tiger = {
            "species": "Bengal tiger",
            "confidence": 0.95,
            "top_k": [
                {"species": "Bengal tiger", "confidence": 0.95},
                {"species": "Indian leopard", "confidence": 0.03},
                {"species": "wild boar", "confidence": 0.01},
            ],
        }
        pred_group1 = normalize_to_target_group(pred_top1_tiger["species"])
        top1_correct1 = (pred_group1 == gt_group)
        top3_groups1 = [normalize_to_target_group(str(i["species"])) for i in pred_top1_tiger["top_k"][:3]]
        top3_correct1 = (gt_group in top3_groups1)
        self.assertTrue(top1_correct1)
        self.assertTrue(top3_correct1)
        reason1 = "success" if top1_correct1 else ("species_top1_wrong" if top3_correct1 else "species_top3_miss")
        self.assertEqual(reason1, "success")

        # Scenario 2: Top-1 Wrong, but in Top-3 -> species_top1_wrong
        pred_top2_tiger = {
            "species": "Indian leopard",
            "confidence": 0.60,
            "top_k": [
                {"species": "Indian leopard", "confidence": 0.60},
                {"species": "Bengal tiger", "confidence": 0.35},
                {"species": "wild boar", "confidence": 0.05},
            ],
        }
        pred_group2 = normalize_to_target_group(pred_top2_tiger["species"])
        top1_correct2 = (pred_group2 == gt_group)
        top3_groups2 = [normalize_to_target_group(str(i["species"])) for i in pred_top2_tiger["top_k"][:3]]
        top3_correct2 = (gt_group in top3_groups2)
        self.assertFalse(top1_correct2)
        self.assertTrue(top3_correct2)
        reason2 = "success" if top1_correct2 else ("species_top1_wrong" if top3_correct2 else "species_top3_miss")
        self.assertEqual(reason2, "species_top1_wrong")

        # Scenario 3: Not in Top-3 -> species_top3_miss
        pred_top3_miss = {
            "species": "sloth bear",
            "confidence": 0.70,
            "top_k": [
                {"species": "sloth bear", "confidence": 0.70},
                {"species": "gaur", "confidence": 0.20},
                {"species": "wild boar", "confidence": 0.08},
            ],
        }
        pred_group3 = normalize_to_target_group(pred_top3_miss["species"])
        top1_correct3 = (pred_group3 == gt_group)
        top3_groups3 = [normalize_to_target_group(str(i["species"])) for i in pred_top3_miss["top_k"][:3]]
        top3_correct3 = (gt_group in top3_groups3)
        self.assertFalse(top1_correct3)
        self.assertFalse(top3_correct3)
        reason3 = "success" if top1_correct3 else ("species_top1_wrong" if top3_correct3 else "species_top3_miss")
        self.assertEqual(reason3, "species_top3_miss")

    def test_end_to_end_metric_calculation(self) -> None:
        """
        Verify distinct calculation of:
        - Detector recall
        - Classification accuracy among detected animals
        - True End-to-End success rate
        """
        # Example from prompt:
        # 20 GT animals, 19 detected, 18 of detected classified correctly
        total_gt = 20
        detected = 19
        classified = 19
        top1_correct = 18

        detector_recall = detected / total_gt
        top1_acc_on_detected = top1_correct / classified
        e2e_top1_success_rate = top1_correct / total_gt

        self.assertAlmostEqual(detector_recall, 0.95, places=4)
        self.assertAlmostEqual(top1_acc_on_detected, 18 / 19, places=4)
        self.assertAlmostEqual(e2e_top1_success_rate, 0.90, places=4)
        self.assertNotEqual(top1_acc_on_detected, e2e_top1_success_rate)


if __name__ == "__main__":
    unittest.main()
