"""Reproduce the 60-image detector comparison without changing inference policy.

The legacy RGB variant is diagnostic only; never use it in production.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
import torch
from ml.detector.detector import get_detector, CLASS_THRESHOLDS
from ml.pipeline.quality import assess_quality
from scripts.test_end_to_end_ntlnp import collect_compatible_samples, calculate_iou


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'data/validation/ntlnp_night')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/ml_foundation')
    args = parser.parse_args()
    torch.manual_seed(42)
    np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    samples = collect_compatible_samples(args.dataset, limit_per_species=20, seed=42)
    if len(samples) != 60:
        raise RuntimeError(f'Expected 60 samples, found {len(samples)}')
    historical_path = ROOT / 'reports/phase2_end_to_end/results.csv'
    historical = {r['image']: r for r in csv.DictReader(historical_path.open())}
    if set(historical) != {s['image_path'].name for s in samples}:
        raise RuntimeError('Sample identities differ from saved historical results')
    detector = get_detector(device='cpu')
    rows, quality_ms, inference_ms = [], [], []
    for sample in samples:
        path = sample['image_path']
        frame = cv2.imread(str(path))
        if frame is None:
            raise RuntimeError(f'Unreadable sample: {path.name}')
        h, w = frame.shape[:2]
        started = perf_counter()
        quality = assess_quality(frame)
        quality_ms.append((perf_counter() - started) * 1000)
        row = {'image': path.name, 'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'annotation_sha256': hashlib.sha256(sample['xml_path'].read_bytes()).hexdigest(),
               'historical_detected': historical[path.name]['detected'] == 'True',
               'historical_iou': float(historical[path.name]['best_iou']),
               'quality_status': quality.status.value}
        for name, pixels in [('bgr', frame), ('legacy_rgb', cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))]:
            started = perf_counter()
            detections = detector.detect(pixels)
            elapsed = (perf_counter() - started) * 1000
            if name == 'bgr':
                inference_ms.append(elapsed)
            best = max((calculate_iou(sample['gt_bbox'], tuple(round(x * size) for x, size in zip(d['bbox'], [w,h,w,h])))
                        for d in detections if d['class'] == 'animal'), default=0.)
            row[name + '_iou'] = round(best, 6)
            row[name + '_detected'] = best >= .5
        rows.append(row)
        print(f"{len(rows):02}/60 {path.name}: BGR={row['bgr_detected']} legacy={row['legacy_rgb_detected']}", flush=True)
    summary = {
        'model': detector.model_version, 'device': 'cpu', 'seed': 42, 'torch_threads': 1,
        'deterministic_algorithms': True, 'iou_threshold': .5,
        'global_threshold': detector.default_conf_threshold, 'class_thresholds': CLASS_THRESHOLDS,
        'count': len(rows), 'historical_successes': sum(r['historical_detected'] for r in rows),
        'bgr_successes': sum(r['bgr_detected'] for r in rows),
        'legacy_rgb_successes': sum(r['legacy_rgb_detected'] for r in rows),
        'color_differences': [r['image'] for r in rows if r['bgr_detected'] != r['legacy_rgb_detected']],
        'historical_differences': [r['image'] for r in rows if r['bgr_detected'] != r['historical_detected']],
        'python': platform.python_version(),
        'packages': {p: importlib.metadata.version(p) for p in ['torch','ultralytics','PytorchWildlife','opencv-python']},
        'quality_ms_median': statistics.median(quality_ms),
        'detector_ms_median': statistics.median(inference_ms),
        'latency_scope': 'CPU detector only, first sample includes warmup; quality uses <=640px long edge. No BioCLIP or HTTP timing.',
        'historical_56_run': 'Original per-image 56/60 report not found; legacy conversion is a controlled reconstruction, not historical proof.'
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'detector_comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
