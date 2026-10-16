"""
VanaDrishti Phase 2B: End-to-End Animal Detection + Species Recognition Benchmark.

Evaluates the complete integrated pipeline:
Full Image -> MegaDetector V6 -> Predicted Animal Crop -> BioCLIP 2 -> Species Group Prediction.
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

from ml.detector import get_detector
from ml.species import get_species_classifier, normalize_to_target_group

logger = logging.getLogger("vanadrishti.end_to_end")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Compatible NTLNP class -> target evaluation group
COMPATIBLE_SPECIES_TO_GROUP = {
    "AmurTiger": "tiger",
    "Leopard": "leopard",
    "WildBoar": "wild_boar",
}


def calculate_iou(
    boxA: Tuple[float, float, float, float],
    boxB: Tuple[float, float, float, float],
) -> float:
    """Calculate IoU between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_width = max(0.0, xB - xA)
    inter_height = max(0.0, yB - yA)
    inter_area = inter_width * inter_height

    boxA_area = max(0.0, boxA[2] - boxA[0]) * max(0.0, boxA[3] - boxA[1])
    boxB_area = max(0.0, boxB[2] - boxB[0]) * max(0.0, boxB[3] - boxB[1])

    union_area = boxA_area + boxB_area - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def parse_voc_annotation(xml_path: Path) -> List[Dict[str, Any]]:
    """Parse Pascal VOC XML annotation."""
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
    """Collect deterministic evaluation samples for compatible target groups."""
    jpeg_dir = dataset_dir / "JPEGImages"
    ann_dir = dataset_dir / "Annotations"

    if not jpeg_dir.exists() or not ann_dir.exists():
        raise FileNotFoundError(
            f"Dataset invalid at {dataset_dir}. Missing JPEGImages or Annotations folder."
        )

    candidates_by_group: Dict[str, List[Dict[str, Any]]] = {
        group: [] for group in COMPATIBLE_SPECIES_TO_GROUP.values()
    }

    xml_files = sorted(ann_dir.glob("*.xml"))
    for xml_path in xml_files:
        stem = xml_path.stem
        img_path = jpeg_dir / f"{stem}.jpg"
        if not img_path.exists():
            img_path = jpeg_dir / f"{stem}.jpeg"
            if not img_path.exists():
                continue

        objects = parse_voc_annotation(xml_path)
        if not objects:
            continue

        for obj in objects:
            ntlnp_label = obj["species"]
            if ntlnp_label in COMPATIBLE_SPECIES_TO_GROUP:
                group = COMPATIBLE_SPECIES_TO_GROUP[ntlnp_label]
                candidates_by_group[group].append({
                    "image_path": img_path,
                    "xml_path": xml_path,
                    "ntlnp_species": ntlnp_label,
                    "target_group": group,
                    "gt_bbox": obj["bbox"],
                })
                break

    rng = random.Random(seed)
    selected_samples: List[Dict[str, Any]] = []
    for group, candidates in candidates_by_group.items():
        rng.shuffle(candidates)
        sampled = candidates[:limit_per_species]
        logger.info(
            "Sampled %d / %d available images for target group '%s'",
            len(sampled),
            len(candidates),
            group,
        )
        selected_samples.extend(sampled)

    return selected_samples


def extract_predicted_crop(
    image: np.ndarray,
    pred_pixel_bbox: Tuple[int, int, int, int],
) -> Optional[np.ndarray]:
    """Extract and validate crop using MegaDetector predicted pixel bounding box."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = pred_pixel_bbox
    x1_c = max(0, min(w - 1, x1))
    y1_c = max(0, min(h - 1, y1))
    x2_c = max(0, min(w, x2))
    y2_c = max(0, min(h, y2))

    if x2_c - x1_c < 5 or y2_c - y1_c < 5:
        return None

    crop = image[y1_c:y2_c, x1_c:x2_c]
    if crop.size == 0:
        return None
    return crop


def draw_failure_preview(
    image: np.ndarray,
    gt_bbox: Tuple[float, float, float, float],
    gt_group: str,
    pred_bbox: Optional[Tuple[int, int, int, int]],
    pred_species: Optional[str],
    pred_score: Optional[float],
    iou: float,
    failure_reason: str,
    output_path: Path,
) -> None:
    """Draw annotated failure preview image and save to disk."""
    vis = image.copy()
    h, w = vis.shape[:2]

    # Draw Ground Truth Box in Green
    gx1, gy1, gx2, gy2 = [round(c) for c in gt_bbox]
    cv2.rectangle(vis, (gx1, gy1), (gx2, gy2), (0, 255, 0), 3)
    cv2.putText(
        vis,
        f"GT: {gt_group}",
        (gx1, max(20, gy1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    # Draw MegaDetector Predicted Box in Red/Orange (if available)
    if pred_bbox is not None:
        px1, py1, px2, py2 = pred_bbox
        cv2.rectangle(vis, (px1, py1), (px2, py2), (0, 0, 255), 2)
        score_str = f"{pred_score:.2f}" if pred_score is not None else "N/A"
        sp_str = pred_species if pred_species else "Unknown"
        cv2.putText(
            vis,
            f"Pred: {sp_str} (IoU={iou:.2f}, score={score_str})",
            (px1, min(h - 10, py2 + 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    # Header Banner for Failure Reason
    banner_text = f"Failure: {failure_reason} | IoU: {iou:.2f}"
    cv2.rectangle(vis, (0, 0), (w, 36), (20, 20, 20), -1)
    cv2.putText(
        vis,
        banner_text,
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 165, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imwrite(str(output_path), vis)


def run_end_to_end_benchmark(
    dataset_dir: Path,
    output_dir: Path,
    limit_per_species: int = 20,
    seed: int = 42,
    iou_threshold: float = 0.50,
) -> Dict[str, Any]:
    """Execute complete Phase 2B End-to-End detection and species classification benchmark."""
    output_dir.mkdir(parents=True, exist_ok=True)
    failures_dir = output_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)

    samples = collect_compatible_samples(
        dataset_dir=dataset_dir,
        limit_per_species=limit_per_species,
        seed=seed,
    )
    total_images = len(samples)
    logger.info("Loaded %d compatible samples for end-to-end evaluation.", total_images)

    detector = get_detector()
    classifier = get_species_classifier()

    # Tracking metrics per target group
    group_stats: Dict[str, Dict[str, Any]] = {
        g: {
            "images": 0,
            "gt_animals": 0,
            "detected": 0,
            "missed": 0,
            "classified": 0,
            "top1_correct": 0,
            "top3_correct": 0,
            "e2e_top1_correct": 0,
            "e2e_top3_correct": 0,
            "matched_ious": [],
            "ranking_scores": [],
        }
        for g in ("tiger", "leopard", "wild_boar")
    }

    failure_counts: Dict[str, int] = {
        "success": 0,
        "species_top1_wrong": 0,
        "species_top3_miss": 0,
        "detector_iou_below_threshold": 0,
        "detector_miss": 0,
    }

    results_rows: List[Dict[str, Any]] = []
    saved_failure_previews = 0
    max_failure_previews = 25

    import time
    start_time = time.time()

    for idx, sample in enumerate(samples, 1):
        img_path: Path = sample["image_path"]
        ntlnp_label: str = sample["ntlnp_species"]
        gt_group: str = sample["target_group"]
        gt_box: Tuple[float, float, float, float] = sample["gt_bbox"]

        g_stat = group_stats[gt_group]
        g_stat["images"] += 1
        g_stat["gt_animals"] += 1

        img = cv2.imread(str(img_path))
        if img is None:
            logger.warning("Could not read image: %s", img_path.name)
            continue

        h, w = img.shape[:2]

        # 1. Run MegaDetector V6
        detections = detector.detect(img)

        # 2. Filter animal detections only
        animal_detections = []
        for d in detections:
            c = d.get("class") if isinstance(d, dict) else getattr(d, "class_name", None)
            if c == "animal":
                animal_detections.append(d)

        # 3. Match predictions to GT animal box
        best_iou = 0.0
        best_pred = None
        best_pred_pixel_bbox = None

        for det in animal_detections:
            bbox = det.get("bbox") if isinstance(det, dict) else getattr(det, "bbox", None)
            if not bbox:
                continue
            # Convert normalized bbox to pixel coordinates
            px1 = round(bbox[0] * w)
            py1 = round(bbox[1] * h)
            px2 = round(bbox[2] * w)
            py2 = round(bbox[3] * h)
            pred_pixel_box = (px1, py1, px2, py2)

            iou = calculate_iou(gt_box, (px1, py1, px2, py2))
            if iou > best_iou:
                best_iou = iou
                best_pred = det
                best_pred_pixel_bbox = pred_pixel_box

        is_detected = (best_iou >= iou_threshold) and (best_pred_pixel_bbox is not None)

        pred_species = None
        pred_group = None
        ranking_score = None
        top1_correct = False
        top3_correct = False
        e2e_top1_success = False
        e2e_top3_success = False
        failure_reason = "detector_miss"

        if is_detected:
            g_stat["detected"] += 1
            g_stat["matched_ious"].append(best_iou)

            # 4. Crop using the MegaDetector predicted box (NEVER GT box!)
            pred_crop = extract_predicted_crop(img, best_pred_pixel_bbox)
            if pred_crop is not None:
                try:
                    # 5. Send predicted crop to BioCLIP SpeciesClassifier
                    pred_res = classifier.classify_crop(pred_crop, top_k=5)
                    g_stat["classified"] += 1

                    pred_species = pred_res["species"]
                    ranking_score = pred_res["confidence"]
                    g_stat["ranking_scores"].append(ranking_score)

                    pred_group = normalize_to_target_group(pred_species)
                    top1_correct = (pred_group == gt_group)

                    # Top-3 evaluation
                    top3_groups = [
                        normalize_to_target_group(item["species"])
                        for item in pred_res.get("top_k", [])[:3]
                    ]
                    top3_correct = (gt_group in top3_groups)

                    if top1_correct:
                        g_stat["top1_correct"] += 1
                        g_stat["e2e_top1_correct"] += 1
                        e2e_top1_success = True

                    if top3_correct:
                        g_stat["top3_correct"] += 1
                        g_stat["e2e_top3_correct"] += 1
                        e2e_top3_success = True

                    # Determine failure category
                    if e2e_top1_success:
                        failure_reason = "success"
                    elif top3_correct:
                        failure_reason = "species_top1_wrong"
                    else:
                        failure_reason = "species_top3_miss"

                except Exception as err:
                    logger.warning("Classification exception for %s: %s", img_path.name, err)
                    failure_reason = "species_top3_miss"
            else:
                failure_reason = "detector_iou_below_threshold"
        else:
            g_stat["missed"] += 1
            if best_iou > 0.0:
                failure_reason = "detector_iou_below_threshold"
            else:
                failure_reason = "detector_miss"

        failure_counts[failure_reason] += 1

        # Save failure preview if not a success and under preview limit
        if failure_reason != "success" and saved_failure_previews < max_failure_previews:
            preview_filename = f"{img_path.stem}_{failure_reason}.jpg"
            preview_path = failures_dir / preview_filename
            draw_failure_preview(
                image=img,
                gt_bbox=gt_box,
                gt_group=gt_group,
                pred_bbox=best_pred_pixel_bbox,
                pred_species=pred_species,
                pred_score=ranking_score,
                iou=best_iou,
                failure_reason=failure_reason,
                output_path=preview_path,
            )
            saved_failure_previews += 1

        results_rows.append({
            "image": img_path.name,
            "ntlnp_species": ntlnp_label,
            "target_group": gt_group,
            "detected": is_detected,
            "best_iou": round(best_iou, 4),
            "pred_species": pred_species if pred_species else "None",
            "pred_group": pred_group if pred_group else "None",
            "ranking_score": round(ranking_score, 4) if ranking_score is not None else 0.0,
            "top1_correct": top1_correct,
            "top3_correct": top3_correct,
            "e2e_top1_success": e2e_top1_success,
            "e2e_top3_success": e2e_top3_success,
            "failure_reason": failure_reason,
        })

        if idx % 10 == 0 or idx == total_images:
            logger.info("Processed %d / %d end-to-end images...", idx, total_images)

    duration = time.time() - start_time

    # Aggregate global metrics
    total_gt = sum(s["gt_animals"] for s in group_stats.values())
    total_detected = sum(s["detected"] for s in group_stats.values())
    total_missed = sum(s["missed"] for s in group_stats.values())
    detector_recall = (total_detected / total_gt) if total_gt > 0 else 0.0
    all_ious = [iou for s in group_stats.values() for iou in s["matched_ious"]]
    mean_matched_iou = (sum(all_ious) / len(all_ious)) if all_ious else 0.0

    total_classified = sum(s["classified"] for s in group_stats.values())
    total_top1_correct = sum(s["top1_correct"] for s in group_stats.values())
    total_top3_correct = sum(s["top3_correct"] for s in group_stats.values())
    all_scores = [sc for s in group_stats.values() for sc in s["ranking_scores"]]

    top1_acc_on_detected = (total_top1_correct / total_classified) if total_classified > 0 else 0.0
    top3_acc_on_detected = (total_top3_correct / total_classified) if total_classified > 0 else 0.0
    mean_top1_score = (sum(all_scores) / len(all_scores)) if all_scores else 0.0

    total_e2e_top1 = sum(s["e2e_top1_correct"] for s in group_stats.values())
    total_e2e_top3 = sum(s["e2e_top3_correct"] for s in group_stats.values())
    e2e_top1_rate = (total_e2e_top1 / total_gt) if total_gt > 0 else 0.0
    e2e_top3_rate = (total_e2e_top3 / total_gt) if total_gt > 0 else 0.0

    # Per-group structured metrics
    per_group_summary: Dict[str, Dict[str, Any]] = {}
    for g, s in group_stats.items():
        gt_cnt = s["gt_animals"]
        det_cnt = s["detected"]
        cls_cnt = s["classified"]
        t1 = s["top1_correct"]
        t3 = s["top3_correct"]
        e1 = s["e2e_top1_correct"]
        e3 = s["e2e_top3_correct"]
        ious = s["matched_ious"]
        scores = s["ranking_scores"]

        per_group_summary[g] = {
            "images": s["images"],
            "gt_animals": gt_cnt,
            "detected": det_cnt,
            "detector_recall": round((det_cnt / gt_cnt) if gt_cnt > 0 else 0.0, 4),
            "classified": cls_cnt,
            "top1_correct": t1,
            "top1_classification_accuracy_on_detected": round((t1 / cls_cnt) if cls_cnt > 0 else 0.0, 4),
            "end_to_end_top1_success_rate": round((e1 / gt_cnt) if gt_cnt > 0 else 0.0, 4),
            "top3_correct": t3,
            "top3_classification_accuracy_on_detected": round((t3 / cls_cnt) if cls_cnt > 0 else 0.0, 4),
            "end_to_end_top3_success_rate": round((e3 / gt_cnt) if gt_cnt > 0 else 0.0, 4),
            "mean_ranking_score": round((sum(scores) / len(scores)) if scores else 0.0, 4),
            "mean_matched_iou": round((sum(ious) / len(ious)) if ious else 0.0, 4),
        }

    summary_data = {
        "dataset": str(dataset_dir),
        "iou_threshold": iou_threshold,
        "seed": seed,
        "limit_per_species": limit_per_species,
        "total_images": total_images,
        "duration_seconds": round(duration, 2),
        "detection_stage": {
            "total_images": total_images,
            "ground_truth_animals": total_gt,
            "animals_detected": total_detected,
            "animals_missed": total_missed,
            "detector_recall": round(detector_recall, 4),
            "mean_matched_iou": round(mean_matched_iou, 4),
        },
        "species_stage_on_detected": {
            "classified_animals": total_classified,
            "top1_correct": total_top1_correct,
            "top1_accuracy": round(top1_acc_on_detected, 4),
            "top3_correct": total_top3_correct,
            "top3_accuracy": round(top3_acc_on_detected, 4),
            "mean_top1_ranking_score": round(mean_top1_score, 4),
        },
        "end_to_end": {
            "ground_truth_animals": total_gt,
            "e2e_top1_correct": total_e2e_top1,
            "e2e_top1_success_rate": round(e2e_top1_rate, 4),
            "e2e_top3_correct": total_e2e_top3,
            "e2e_top3_success_rate": round(e2e_top3_rate, 4),
        },
        "failure_breakdown": failure_counts,
        "per_target_group": per_group_summary,
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
    logger.info("Saved per-image results to %s", results_path)

    # Save per_species.csv
    per_species_path = output_dir / "per_species.csv"
    with open(per_species_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "target_group",
            "images",
            "gt_animals",
            "detected",
            "detector_recall",
            "classified",
            "top1_correct",
            "top1_acc_on_detected",
            "e2e_top1_success_rate",
            "top3_acc_on_detected",
            "e2e_top3_success_rate",
            "mean_ranking_score",
            "mean_matched_iou",
        ])
        for g, d in per_group_summary.items():
            writer.writerow([
                g,
                d["images"],
                d["gt_animals"],
                d["detected"],
                d["detector_recall"],
                d["classified"],
                d["top1_correct"],
                d["top1_classification_accuracy_on_detected"],
                d["end_to_end_top1_success_rate"],
                d["top3_classification_accuracy_on_detected"],
                d["end_to_end_top3_success_rate"],
                d["mean_ranking_score"],
                d["mean_matched_iou"],
            ])
    logger.info("Saved per_species breakdown to %s", per_species_path)

    # Terminal summary table
    print("\n" + "=" * 78)
    print("VanaDrishti Phase 2B: End-to-End Wildlife Detection + Species Recognition")
    print("-" * 78)
    print(f"Total Images Evaluated:          {total_images}")
    print(f"Ground-Truth Animals:            {total_gt}")
    print(f"Detection Stage Recall:          {detector_recall * 100:.2f}% ({total_detected}/{total_gt})")
    print(f"Mean Matched IoU:                {mean_matched_iou:.4f}")
    print("-" * 78)
    print(f"Species Classified on Detected:  {total_classified}")
    print(f"Top-1 Accuracy on Detected:      {top1_acc_on_detected * 100:.2f}% ({total_top1_correct}/{total_classified})")
    print(f"Top-3 Accuracy on Detected:      {top3_acc_on_detected * 100:.2f}% ({total_top3_correct}/{total_classified})")
    print(f"Mean Ranking Score on Detected:  {mean_top1_score:.4f}")
    print("-" * 78)
    print(f"TRUE END-TO-END TOP-1 SUCCESS:   {e2e_top1_rate * 100:.2f}% ({total_e2e_top1}/{total_gt})")
    print(f"TRUE END-TO-END TOP-3 SUCCESS:   {e2e_top3_rate * 100:.2f}% ({total_e2e_top3}/{total_gt})")
    print("-" * 78)
    print("Failure Breakdown:")
    for k, v in failure_counts.items():
        print(f"  {k:<32}: {v}")
    print("-" * 78)
    print("Per Target Group Breakdown:")
    print(f"{'Group':<12} {'GT':<4} {'Det':<4} {'Det Rec':<10} {'Cls':<4} {'Top1 Det':<10} {'E2E Top1':<10} {'E2E Top3':<10} {'Score':<8} {'IoU':<8}")
    print("-" * 78)
    for g, d in per_group_summary.items():
        print(
            f"{g:<12} "
            f"{d['gt_animals']:<4} "
            f"{d['detected']:<4} "
            f"{d['detector_recall'] * 100:>6.1f}%    "
            f"{d['classified']:<4} "
            f"{d['top1_classification_accuracy_on_detected'] * 100:>6.1f}%    "
            f"{d['end_to_end_top1_success_rate'] * 100:>6.1f}%    "
            f"{d['end_to_end_top3_success_rate'] * 100:>6.1f}%    "
            f"{d['mean_ranking_score']:>6.3f}  "
            f"{d['mean_matched_iou']:>6.3f}"
        )
    print("=" * 78 + "\n")

    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 2B End-to-End Evaluation on NTLNP Dataset"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/validation/ntlnp_night",
        help="Path to NTLNP dataset root",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/phase2_end_to_end",
        help="Output directory for reports and failure previews",
    )
    parser.add_argument(
        "--limit-per-species",
        type=int,
        default=20,
        help="Max images per compatible group (default: 20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.50,
        help="IoU threshold for valid animal detection matching (default: 0.50)",
    )

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    run_end_to_end_benchmark(
        dataset_dir=dataset_path,
        output_dir=output_path,
        limit_per_species=args.limit_per_species,
        seed=args.seed,
        iou_threshold=args.iou_threshold,
    )


if __name__ == "__main__":
    main()
