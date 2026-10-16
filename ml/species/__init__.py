"""
VanaDrishti Wildlife Species Recognition Module.
Phase 2: Fine-grained species recognition powered by BioCLIP 2.
"""

from ml.species.classifier import (
    SpeciesClassifier,
    get_species_classifier,
    reset_species_classifier,
)
from ml.species.species import (
    SpeciesInfo,
    TARGET_SPECIES,
    SPECIES_BY_ID,
    NTLNP_TO_VANADRISHTI_MAP,
    get_target_species,
    get_species_by_id,
    get_species_by_common_name,
    normalize_to_target_group,
)

__all__ = [
    "SpeciesClassifier",
    "get_species_classifier",
    "reset_species_classifier",
    "SpeciesInfo",
    "TARGET_SPECIES",
    "SPECIES_BY_ID",
    "NTLNP_TO_VANADRISHTI_MAP",
    "get_target_species",
    "get_species_by_id",
    "get_species_by_common_name",
    "normalize_to_target_group",
]
