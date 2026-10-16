# Detector benchmark reconciliation

The local NTLNP dataset was available. The controlled CPU run used the historical
60-image sample (20 per group, seed 42), MDV6-yolov10-c, global threshold 0.20,
animal/person/vehicle thresholds 0.20/0.25/0.50, and IoU >=0.50. Sorted annotation
sampling, fixed seeds and deterministic PyTorch algorithms were used. All sample
identities were verified against the saved report before inference.

| Variant | Successful images |
|---|---|
| Saved post-fix report | 55/60 (91.67%) |
| Current BGR detector rerun | 55/60 (91.67%) |
| Diagnostic old extra BGR-to-RGB conversion | 56/60 (93.33%) |

WildBoar410.jpg is the sole success/failure difference between the color variants.
All 60 current BGR success/failure outcomes match the saved post-fix results.
The original 56/60 per-image report was not found, so the diagnostic reconstruction
explains the observed count difference but does not prove every historical setting.
The corrected color path remains in production. No zero-regression claim is made
relative to the old color path, and no threshold was tuned to this sample.

All 60 rows, image/annotation SHA-256 hashes, IoUs and per-variant outcomes are in
reports/ml_foundation/detector_comparison.csv. Package versions and configuration
are in reports/ml_foundation/summary.json. No raw images were added to Git.

Measured median quality assessment: 7.84 ms; median corrected detector call:
297.10 ms on this CPU run. These are observations from one run, not performance
promises. The detector first sample includes warmup. BioCLIP, HTTP and full pipeline
latency were not benchmarked; species accuracy was not rerun in this comparison.

Reproduce from the repository root:

```powershell
python scripts/reconcile_detector_benchmark.py --dataset data/validation/ntlnp_night --output reports/ml_foundation
```
