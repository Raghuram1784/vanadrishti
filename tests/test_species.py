"""
Unit tests for VanaDrishti Phase 2 Species Recognition Module.

Tests cover:
- Species registry and prompt configuration
- Invalid, empty, small, and corrupted crop handling
- Output schema compliance and top-k ordering
- Animal-only pipeline routing (no classification on person/vehicle)
- Singleton lifecycle

Uses mocking for model inference to avoid re-downloading or heavy CPU runs during testing.
"""

from dataclasses import dataclass
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import torch
from PIL import Image

from ml.species.classifier import (
    SpeciesClassifier,
    get_species_classifier,
    reset_species_classifier,
)
from ml.species.species import (
    SpeciesInfo,
    TARGET_SPECIES,
    NTLNP_TO_VANADRISHTI_MAP,
    get_target_species,
    get_species_by_id,
    get_species_by_common_name,
)


@dataclass
class MockDetection:
    class_name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2) normalized


class TestSpeciesModule(unittest.TestCase):
    """Test suite for Phase 2 species recognition and classification."""

    def setUp(self) -> None:
        reset_species_classifier()

    def tearDown(self) -> None:
        reset_species_classifier()

    def test_species_configuration(self) -> None:
        """Verify target species list, scientific names, prompts, and NTLNP mappings."""
        species = get_target_species()
        self.assertEqual(len(species), 10, "Should have exactly 10 target species.")

        expected_species_ids = {
            "bengal_tiger",
            "indian_leopard",
            "chital",
            "sambar_deer",
            "gaur",
            "sloth_bear",
            "wild_boar",
            "dhole",
            "nilgai",
            "indian_peafowl",
        }
        actual_ids = {sp.id for sp in species}
        self.assertEqual(actual_ids, expected_species_ids)

        for sp in species:
            self.assertTrue(sp.common_name, f"Species {sp.id} missing common_name")
            self.assertTrue(sp.scientific_name, f"Species {sp.id} missing scientific_name")
            prompts = sp.get_prompts()
            self.assertGreaterEqual(len(prompts), 1, f"Species {sp.id} has no prompts")
            # Verify prompts contain the common name or scientific name
            has_ref = any(
                sp.common_name.lower() in p.lower() or sp.scientific_name.lower() in p.lower()
                for p in prompts
            )
            self.assertTrue(has_ref, f"Prompts for {sp.id} don't reference names")

        # Test lookup helpers
        tiger = get_species_by_id("bengal_tiger")
        self.assertIsNotNone(tiger)
        self.assertEqual(tiger.scientific_name, "Panthera tigris tigris")

        leopard = get_species_by_common_name("Indian leopard")
        self.assertIsNotNone(leopard)
        self.assertEqual(leopard.id, "indian_leopard")

        # Test NTLNP compatible mapping
        self.assertEqual(NTLNP_TO_VANADRISHTI_MAP.get("AmurTiger"), "bengal_tiger")
        self.assertEqual(NTLNP_TO_VANADRISHTI_MAP.get("Leopard"), "indian_leopard")
        self.assertEqual(NTLNP_TO_VANADRISHTI_MAP.get("WildBoar"), "wild_boar")

    def test_invalid_crop_handling(self) -> None:
        """Verify validation errors for None, empty, tiny, corrupt, or invalid crops."""
        # Create a mock classifier without loading BioCLIP weights
        with patch("open_clip.create_model_and_transforms") as mock_create, \
             patch("open_clip.get_tokenizer") as mock_tok:

            mock_model = MagicMock()
            mock_model.encode_text.return_value = torch.ones(5, 768)
            mock_create.return_value = (mock_model, None, MagicMock())
            mock_tok.return_value = MagicMock()

            classifier = SpeciesClassifier(device="cpu")

            # 1. None crop
            with self.assertRaises(ValueError):
                classifier.validate_and_preprocess_crop(None)

            # 2. Non-numpy type
            with self.assertRaises(ValueError):
                classifier.validate_and_preprocess_crop("not an array")

            # 3. Empty numpy array
            with self.assertRaises(ValueError):
                classifier.validate_and_preprocess_crop(np.zeros((0, 0, 3), dtype=np.uint8))

            # 4. Tiny crop below min_crop_size (5x5)
            with self.assertRaises(ValueError):
                classifier.validate_and_preprocess_crop(np.zeros((3, 3, 3), dtype=np.uint8))

            # 5. Non-finite values (NaN / Inf)
            nan_arr = np.ones((50, 50, 3), dtype=np.float32)
            nan_arr[10, 10, 0] = np.nan
            with self.assertRaises(ValueError):
                classifier.validate_and_preprocess_crop(nan_arr)

            # 6. Grayscale 2D array should successfully convert to 3-channel RGB PIL Image
            gray_crop = np.full((30, 30), 128, dtype=np.uint8)
            pil_img = classifier.validate_and_preprocess_crop(gray_crop)
            self.assertIsInstance(pil_img, Image.Image)
            self.assertEqual(pil_img.mode, "RGB")
            self.assertEqual(pil_img.size, (30, 30))

            # 7. Grayscale 1-channel 3D array (H, W, 1)
            gray_3d = np.full((40, 40, 1), 200, dtype=np.uint8)
            pil_img_3d = classifier.validate_and_preprocess_crop(gray_3d)
            self.assertEqual(pil_img_3d.mode, "RGB")
            self.assertEqual(pil_img_3d.size, (40, 40))

    def test_output_schema_and_top_k_ordering(self) -> None:
        """Verify schema compliance, top_k ordering, and ranking with mock model."""
        with patch("open_clip.create_model_and_transforms") as mock_create, \
             patch("open_clip.get_tokenizer") as mock_tok:

            num_species = len(TARGET_SPECIES)
            embed_dim = 64

            mock_model = MagicMock()
            # encode_text returns dummy embeddings
            mock_model.encode_text.return_value = torch.randn(5, embed_dim)
            # encode_image returns dummy image feature
            mock_model.encode_image.return_value = torch.randn(1, embed_dim)
            mock_model.logit_scale.exp.return_value = torch.tensor(10.0)

            mock_preprocess = MagicMock(return_value=torch.zeros(3, 224, 224))
            mock_create.return_value = (mock_model, None, mock_preprocess)
            mock_tok.return_value = MagicMock()

            classifier = SpeciesClassifier(device="cpu")

            # Override text_embeddings and logit_scale for deterministic testing
            # Species 0: Bengal tiger (highest score), Species 1: Indian leopard (second)
            classifier.text_embeddings = torch.zeros(num_species, embed_dim)
            classifier.text_embeddings[0, 0] = 1.0  # tiger
            classifier.text_embeddings[1, 1] = 1.0  # leopard
            classifier.text_embeddings[2, 2] = 1.0  # chital

            # Image feature matching tiger mostly, then leopard
            img_feat = torch.zeros(1, embed_dim)
            img_feat[0, 0] = 0.9
            img_feat[0, 1] = 0.4
            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            mock_model.encode_image.return_value = img_feat

            dummy_crop = np.zeros((50, 50, 3), dtype=np.uint8)
            result = classifier.classify_crop(dummy_crop, top_k=3)

            # Check output schema
            self.assertIn("species", result)
            self.assertIn("scientific_name", result)
            self.assertIn("confidence", result)
            self.assertIn("top_k", result)

            self.assertEqual(result["species"], "Bengal tiger")
            self.assertEqual(result["scientific_name"], "Panthera tigris tigris")
            self.assertIsInstance(result["confidence"], float)

            # Check top_k length and ordering
            top_k = result["top_k"]
            self.assertEqual(len(top_k), 3)
            self.assertEqual(top_k[0]["species"], "Bengal tiger")
            self.assertGreater(top_k[0]["confidence"], top_k[1]["confidence"])
            self.assertGreater(top_k[1]["confidence"], top_k[2]["confidence"])

    def test_animal_only_routing(self) -> None:
        """Verify species classification runs strictly on 'animal' and skips 'person'/'vehicle'."""
        with patch("open_clip.create_model_and_transforms") as mock_create, \
             patch("open_clip.get_tokenizer") as mock_tok:

            mock_model = MagicMock()
            mock_model.encode_text.return_value = torch.ones(5, 64)
            mock_model.encode_image.return_value = torch.ones(1, 64)
            mock_model.logit_scale.exp.return_value = torch.tensor(10.0)

            mock_create.return_value = (mock_model, None, MagicMock(return_value=torch.zeros(3, 224, 224)))
            mock_tok.return_value = MagicMock()

            classifier = SpeciesClassifier(device="cpu")

            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            # Case A: Animal detection -> should be routed and classified
            animal_det = MockDetection(
                class_name="animal",
                confidence=0.85,
                bbox=(0.1, 0.1, 0.5, 0.5),
            )
            animal_res = classifier.classify_animal_detection(animal_det, frame)
            self.assertIsNotNone(animal_res, "Animal detection should return classification result.")
            self.assertIn("species", animal_res)

            # Case B: Person detection -> should return None (bypassed)
            person_det = MockDetection(
                class_name="person",
                confidence=0.92,
                bbox=(0.2, 0.2, 0.6, 0.8),
            )
            person_res = classifier.classify_animal_detection(person_det, frame)
            self.assertIsNone(person_res, "Person detection must NOT run species classification.")

            # Case C: Vehicle detection -> should return None (bypassed)
            vehicle_det = MockDetection(
                class_name="vehicle",
                confidence=0.78,
                bbox=(0.0, 0.0, 1.0, 1.0),
            )
            vehicle_res = classifier.classify_animal_detection(vehicle_det, frame)
            self.assertIsNone(vehicle_res, "Vehicle detection must NOT run species classification.")

            # Case D: Dictionary-style detection input
            dict_animal = {"class_name": "animal", "bbox": (0.1, 0.1, 0.4, 0.4)}
            dict_res = classifier.classify_animal_detection(dict_animal, frame)
            self.assertIsNotNone(dict_res)

            dict_person = {"class_name": "person", "bbox": (0.1, 0.1, 0.4, 0.4)}
            self.assertIsNone(classifier.classify_animal_detection(dict_person, frame))

    def test_singleton_behavior(self) -> None:
        """Verify get_species_classifier returns singleton and reset clears it."""
        with patch("open_clip.create_model_and_transforms") as mock_create, \
             patch("open_clip.get_tokenizer") as mock_tok:

            mock_model = MagicMock()
            mock_model.encode_text.return_value = torch.ones(5, 64)
            mock_create.return_value = (mock_model, None, MagicMock())
            mock_tok.return_value = MagicMock()

            inst1 = get_species_classifier()
            inst2 = get_species_classifier()
            self.assertIs(inst1, inst2, "get_species_classifier must return singleton instance.")

            reset_species_classifier()
            inst3 = get_species_classifier()
            self.assertIsNot(inst1, inst3, "After reset, a new instance should be created.")


if __name__ == "__main__":
    unittest.main()
