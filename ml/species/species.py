"""
VanaDrishti Wildlife Species Taxonomy and Registry.
Phase 2: Target Species for Tadoba-Andhari Tiger Reserve and Central Indian Forests.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SpeciesInfo:
    """Metadata and prompt definition for a target wildlife species."""
    id: str
    common_name: str
    scientific_name: str
    aliases: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)

    def get_prompts(self) -> List[str]:
        """Return the list of text prompts for zero-shot BioCLIP classification."""
        if self.prompts:
            return list(self.prompts)
        return [
            f"a photo of a {self.common_name} ({self.scientific_name})",
            f"a camera trap photo of a {self.common_name}",
            f"a photo of {self.scientific_name}",
            f"{self.common_name}, {self.scientific_name}",
        ]


# 10 Target Wildlife Species for VanaDrishti (Tadoba-Andhari Tiger Reserve)
TARGET_SPECIES: List[SpeciesInfo] = [
    SpeciesInfo(
        id="bengal_tiger",
        common_name="Bengal tiger",
        scientific_name="Panthera tigris tigris",
        aliases=["tiger", "Royal Bengal tiger", "Panthera tigris", "AmurTiger"],
        prompts=[
            "a photo of a Bengal tiger (Panthera tigris tigris)",
            "a camera trap photo of a Bengal tiger",
            "a photo of Panthera tigris tigris",
            "a photo of a tiger in the forest",
            "Bengal tiger, Panthera tigris tigris",
        ],
    ),
    SpeciesInfo(
        id="indian_leopard",
        common_name="Indian leopard",
        scientific_name="Panthera pardus fusca",
        aliases=["leopard", "Panthera pardus", "Leopard"],
        prompts=[
            "a photo of an Indian leopard (Panthera pardus fusca)",
            "a camera trap photo of an Indian leopard",
            "a photo of Panthera pardus fusca",
            "a photo of a leopard in the jungle",
            "Indian leopard, Panthera pardus fusca",
        ],
    ),
    SpeciesInfo(
        id="chital",
        common_name="chital / spotted deer",
        scientific_name="Axis axis",
        aliases=["chital", "spotted deer", "Axis axis", "cheetal"],
        prompts=[
            "a photo of a chital spotted deer (Axis axis)",
            "a camera trap photo of a chital spotted deer",
            "a photo of Axis axis",
            "a photo of a spotted deer with white spots",
            "chital, Axis axis",
        ],
    ),
    SpeciesInfo(
        id="sambar_deer",
        common_name="sambar deer",
        scientific_name="Rusa unicolor",
        aliases=["sambar", "Rusa unicolor", "Cervus unicolor"],
        prompts=[
            "a photo of a sambar deer (Rusa unicolor)",
            "a camera trap photo of a sambar deer",
            "a photo of Rusa unicolor",
            "a photo of a large brown sambar deer in the forest",
            "sambar deer, Rusa unicolor",
        ],
    ),
    SpeciesInfo(
        id="gaur",
        common_name="gaur",
        scientific_name="Bos gaurus",
        aliases=["Indian bison", "Bos gaurus", "gaur bison"],
        prompts=[
            "a photo of a gaur Indian bison (Bos gaurus)",
            "a camera trap photo of a gaur Indian bison",
            "a photo of Bos gaurus",
            "a photo of a large dark gaur with muscular ridge",
            "gaur, Bos gaurus",
        ],
    ),
    SpeciesInfo(
        id="sloth_bear",
        common_name="sloth bear",
        scientific_name="Melursus ursinus",
        aliases=["sloth bear", "Melursus ursinus", "Indian sloth bear"],
        prompts=[
            "a photo of a sloth bear (Melursus ursinus)",
            "a camera trap photo of a sloth bear",
            "a photo of Melursus ursinus",
            "a photo of a shaggy black sloth bear with pale snout",
            "sloth bear, Melursus ursinus",
        ],
    ),
    SpeciesInfo(
        id="wild_boar",
        common_name="wild boar",
        scientific_name="Sus scrofa",
        aliases=["wild boar", "Sus scrofa", "wild pig", "WildBoar"],
        prompts=[
            "a photo of a wild boar (Sus scrofa)",
            "a camera trap photo of a wild boar",
            "a photo of Sus scrofa",
            "a photo of a bristly wild boar with tusks",
            "wild boar, Sus scrofa",
        ],
    ),
    SpeciesInfo(
        id="dhole",
        common_name="dhole / Indian wild dog",
        scientific_name="Cuon alpinus",
        aliases=["dhole", "Indian wild dog", "Cuon alpinus", "red dog", "Asiatic wild dog"],
        prompts=[
            "a photo of a dhole Indian wild dog (Cuon alpinus)",
            "a camera trap photo of a dhole wild dog",
            "a photo of Cuon alpinus",
            "a photo of a reddish-brown dhole pack hunter",
            "dhole, Cuon alpinus",
        ],
    ),
    SpeciesInfo(
        id="nilgai",
        common_name="nilgai",
        scientific_name="Boselaphus tragocamelus",
        aliases=["nilgai", "blue bull", "Boselaphus tragocamelus"],
        prompts=[
            "a photo of a nilgai blue bull (Boselaphus tragocamelus)",
            "a camera trap photo of a nilgai antelope",
            "a photo of Boselaphus tragocamelus",
            "a photo of a large grey-blue nilgai antelope",
            "nilgai, Boselaphus tragocamelus",
        ],
    ),
    SpeciesInfo(
        id="indian_peafowl",
        common_name="Indian peafowl",
        scientific_name="Pavo cristatus",
        aliases=["peacock", "peahen", "peafowl", "Pavo cristatus", "Indian peacock"],
        prompts=[
            "a photo of an Indian peafowl (Pavo cristatus)",
            "a camera trap photo of an Indian peacock or peahen",
            "a photo of Pavo cristatus",
            "a photo of an iridescent Indian peafowl",
            "Indian peafowl, Pavo cristatus",
        ],
    ),
]

# Map by id for fast lookup
SPECIES_BY_ID: Dict[str, SpeciesInfo] = {sp.id: sp for sp in TARGET_SPECIES}

# Compatible mapping from NTLNP VOC class names to VanaDrishti target species IDs
NTLNP_TO_VANADRISHTI_MAP: Dict[str, str] = {
    "AmurTiger": "bengal_tiger",
    "Leopard": "indian_leopard",
    "WildBoar": "wild_boar",
}


def get_target_species() -> List[SpeciesInfo]:
    """Return the list of configured target wildlife species."""
    return list(TARGET_SPECIES)


def get_species_by_id(species_id: str) -> Optional[SpeciesInfo]:
    """Lookup species info by unique id."""
    return SPECIES_BY_ID.get(species_id)


def get_species_by_common_name(name: str) -> Optional[SpeciesInfo]:
    """Lookup species info by common name (case-insensitive)."""
    norm = name.strip().lower()
    for sp in TARGET_SPECIES:
        if sp.common_name.lower() == norm or any(a.lower() == norm for a in sp.aliases):
            return sp
    return None


def normalize_to_target_group(species_name: str) -> str:
    """
    Normalize fine-grained species prediction or dataset label
    to coarse compatible target group for evaluation (e.g. 'tiger', 'leopard', 'wild_boar').
    """
    s = species_name.strip().lower()
    if "amurtiger" in s or "bengal tiger" in s or "tiger" in s or "tigris" in s:
        return "tiger"
    if ("leopard" in s or "pardus" in s) and "cat" not in s:
        return "leopard"
    if "wildboar" in s or "wild boar" in s or "sus scrofa" in s or "boar" in s or "pig" in s:
        return "wild_boar"
    if "chital" in s or "spotted deer" in s or "axis axis" in s:
        return "chital"
    if "sambar" in s or "rusa unicolor" in s:
        return "sambar"
    if "gaur" in s or "bos gaurus" in s or "bison" in s:
        return "gaur"
    if "sloth bear" in s or "melursus ursinus" in s:
        return "sloth_bear"
    if "dhole" in s or "cuon alpinus" in s or "wild dog" in s:
        return "dhole"
    if "nilgai" in s or "boselaphus tragocamelus" in s or "blue bull" in s:
        return "nilgai"
    if "peafowl" in s or "peacock" in s or "pavo cristatus" in s:
        return "peafowl"
    return s

