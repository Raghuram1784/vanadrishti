"""
VanaDrishti - Phase 1 Evaluation & NTLNP Night Benchmark Subsystem

Evaluates MegaDetector V6 against the Northeast Tiger and Leopard National Park
(NTLNP) night camera-trap validation dataset with Pascal VOC XML annotations.

Treats all wildlife species in NTLNP as ground-truth class "animal" (species identification
is reserved for Phase 2). Measures object-level recall, image-level detection rate,
confidence statistics, IoU overlap, and per-species breakdown.
"""

import os
import sys
import time
import json
import csv
import random
import argparse
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict

import cv2
import numpy as np

# Ensure project root is in sys.path when executed directly as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Use existing WildlifeDetector singleton from Phase 1
from ml.detector import get_detector

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [vanadrishti.benchmark]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("vanadrishti.benchmark")


def calculate_iou(box_a: List[float], box_b: List[float]) -> float:
    """
    Computes Intersection over Union (IoU) between two bounding boxes.
    Boxes are in [x1, y1, x2, y2] format.
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0

    return float(inter_area / union_area)


def parse_pascal_voc(xml_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parses a Pascal VOC XML annotation file.
    Extracts image dimensions and ground-truth objects (species name and bounding box).

    Returns:
        Dict with keys:
            - width (int)
            - height (int)
            - objects: list of dicts with 'species' and 'bbox' [xmin, ymin, xmax, ymax]
        or None if parsing fails.
    """
    if not xml_path.exists():
        logger.warning("Annotation XML file not found: %s", xml_path)
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as exc:
        logger.warning("Failed to parse XML file %s: %s", xml_path, exc)
        return None

    # Parse image dimensions
    width, height = 0, 0
    size_elem = root.find("size")
    if size_elem is not None:
        try:
            w_elem = size_elem.find("width")
            h_elem = size_elem.find("height")
            if w_elem is not None and w_elem.text:
                width = int(float(w_elem.text.strip()))
            if h_elem is not None and h_elem.text:
                height = int(float(h_elem.text.strip()))
        except (ValueError, TypeError):
            width, height = 0, 0

    objects: List[Dict[str, Any]] = []
    for obj_elem in root.findall("object"):
        name_elem = obj_elem.find("name")
        species_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else "Unknown"

        bndbox_elem = obj_elem.find("bndbox")
        if bndbox_elem is None:
            continue

        try:
            xmin = float(bndbox_elem.find("xmin").text.strip())  # type: ignore
            ymin = float(bndbox_elem.find("ymin").text.strip())  # type: ignore
            xmax = float(bndbox_elem.find("xmax").text.strip())  # type: ignore
            ymax = float(bndbox_elem.find("ymax").text.strip())  # type: ignore
        except (AttributeError, ValueError, TypeError) as exc:
            logger.warning("Invalid bndbox coordinates in %s: %s", xml_path, exc)
            continue

        # Sanitize coordinate order
        if xmax < xmin:
            xmin, xmax = xmax, xmin
        if ymax < ymin:
            ymin, ymax = ymax, ymin

        if xmax <= xmin or ymax <= ymin:
            continue

        objects.append({
            "species": species_name,
            "bbox": [xmin, ymin, xmax, ymax]
        })

    return {
        "width": width,
        "height": height,
        "objects": objects
    }


def match_gt_and_predictions(
    gt_objects: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
    img_width: int,
    img_height: int,
    iou_threshold: float = 0.50
) -> Dict[str, Any]:
    """
    Compares predicted MegaDetector animal boxes with ground-truth animal boxes.
    Sorts predictions by confidence descending and performs greedy assignment.

    Args:
        gt_objects: Ground-truth objects with 'species' and 'bbox' [xmin, ymin, xmax, ymax].
        predictions: MegaDetector animal predictions with normalized 'bbox' and 'confidence'.
        img_width: Image width in pixels.
        img_height: Image height in pixels.
        iou_threshold: Minimum IoU for a successful detection (default: 0.50).

    Returns:
        Dict containing match statistics, assigned pairings, and unmatched counts.
    """
    # Convert normalized predictions to pixel coordinates
    preds_with_pixel = []
    for p in predictions:
        nx1, ny1, nx2, ny2 = p["bbox"]
        px_box = [
            float(nx1 * img_width),
            float(ny1 * img_height),
            float(nx2 * img_width),
            float(ny2 * img_height)
        ]
        preds_with_pixel.append({
            "confidence": float(p.get("confidence", 0.0)),
            "norm_bbox": p["bbox"],
            "pixel_bbox": px_box,
            "matched": False
        })

    # Sort predictions by confidence descending
    preds_with_pixel.sort(key=lambda x: x["confidence"], reverse=True)

    # Initialize ground truth matching records
    gt_matches = []
    for gt in gt_objects:
        gt_matches.append({
            "species": gt["species"],
            "bbox": gt["bbox"],
            "matched": False,
            "matched_confidence": 0.0,
            "matched_iou": 0.0,
            "best_iou": 0.0
        })

    # Greedy matching from highest confidence prediction to best unassigned GT box
    for pred in preds_with_pixel:
        best_iou = 0.0
        best_gt_idx = -1

        for idx, gt in enumerate(gt_matches):
            iou = calculate_iou(gt["bbox"], pred["pixel_bbox"])
            # Track overall best IoU for GT object regardless of match status
            if iou > gt["best_iou"]:
                gt["best_iou"] = iou

            if not gt["matched"] and iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_gt_idx = idx

        if best_gt_idx != -1:
            gt_matches[best_gt_idx]["matched"] = True
            gt_matches[best_gt_idx]["matched_confidence"] = pred["confidence"]
            gt_matches[best_gt_idx]["matched_iou"] = best_iou
            pred["matched"] = True

    # Also update best IoU for any GT that had predictions evaluated after its match
    for gt in gt_matches:
        for pred in preds_with_pixel:
            iou = calculate_iou(gt["bbox"], pred["pixel_bbox"])
            if iou > gt["best_iou"]:
                gt["best_iou"] = iou

    matched_gt = [gt for gt in gt_matches if gt["matched"]]
    missed_gt = [gt for gt in gt_matches if not gt["matched"]]
    unmatched_preds = [p for p in preds_with_pixel if not p["matched"]]

    # Image-level best IoU and max confidence
    best_image_iou = 0.0
    for gt in gt_matches:
        for pred in preds_with_pixel:
            iou = calculate_iou(gt["bbox"], pred["pixel_bbox"])
            if iou > best_image_iou:
                best_image_iou = iou

    max_conf = max([p["confidence"] for p in preds_with_pixel], default=0.0)

    return {
        "gt_matches": gt_matches,
        "matched_gt": matched_gt,
        "missed_gt": missed_gt,
        "predictions": preds_with_pixel,
        "unmatched_predictions": unmatched_preds,
        "matched_count": len(matched_gt),
        "missed_count": len(missed_gt),
        "prediction_count": len(preds_with_pixel),
        "best_image_iou": best_image_iou,
        "max_confidence": max_conf,
        "detected": len(matched_gt) > 0
    }


def draw_missed_visual(
    image_path: Path,
    gt_objects: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
    img_width: int,
    img_height: int,
    output_path: Path,
    best_iou: float
) -> None:
    """
    Renders diagnostic visualization for missed detections and saves to output_path.
    Draws ground-truth boxes in Green and MegaDetector candidate predictions in Orange.
    """
    frame = cv2.imread(str(image_path))
    if frame is None:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = frame.copy()

    # Draw Ground Truth boxes (Green: (40, 210, 80))
    for gt in gt_objects:
        xmin, ymin, xmax, ymax = [int(round(c)) for c in gt["bbox"]]
        species = gt.get("species", "Animal")
        matched = gt.get("matched", False)

        color = (40, 210, 80) if matched else (0, 200, 255)  # Gold/Yellow for missed GT
        label = f"GT: {species}" + (" [DETECTED]" if matched else " [MISSED]")

        cv2.rectangle(canvas, (xmin, ymin), (xmax, ymax), color, 2, cv2.LINE_AA)
        cv2.putText(
            canvas, label, (xmin, max(20, ymin - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA
        )

    # Draw MegaDetector Predicted boxes (Orange/Red: (0, 90, 255))
    for pred in predictions:
        px1, py1, px2, py2 = [int(round(c)) for c in pred["pixel_bbox"]]
        conf = pred.get("confidence", 0.0)
        matched = pred.get("matched", False)

        p_color = (0, 140, 255)
        p_label = f"MD: animal {int(round(conf * 100))}%" + (" (matched)" if matched else " (unmatched)")

        cv2.rectangle(canvas, (px1, py1), (px2, py2), p_color, 2, cv2.LINE_AA)
        cv2.putText(
            canvas, p_label, (px1, min(img_height - 10, py2 + 18)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.52, p_color, 2, cv2.LINE_AA
        )

    # Header summary bar
    header_text = f"{image_path.name} | GT: {len(gt_objects)} | Preds: {len(predictions)} | Best IoU: {best_iou:.2f}"
    cv2.rectangle(canvas, (0, 0), (img_width, 32), (18, 18, 18), -1)
    cv2.putText(
        canvas, header_text, (12, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA
    )

    cv2.imwrite(str(output_path), canvas)


def run_benchmark(
    dataset_dir: str = "data/validation/ntlnp_night",
    limit: Optional[int] = None,
    seed: int = 42,
    iou_threshold: float = 0.50,
    output_dir: str = "reports/phase1_ntlnp"
) -> Dict[str, Any]:
    """
    Executes the NTLNP Phase 1 benchmark and writes summary JSON, CSVs, and preview images.
    """
    dataset_path = Path(dataset_dir)
    images_dir = dataset_path / "JPEGImages"
    annotations_dir = dataset_path / "Annotations"
    out_path = Path(output_dir)
    missed_dir = out_path / "missed"

    if not images_dir.exists():
        raise FileNotFoundError(f"JPEGImages directory not found: {images_dir}")
    if not annotations_dir.exists():
        raise FileNotFoundError(f"Annotations directory not found: {annotations_dir}")

    out_path.mkdir(parents=True, exist_ok=True)
    missed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Discover all matching pairs (image and XML matching by filename stem)
    all_images = {p.stem: p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png"]}
    all_xmls = {p.stem: p for p in annotations_dir.iterdir() if p.is_file() and p.suffix.lower() == ".xml"}

    common_stems = sorted(list(set(all_images.keys()) & set(all_xmls.keys())))
    logger.info("Found %d paired image-annotation files in %s", len(common_stems), dataset_dir)

    if not common_stems:
        raise ValueError(f"No valid image-annotation pairs found in {dataset_dir}")

    # 2. Deterministic sampling if limit is specified
    if limit is not None and limit < len(common_stems):
        rng = random.Random(seed)
        selected_stems = sorted(rng.sample(common_stems, limit))
        logger.info("Sampled %d images deterministically using seed=%d", limit, seed)
    else:
        selected_stems = common_stems
        logger.info("Evaluating all %d images", len(selected_stems))

    # 3. Initialize detector (singleton)
    logger.info("Loading WildlifeDetector singleton...")
    detector = get_detector()

    # 4. Evaluation loop
    results_records: List[Dict[str, Any]] = []
    species_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "images": 0,
        "ground_truth_objects": 0,
        "detected_objects": 0,
        "missed_objects": 0,
        "matched_confidences": [],
        "best_ious": []
    })

    total_gt_animals = 0
    total_detected_animals = 0
    total_missed_animals = 0
    total_animal_predictions = 0
    total_unmatched_predictions = 0
    all_matched_confidences: List[float] = []
    all_best_ious: List[float] = []
    images_with_gt_count = 0
    images_with_detection_count = 0
    saved_missed_count = 0

    t_start = time.time()

    for idx, stem in enumerate(selected_stems, 1):
        img_path = all_images[stem]
        xml_path = all_xmls[stem]

        # Parse XML
        parsed_xml = parse_pascal_voc(xml_path)
        if parsed_xml is None:
            logger.warning("Skipping stem %s due to XML parsing error", stem)
            continue

        # Load image with OpenCV
        frame = cv2.imread(str(img_path))
        if frame is None:
            logger.warning("Skipping corrupt or unreadable image: %s", img_path)
            continue

        real_h, real_w = frame.shape[:2]
        img_w = parsed_xml["width"] if parsed_xml["width"] > 0 else real_w
        img_h = parsed_xml["height"] if parsed_xml["height"] > 0 else real_h

        gt_objects = parsed_xml["objects"]

        # Run MegaDetector V6 with Phase 1 class-specific thresholds
        raw_detections = detector.detect(frame)
        # Filter for 'animal' predictions
        animal_preds = [d for d in raw_detections if d.get("class") == "animal"]

        # Match predictions against ground truth
        match_info = match_gt_and_predictions(
            gt_objects=gt_objects,
            predictions=animal_preds,
            img_width=img_w,
            img_height=img_h,
            iou_threshold=iou_threshold
        )

        gt_count = len(gt_objects)
        pred_count = match_info["prediction_count"]
        matched_count = match_info["matched_count"]
        missed_count = match_info["missed_count"]
        unmatched_count = len(match_info["unmatched_predictions"])
        detected_flag = match_info["detected"]

        total_gt_animals += gt_count
        total_detected_animals += matched_count
        total_missed_animals += missed_count
        total_animal_predictions += pred_count
        total_unmatched_predictions += unmatched_count

        if gt_count > 0:
            images_with_gt_count += 1
            if detected_flag:
                images_with_detection_count += 1

        # Track per-species statistics
        species_in_image: Set[str] = set()
        for gt in match_info["gt_matches"]:
            sp = gt["species"]
            species_in_image.add(sp)
            species_stats[sp]["ground_truth_objects"] += 1
            species_stats[sp]["best_ious"].append(gt["best_iou"])
            all_best_ious.append(gt["best_iou"])

            if gt["matched"]:
                species_stats[sp]["detected_objects"] += 1
                species_stats[sp]["matched_confidences"].append(gt["matched_confidence"])
                all_matched_confidences.append(gt["matched_confidence"])
            else:
                species_stats[sp]["missed_objects"] += 1

        for sp in species_in_image:
            species_stats[sp]["images"] += 1

        species_str = ", ".join(sorted(list(species_in_image))) if species_in_image else "None"

        # Record per-image result
        results_records.append({
            "image": img_path.name,
            "species": species_str,
            "ground_truth_count": gt_count,
            "prediction_count": pred_count,
            "matched_count": matched_count,
            "missed_count": missed_count,
            "best_iou": round(match_info["best_image_iou"], 4),
            "max_confidence": round(match_info["max_confidence"], 4),
            "detected": detected_flag
        })

        # Save visual failure previews (up to 25 images)
        if missed_count > 0 and saved_missed_count < 25:
            missed_preview_path = missed_dir / f"{stem}_missed.jpg"
            draw_missed_visual(
                image_path=img_path,
                gt_objects=match_info["gt_matches"],
                predictions=match_info["predictions"],
                img_width=img_w,
                img_height=img_h,
                output_path=missed_preview_path,
                best_iou=match_info["best_image_iou"]
            )
            saved_missed_count += 1

        if idx % 20 == 0 or idx == len(selected_stems):
            logger.info("Processed %d/%d images...", idx, len(selected_stems))

    elapsed_time = time.time() - t_start
    total_evaluated = len(results_records)

    # 5. Aggregate metrics
    object_recall = (total_detected_animals / total_gt_animals) if total_gt_animals > 0 else 0.0
    image_detection_rate = (images_with_detection_count / images_with_gt_count) if images_with_gt_count > 0 else 0.0
    mean_matched_conf = float(np.mean(all_matched_confidences)) if all_matched_confidences else 0.0
    mean_best_iou = float(np.mean(all_best_ious)) if all_best_ious else 0.0

    # Per-species summary calculation
    per_species_dict = {}
    per_species_rows = []
    for sp in sorted(species_stats.keys()):
        data = species_stats[sp]
        gt_cnt = data["ground_truth_objects"]
        det_cnt = data["detected_objects"]
        mis_cnt = data["missed_objects"]
        rec = (det_cnt / gt_cnt) if gt_cnt > 0 else 0.0
        m_conf = float(np.mean(data["matched_confidences"])) if data["matched_confidences"] else 0.0
        m_iou = float(np.mean(data["best_ious"])) if data["best_ious"] else 0.0

        per_species_dict[sp] = {
            "images": data["images"],
            "ground_truth_objects": gt_cnt,
            "detected_objects": det_cnt,
            "missed_objects": mis_cnt,
            "recall": round(rec, 4),
            "mean_matched_confidence": round(m_conf, 4),
            "mean_best_iou": round(m_iou, 4)
        }

        per_species_rows.append({
            "species": sp,
            "images": data["images"],
            "ground_truth_objects": gt_cnt,
            "detected_objects": det_cnt,
            "missed_objects": mis_cnt,
            "recall": round(rec, 4),
            "mean_matched_confidence": round(m_conf, 4),
            "mean_best_iou": round(m_iou, 4)
        })

    summary_data = {
        "dataset": str(dataset_dir),
        "iou_threshold": iou_threshold,
        "limit": limit,
        "seed": seed,
        "images_evaluated": total_evaluated,
        "ground_truth_animals": total_gt_animals,
        "total_animal_predictions": total_animal_predictions,
        "detected_animals": total_detected_animals,
        "missed_animals": total_missed_animals,
        "object_recall": round(object_recall, 4),
        "images_with_ground_truth": images_with_gt_count,
        "images_with_detection": images_with_detection_count,
        "image_detection_rate": round(image_detection_rate, 4),
        "unmatched_predictions": total_unmatched_predictions,
        "mean_matched_confidence": round(mean_matched_conf, 4),
        "mean_best_iou": round(mean_best_iou, 4),
        "evaluation_time_seconds": round(elapsed_time, 2),
        "per_species": per_species_dict
    }

    # 6. Save reports/phase1_ntlnp/summary.json
    summary_file = out_path / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    logger.info("Saved summary report to %s", summary_file)

    # 7. Save reports/phase1_ntlnp/results.csv
    results_file = out_path / "results.csv"
    with open(results_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image", "species", "ground_truth_count", "prediction_count",
            "matched_count", "missed_count", "best_iou", "max_confidence", "detected"
        ])
        writer.writeheader()
        writer.writerows(results_records)
    logger.info("Saved per-image results to %s", results_file)

    # 8. Save reports/phase1_ntlnp/per_species.csv
    species_file = out_path / "per_species.csv"
    with open(species_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "species", "images", "ground_truth_objects", "detected_objects",
            "missed_objects", "recall", "mean_matched_confidence", "mean_best_iou"
        ])
        writer.writeheader()
        writer.writerows(per_species_rows)
    logger.info("Saved per-species breakdown to %s", species_file)

    # 9. Print clean terminal summary (Requirement 10)
    print("\n" + "=" * 80)
    print("NTLNP Phase 1 Benchmark Summary")
    print("-" * 80)
    print(f"Images evaluated:           {total_evaluated}")
    print(f"Ground-truth animals:       {total_gt_animals}")
    print(f"Total animal detections:    {total_animal_predictions}")
    print(f"Detected:                   {total_detected_animals}")
    print(f"Missed:                     {total_missed_animals}")
    print(f"Object recall:              {object_recall * 100:.2f}%")
    print(f"Image detection rate:       {image_detection_rate * 100:.2f}%")
    print(f"Mean matched confidence:    {mean_matched_conf:.4f}")
    print(f"Mean best IoU:              {mean_best_iou:.4f}")
    print(f"Unmatched predictions:      {total_unmatched_predictions}")
    print(f"Missed previews saved:      {saved_missed_count} (in {missed_dir})")
    print(f"Evaluation duration:        {elapsed_time:.1f}s")
    print("-" * 80)
    print("Per-Species Evaluation Breakdown:")
    print("-" * 80)
    print(f"{'Species':<16} {'Images':>6} {'GT Objs':>8} {'Detected':>9} {'Missed':>7} {'Recall':>9} {'Mean Conf':>10} {'Mean IoU':>9}")
    print("-" * 80)
    for row in per_species_rows:
        rec_str = f"{row['recall'] * 100:.1f}%"
        conf_str = f"{row['mean_matched_confidence']:.3f}"
        iou_str = f"{row['mean_best_iou']:.3f}"
        print(f"{row['species']:<16} {row['images']:>6} {row['ground_truth_objects']:>8} {row['detected_objects']:>9} {row['missed_objects']:>7} {rec_str:>9} {conf_str:>10} {iou_str:>9}")
    print("=" * 80 + "\n")

    return summary_data


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 1 - NTLNP Night Camera-Trap Benchmark"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/validation/ntlnp_night",
        help="Path to NTLNP dataset directory containing JPEGImages and Annotations"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of images to evaluate (omitted = evaluate entire dataset)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic image sampling (default: 42)"
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.50,
        help="IoU threshold for positive ground-truth match (default: 0.50)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/phase1_ntlnp",
        help="Output directory for reports and preview images (default: reports/phase1_ntlnp)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    try:
        run_benchmark(
            dataset_dir=args.dataset,
            limit=args.limit,
            seed=args.seed,
            iou_threshold=args.iou_threshold,
            output_dir=args.output
        )
    except Exception as exc:
        logger.error("Benchmark failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
