"""
VanaDrishti - Test Suite for NTLNP Night Camera-Trap Benchmark Subsystem
Tests:
- Pascal VOC XML parsing
- IoU computation
- Positive match at IoU >= 0.50
- Miss at IoU < 0.50
- Multiple ground-truth objects
- Multiple predictions per ground-truth object
- Missing or malformed XML handling
"""

import unittest
import tempfile
from pathlib import Path
from scripts.benchmark_ntlnp import (
    calculate_iou,
    parse_pascal_voc,
    match_gt_and_predictions
)


class TestNTLNPBenchmark(unittest.TestCase):
    def test_iou_calculation(self):
        """Test intersection-over-union calculation for various box configurations."""
        # Exact match
        box_a = [0.0, 0.0, 100.0, 100.0]
        box_b = [0.0, 0.0, 100.0, 100.0]
        self.assertAlmostEqual(calculate_iou(box_a, box_b), 1.0)

        # Disjoint boxes
        box_c = [200.0, 200.0, 300.0, 300.0]
        self.assertAlmostEqual(calculate_iou(box_a, box_c), 0.0)

        # Partial overlap: [0, 0, 10, 10] and [5, 0, 15, 10]
        # Inter = 5 * 10 = 50; Union = 100 + 100 - 50 = 150 -> IoU = 50 / 150 = 1/3
        box_d = [0.0, 0.0, 10.0, 10.0]
        box_e = [5.0, 0.0, 15.0, 10.0]
        self.assertAlmostEqual(calculate_iou(box_d, box_e), 1.0 / 3.0, places=4)

    def test_pascal_voc_xml_parsing_valid(self):
        """Verify parsing of valid Pascal VOC XML with dimensions and objects."""
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<annotation>
    <folder>JPEGImages</folder>
    <filename>test_tiger.jpg</filename>
    <size>
        <width>1280</width>
        <height>720</height>
        <depth>3</depth>
    </size>
    <object>
        <name>AmurTiger</name>
        <pose>Unspecified</pose>
        <truncated>0</truncated>
        <difficult>0</difficult>
        <bndbox>
            <xmin>150</xmin>
            <ymin>200</ymin>
            <xmax>600</xmax>
            <ymax>650</ymax>
        </bndbox>
    </object>
</annotation>
"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
            tmp.write(xml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_pascal_voc(tmp_path)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["width"], 1280)
            self.assertEqual(parsed["height"], 720)
            self.assertEqual(len(parsed["objects"]), 1)
            self.assertEqual(parsed["objects"][0]["species"], "AmurTiger")
            self.assertEqual(parsed["objects"][0]["bbox"], [150.0, 200.0, 600.0, 650.0])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_missing_and_corrupt_annotation_handling(self):
        """Verify graceful handling of non-existent or malformed XML files."""
        # Non-existent file
        res_missing = parse_pascal_voc(Path("non_existent_annotation_file.xml"))
        self.assertIsNone(res_missing)

        # Corrupt / malformed XML
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
            tmp.write("<annotation><broken>unclosed tag")
            tmp_path = Path(tmp.name)

        try:
            res_corrupt = parse_pascal_voc(tmp_path)
            self.assertIsNone(res_corrupt)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_correct_match_at_iou_ge_050(self):
        """
        Verify that a predicted animal box with IoU >= 0.50 successfully detects ground truth.
        """
        # GT box: [100, 100, 300, 300] in 1000x1000 image
        gt_objects = [{"species": "Leopard", "bbox": [100.0, 100.0, 300.0, 300.0]}]

        # Normalized pred: [0.10, 0.10, 0.28, 0.28] -> [100, 100, 280, 280] in pixels
        # Inter = 180 * 180 = 32400; Area A = 40000; Area B = 32400; Union = 40000; IoU = 32400 / 40000 = 0.81 >= 0.50
        predictions = [{
            "class": "animal",
            "confidence": 0.89,
            "bbox": [0.10, 0.10, 0.28, 0.28]
        }]

        result = match_gt_and_predictions(
            gt_objects=gt_objects,
            predictions=predictions,
            img_width=1000,
            img_height=1000,
            iou_threshold=0.50
        )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["missed_count"], 0)
        self.assertEqual(len(result["unmatched_predictions"]), 0)
        self.assertTrue(result["detected"])
        self.assertGreaterEqual(result["best_image_iou"], 0.50)

    def test_miss_at_iou_lt_050(self):
        """
        Verify that a prediction with IoU < 0.50 is NOT matched and results in a missed animal.
        """
        gt_objects = [{"species": "AmurTiger", "bbox": [100.0, 100.0, 200.0, 200.0]}]

        # Normalized pred: [0.15, 0.15, 0.30, 0.30] -> [150, 150, 300, 300]
        # Inter = 50 * 50 = 2500; Union = 10000 + 22500 - 2500 = 30000 -> IoU = 2500 / 30000 = 0.083 < 0.50
        predictions = [{
            "class": "animal",
            "confidence": 0.85,
            "bbox": [0.15, 0.15, 0.30, 0.30]
        }]

        result = match_gt_and_predictions(
            gt_objects=gt_objects,
            predictions=predictions,
            img_width=1000,
            img_height=1000,
            iou_threshold=0.50
        )

        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["missed_count"], 1)
        self.assertEqual(len(result["unmatched_predictions"]), 1)
        self.assertFalse(result["detected"])
        self.assertLess(result["best_image_iou"], 0.50)

    def test_multiple_ground_truth_objects(self):
        """
        Verify handling of multiple ground-truth animals in a single frame.
        """
        gt_objects = [
            {"species": "Wildboar", "bbox": [100.0, 100.0, 200.0, 200.0]},
            {"species": "Wildboar", "bbox": [500.0, 500.0, 600.0, 600.0]}
        ]

        # Only one prediction matching the first GT
        predictions = [{
            "class": "animal",
            "confidence": 0.92,
            "bbox": [0.10, 0.10, 0.20, 0.20]  # Pixel: [100, 100, 200, 200]
        }]

        result = match_gt_and_predictions(
            gt_objects=gt_objects,
            predictions=predictions,
            img_width=1000,
            img_height=1000,
            iou_threshold=0.50
        )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["missed_count"], 1)
        self.assertTrue(result["detected"])

    def test_multiple_predictions_for_single_ground_truth(self):
        """
        Verify that multiple overlapping predictions only match a GT animal once,
        and excess predictions are categorized as unmatched.
        """
        gt_objects = [{"species": "Hare", "bbox": [100.0, 100.0, 200.0, 200.0]}]

        # Two overlapping predictions for the same animal
        predictions = [
            {"class": "animal", "confidence": 0.95, "bbox": [0.10, 0.10, 0.20, 0.20]},
            {"class": "animal", "confidence": 0.70, "bbox": [0.09, 0.09, 0.21, 0.21]}
        ]

        result = match_gt_and_predictions(
            gt_objects=gt_objects,
            predictions=predictions,
            img_width=1000,
            img_height=1000,
            iou_threshold=0.50
        )

        # 1 GT matched by higher confidence prediction, 1 unmatched prediction
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["missed_count"], 0)
        self.assertEqual(len(result["unmatched_predictions"]), 1)
        self.assertTrue(result["detected"])


if __name__ == "__main__":
    unittest.main()
