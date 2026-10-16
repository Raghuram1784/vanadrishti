"""
VanaDrishti Phase 2: Wildlife Species Classifier using BioCLIP 2.

Provides zero-shot fine-grained wildlife classification for animal crops
produced by Phase 1 detection.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image
import torch

from ml.species.species import (
    SpeciesInfo,
    get_target_species,
)

logger = logging.getLogger("vanadrishti.species")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class SpeciesClassifier:
    """
    Zero-shot Wildlife Species Classifier utilizing BioCLIP 2.

    IMPORTANT STATISTICAL NOTE:
    BioCLIP similarity scores are raw cosine similarities between image and text
    feature representations. The reported `confidence` values are softmax-normalized
    scaled logits (using the CLIP temperature / logit_scale parameter) intended
    strictly for ranking and relative display. They are NOT calibrated Bayesian
    posterior probabilities.
    """

    def __init__(
        self,
        model_name: str = "hf-hub:imageomics/bioclip-2",
        device: Optional[str] = None,
        species_list: Optional[List[SpeciesInfo]] = None,
        min_crop_size: int = 5,
    ) -> None:
        """
        Initialize the BioCLIP 2 species classifier.

        Args:
            model_name: Hugging Face or OpenCLIP model identifier.
            device: Computing device ('cuda', 'cpu', or None for auto-detect).
            species_list: List of target species. Defaults to VanaDrishti target species.
            min_crop_size: Minimum width and height for valid crops in pixels.
        """
        self.model_name = model_name
        self.min_crop_size = min_crop_size
        self.species_list = species_list if species_list is not None else get_target_species()

        # Device selection
        if device is not None:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        logger.info(
            "Initializing BioCLIP 2 classifier (model: %s, device: %s, species_count: %d)...",
            self.model_name,
            self.device,
            len(self.species_list),
        )

        import open_clip

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.model_name,
            device=self.device,
        )
        self.tokenizer = open_clip.get_tokenizer(self.model_name)
        self.model.eval()

        # Cache temperature scale
        if hasattr(self.model, "logit_scale"):
            self.logit_scale = float(self.model.logit_scale.exp().item())
        else:
            self.logit_scale = 100.0

        # Precompute and cache normalized text embeddings for all target species
        self.text_embeddings = self._precompute_text_embeddings()
        logger.info(
            "BioCLIP 2 species classifier loaded successfully on %s (cached embeddings shape: %s).",
            self.device,
            tuple(self.text_embeddings.shape),
        )

    def _precompute_text_embeddings(self) -> torch.Tensor:
        """
        Precompute ensemble text embeddings for each target species.
        Embeddings are averaged across species prompts and normalized.

        Returns:
            Normalized text embeddings matrix of shape [num_species, embed_dim].
        """
        embeddings_list = []
        with torch.no_grad():
            for sp in self.species_list:
                prompts = sp.get_prompts()
                tokens = self.tokenizer(prompts).to(self.device)
                text_features = self.model.encode_text(tokens)
                # Normalize individual prompt vectors
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                # Average prompt features for the species ensemble
                mean_feature = text_features.mean(dim=0)
                # Re-normalize species centroid vector
                mean_feature = mean_feature / mean_feature.norm(dim=-1, keepdim=True)
                embeddings_list.append(mean_feature)

        stacked = torch.stack(embeddings_list, dim=0)  # [num_species, embed_dim]
        return stacked

    def validate_and_preprocess_crop(self, crop: Any) -> Image.Image:
        """
        Validate input crop and convert to PIL RGB Image.

        Args:
            crop: Input image crop, typically BGR numpy ndarray from OpenCV.

        Returns:
            PIL RGB Image ready for BioCLIP transforms.

        Raises:
            ValueError: If crop is None, invalid type, empty, corrupt, or too small.
        """
        if crop is None:
            raise ValueError("Input crop is None.")

        if not isinstance(crop, np.ndarray):
            raise ValueError(f"Input crop must be a numpy.ndarray, got {type(crop)}.")

        if crop.size == 0 or crop.ndim < 2:
            raise ValueError(f"Input crop is empty or invalid shape: {crop.shape}")

        h, w = crop.shape[:2]
        if h < self.min_crop_size or w < self.min_crop_size:
            raise ValueError(
                f"Input crop dimensions ({w}x{h}) are below minimum threshold "
                f"({self.min_crop_size}x{self.min_crop_size} px)."
            )

        # Check for NaN / Inf
        if not np.isfinite(crop).all():
            raise ValueError("Input crop contains NaN or infinite values.")

        # Handle grayscale (2D array or 3D with 1 channel)
        if crop.ndim == 2:
            rgb_arr = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
        elif crop.ndim == 3 and crop.shape[2] == 1:
            rgb_arr = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
        elif crop.ndim == 3 and crop.shape[2] == 3:
            rgb_arr = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        elif crop.ndim == 3 and crop.shape[2] == 4:
            rgb_arr = cv2.cvtColor(crop, cv2.COLOR_BGRA2RGB)
        else:
            raise ValueError(f"Unsupported number of image channels: {crop.shape}")

        return Image.fromarray(rgb_arr)

    def classify_crop(
        self,
        crop: np.ndarray,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Classify an animal image crop against the configured species list.

        Args:
            crop: BGR OpenCV image crop (np.ndarray).
            top_k: Number of ranked predictions to return in 'top_k'.

        Returns:
            Dictionary with schema:
            {
                "species": str,              # Top-1 common name
                "scientific_name": str,      # Top-1 scientific name
                "confidence": float,         # Top-1 softmax score [0, 1]
                "top_k": [
                    {
                        "species": str,
                        "scientific_name": str,
                        "confidence": float,
                    },
                    ...
                ]
            }
        """
        pil_image = self.validate_and_preprocess_crop(crop)
        image_tensor = self.preprocess(pil_image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Cosine similarity between image and all species text embeddings
            cos_sims = (image_features @ self.text_embeddings.T).squeeze(0)  # [num_species]

            # Softmax ranking display scores
            scaled_logits = cos_sims * self.logit_scale
            probs = torch.softmax(scaled_logits, dim=-1)

        k = max(1, min(top_k, len(self.species_list)))
        top_scores, top_indices = torch.topk(probs, k=k)

        top_k_results: List[Dict[str, Any]] = []
        for score, idx in zip(top_scores.cpu().tolist(), top_indices.cpu().tolist()):
            sp = self.species_list[idx]
            top_k_results.append({
                "species": sp.common_name,
                "scientific_name": sp.scientific_name,
                "confidence": round(float(score), 4),
            })

        best = top_k_results[0]
        return {
            "species": best["species"],
            "scientific_name": best["scientific_name"],
            "confidence": best["confidence"],
            "top_k": top_k_results,
        }

    def classify_animal_detection(
        self,
        detection: Any,
        frame: np.ndarray,
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Animal-only pipeline routing helper.

        Extracts the bounding box crop from the frame and runs species classification
        ONLY if the detection belongs to class 'animal'.
        Does NOT run species classification on 'person' or 'vehicle' detections.

        Args:
            detection: Detection object (e.g., from WildlifeDetector) with attributes
                       `class_name` and `bbox` (normalized [x1, y1, x2, y2]).
            frame: Full original BGR video frame or image.
            top_k: Number of ranked predictions to return.

        Returns:
            Species classification dictionary if detection is an animal,
            or None if detection is not an animal or crop is invalid.
        """
        class_name = getattr(detection, "class_name", None)
        if class_name is None and isinstance(detection, dict):
            class_name = detection.get("class_name")

        # Strict routing: only classify animals
        if class_name != "animal":
            return None

        # Extract normalized bbox coordinates
        bbox = getattr(detection, "bbox", None)
        if bbox is None and isinstance(detection, dict):
            bbox = detection.get("bbox")

        if bbox is None or frame is None:
            return None

        h, w = frame.shape[:2]
        x1_norm, y1_norm, x2_norm, y2_norm = bbox
        x1 = max(0, min(w - 1, round(x1_norm * w)))
        y1 = max(0, min(h - 1, round(y1_norm * h)))
        x2 = max(0, min(w, round(x2_norm * w)))
        y2 = max(0, min(h, round(y2_norm * h)))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        try:
            return self.classify_crop(crop, top_k=top_k)
        except ValueError as err:
            logger.warning("Failed to classify animal crop: %s", err)
            return None


# Global singleton instance
_SPECIES_CLASSIFIER_INSTANCE: Optional[SpeciesClassifier] = None


def get_species_classifier(
    model_name: str = "hf-hub:imageomics/bioclip-2",
    device: Optional[str] = None,
) -> SpeciesClassifier:
    """
    Get or create the singleton instance of SpeciesClassifier.

    Ensures BioCLIP 2 weights are loaded into memory exactly once.
    """
    global _SPECIES_CLASSIFIER_INSTANCE
    if _SPECIES_CLASSIFIER_INSTANCE is None:
        _SPECIES_CLASSIFIER_INSTANCE = SpeciesClassifier(
            model_name=model_name,
            device=device,
        )
    return _SPECIES_CLASSIFIER_INSTANCE


def reset_species_classifier() -> None:
    """Reset the singleton instance (primarily for testing and mock injection)."""
    global _SPECIES_CLASSIFIER_INSTANCE
    _SPECIES_CLASSIFIER_INSTANCE = None
