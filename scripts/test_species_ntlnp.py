"""
VanaDrishti Phase 2: Wildlife Species Recognition Benchmark on NTLNP Dataset.

Evaluates zero-shot BioCLIP 2 species classification on ground-truth crops
of compatible wildlife species (AmurTiger, Leopard, WildBoar) from NTLNP.
"""

import argparse
import csv
import json
import logging
import os
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from ml.species import get_species_classifier, NTLNP_TO_VANADRISHTI_MAP, get_species_by_id

logger = logging.getLogger("vanadrishti.test_species")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Compatible mapping: NTLNP label -> (evaluation group key, target species id)
COMPATIBLE_SPECIES = {
    "AmurTiger": ("tiger", "bengal_tiger"),
    "Leopard": ("leopard", "indian_leopard"),
    "WildBoar": ("wild_boar", "wild_boar"),
}


def parse_voc_annotation(xml_path: Path) -> List[Dict[str, Any]]:
    """Parse Pascal VOC XML annotation and extract species objects and bounding boxes."""
    if not xml_path.exists():
        logger.warning("Annotation XML not found: %s", xml_path.name)
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as err:
        logger.warning("Failed to parse XML %s: %s", xml_path.name, err)
        return []

    objects = []
    for obj in root.findall("object"):
        name_elem = obj.find("name")
        if name_elem is None or not name_elem.text:
            continue
        species_name = name_elem.text.strip()

        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue

        try:
            xmin = float(bndbox.findtext("xmin", "0"))
            ymin = float(bndbox.findtext("ymin", "0"))
            xmax = float(bndbox.findtext("xmax", "0"))
            ymax = float(bndbox.findtext("ymax", "0"))
        except (ValueError, TypeError):
            continue

        objects.append({
            "species": species_name,
            "bbox": (xmin, ymin, xmax, ymax),
        })

    return objects


def collect_compatible_samples(
    dataset_dir: Path,
    limit_per_species: int = 20,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Scan dataset annotations and collect up to limit_per_species per compatible class.
    """
    jpeg_dir = dataset_dir / "JPEGImages"
    ann_dir = dataset_dir / "Annotations"

    if not jpeg_dir.exists() or not ann_dir.exists():
        raise FileNotFoundError(
            f"Dataset structure invalid at {dataset_dir}. Expected JPEGImages and Annotations folders."
        )

    # Group by compatible species
    candidates_by_species: Dict[str, List[Dict[str, Any]]] = {
        group_key: [] for group_key, _ in COMPATIBLE_SPECIES.values()
    }

    # Index all XML files sorted for determinism
    xml_files = sorted(ann_dir.glob("*.xml"))
    for xml_path in xml_files:
        stem = xml_path.stem
        # Check matching image (.jpg or .jpeg)
        img_path = jpeg_dir / f"{stem}.jpg"
        if not img_path.exists():
            img_path = jpeg_dir / f"{stem}.jpeg"
            if not img_path.exists():
                continue

        objects = parse_voc_annotation(xml_path)
        if not objects:
            continue

        # Look for first compatible object in image
        for obj in objects:
            ntlnp_label = obj["species"]
            if ntlnp_label in COMPATIBLE_SPECIES:
                group_key, target_id = COMPATIBLE_SPECIES[ntlnp_label]
                candidates_by_species[group_key].append({
                    "image_path": img_path,
                    "xml_path": xml_path,
                    "ntlnp_species": ntlnp_label,
                    "group_key": group_key,
                    "target_id": target_id,
                    "bbox": obj["bbox"],
                })
                break  # one primary sample per image

    # Deterministic sampling
    rng = random.Random(seed)
    selected_samples: List[Dict[str, Any]] = []

    for group_key, candidates in candidates_by_species.items():
        rng.shuffle(candidates)
        sampled = candidates[:limit_per_species]
        logger.info(
            "Sampled %d / %d available images for %s",
            len(sampled),
            len(candidates),
            group_key,
        )
        selected_samples.extend(sampled)

    return selected_samples


def evaluate_bioclip_on_ntlnp(
    dataset_dir: Path,
    output_dir: Path,
    limit_per_species: int = 20,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run Phase 2 BioCLIP evaluation on ground-truth crops from NTLNP."""
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = collect_compatible_samples(
        dataset_dir=dataset_dir,
        limit_per_species=limit_per_species,
        seed=seed,
    )
    total_images = len(samples)
    logger.info("Starting BioCLIP evaluation on %d total compatible samples...", total_images)

    classifier = get_species_classifier()

    results_rows: List[Dict[str, Any]] = []
    per_species_stats: Dict[str, Dict[str, Any]] = {
        group_key: {
            "images": 0,
            "top1_correct": 0,
            "top3_correct": 0,
            "top1_scores": [],
        }
        for group_key, _ in COMPATIBLE_SPECIES.values()
    }

    for idx, sample in enumerate(samples, 1):
        img_path: Path = sample["image_path"]
        group_key: str = sample["group_key"]
        target_id: str = sample["target_id"]
        ntlnp_label: str = sample["ntlnp_species"]
        xmin, ymin, xmax, ymax = sample["bbox"]

        target_info = get_species_by_id(target_id)
        expected_common_name = target_info.common_name if target_info else target_id

        # Load image
        img = cv2.imread(str(img_path))
        if img is None:
            logger.warning("Could not read image: %s", img_path.name)
            continue

        h, w = img.shape[:2]
        x1 = max(0, min(w - 1, round(xmin)))
        y1 = max(0, min(h - 1, round(ymin)))
        x2 = max(0, min(w, round(xmax)))
        y2 = max(0, min(h, round(ymax)))

        if x2 <= x1 or y2 <= y1:
            logger.warning("Invalid bounding box dimensions for %s", img_path.name)
            continue

        crop = img[y1:y2, x1:x2]

        try:
            prediction = classifier.classify_crop(crop, top_k=3)
        except Exception as err:
            logger.warning("Classification failed for %s: %s", img_path.name, err)
            continue

        top1_species = prediction["species"]
        top1_conf = prediction["confidence"]
        top_k_list = prediction["top_k"]

        # Check Top-1 match
        top1_match = (top1_species.lower() == expected_common_name.lower())

        # Check Top-3 match
        top3_species_names = [item["species"].lower() for item in top_k_list[:3]]
        top3_match = (expected_common_name.lower() in top3_species_names)

        # Update per-species tracking
        stat = per_species_stats[group_key]
        stat["images"] += 1
        if top1_match:
            stat["top1_correct"] += 1
        if top3_match:
            stat["top3_correct"] += 1
        stat["top1_scores"].append(top1_conf)

        results_rows.append({
            "image": img_path.name,
            "ntlnp_species": ntlnp_label,
            "target_species": expected_common_name,
            "top1_prediction": top1_species,
            "top1_scientific": prediction["scientific_name"],
            "top1_confidence": top1_conf,
            "top1_correct": top1_match,
            "top3_correct": top3_match,
            "top3_predictions": " | ".join(
                f"{item['species']} ({item['confidence']:.2f})" for item in top_k_list[:3]
            ),
        })

        if idx % 10 == 0 or idx == total_images:
            logger.info("Processed %d / %d images...", idx, total_images)

    # Compute aggregate metrics
    evaluated_total = len(results_rows)
    total_top1 = sum(r["top1_correct"] for r in results_rows)
    total_top3 = sum(r["top3_correct"] for r in results_rows)
    all_top1_scores = [r["top1_confidence"] for r in results_rows]

    top1_acc = (total_top1 / evaluated_total) if evaluated_total > 0 else 0.0
    top3_acc = (total_top3 / evaluated_total) if evaluated_total > 0 else 0.0
    mean_top1_score = (sum(all_top1_scores) / evaluated_total) if evaluated_total > 0 else 0.0

    summary_per_species = {}
    for group_key, stat in per_species_stats.items():
        cnt = stat["images"]
        c1 = stat["top1_correct"]
        c3 = stat["top3_correct"]
        scores = stat["top1_scores"]
        summary_per_species[group_key] = {
            "images": cnt,
            "top1_correct": c1,
            "top1_accuracy": round((c1 / cnt) if cnt > 0 else 0.0, 4),
            "top3_correct": c3,
            "top3_accuracy": round((c3 / cnt) if cnt > 0 else 0.0, 4),
            "mean_top1_score": round((sum(scores) / cnt) if cnt > 0 else 0.0, 4),
        }

    summary_data = {
        "dataset": str(dataset_dir),
        "total_images": evaluated_total,
        "top1_correct": total_top1,
        "top1_accuracy": round(top1_acc, 4),
        "top3_correct": total_top3,
        "top3_accuracy": round(top3_acc, 4),
        "mean_top1_score": round(mean_top1_score, 4),
        "per_species": summary_per_species,
    }

    # Save summary.json
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    logger.info("Saved summary report to %s", summary_path)

    # Save results.csv
    results_path = output_dir / "results.csv"
    with open(results_path, "w", newline="", encoding="utf-8") as f:
        if results_rows:
            writer = csv.DictWriter(f, fieldnames=list(results_rows[0].keys()))
            writer.writeheader()
            writer.writerows(results_rows)
    logger.info("Saved detailed results to %s", results_path)

    # Print clean terminal summary
    print("\n" + "=" * 70)
    print("VanaDrishti Phase 2: BioCLIP 2 Species Recognition Benchmark")
    print("-" * 70)
    print(f"Total images evaluated:  {evaluated_total}")
    print(f"Top-1 correct:           {total_top1} / {evaluated_total}")
    print(f"Top-1 accuracy:          {top1_acc * 100:.2f}%")
    print(f"Top-3 correct:           {total_top3} / {evaluated_total}")
    print(f"Top-3 accuracy:          {top3_acc * 100:.2f}%")
    print(f"Mean Top-1 score:        {mean_top1_score:.4f}")
    print("-" * 70)
    print("Per-Species Evaluation Breakdown:")
    print("-" * 70)
    print(f"{'Species Group':<16} {'Images':<8} {'Top-1 Acc':<12} {'Top-3 Acc':<12} {'Mean Score':<10}")
    print("-" * 70)
    for group_key, stat in summary_per_species.items():
        print(
            f"{group_key:<16} "
            f"{stat['images']:<8} "
            f"{stat['top1_accuracy'] * 100:>8.2f}%   "
            f"{stat['top3_accuracy'] * 100:>8.2f}%   "
            f"{stat['mean_top1_score']:>8.4f}"
        )
    print("=" * 70 + "\n")

    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 2: BioCLIP 2 Wildlife Species Evaluation"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/validation/ntlnp_night",
        help="Path to NTLNP dataset root containing JPEGImages and Annotations",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/phase2_bioclip",
        help="Directory to save summary.json and results.csv",
    )
    parser.add_argument(
        "--limit-per-species",
        type=int,
        default=20,
        help="Max images per compatible species (default: 20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible dataset sampling (default: 42)",
    )

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    evaluate_bioclip_on_ntlnp(
        dataset_dir=dataset_path,
        output_dir=output_path,
        limit_per_species=args.limit_per_species,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
