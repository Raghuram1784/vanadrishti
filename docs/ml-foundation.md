# ML frame foundation

## Architecture and compatibility

`ml.pipeline.analyze_frame(frame, camera_id, metadata=None)` is the shared entry
point for decoded uint8 H x W x 3 BGR arrays. Capture and source transport stay
outside ML. `FrameAnalyzer` owns serialized lazy model access. The old
`backend.services.vision_service.VisionService` subclasses it and retains
`analyze(frame)` and its list-of-dicts output. Existing detector APIs are unchanged.

Both `/api/analyze-image` and `/api/cameras/{camera_id}/frame` use the shared entry
point and expose its result as additive `frame_analysis`. Their existing event,
risk, evidence, session and detection fields remain. Existing injected services
with only `analyze(frame)` are supported via the entry point's `inference` argument.
`CameraSessionService` still owns continuity, weak-frame temporal confirmation and
deduplication. No temporal state, alerts or maintenance workflow was added to ML.

## Contract

`FrameAnalysisResult` contains camera_id, captured_at, processing_ms, status,
detections, image_quality and warnings. `metadata['captured_at']` accepts an ISO
string or datetime; omit for current UTC. Naive times are interpreted as UTC;
HTTP callers first apply the existing India-local timestamp policy. Supply valid
metadata; timestamp parse errors are caller errors. processing_ms includes quality,
model loading when necessary, lock wait, inference and schema validation.

Detection models were moved from backend/schemas/api.py into ml/pipeline/models.py
and re-exported at the old location. Existing names are preserved: `type`, `score`,
normalized xyxy `bbox`, `uncertain`, `uncertainty_reason`, `candidate_signals`,
`species`. Species contains `top1`, `ranking_score`, and `top3` candidates.
These are rankings, not calibrated probabilities.

Frame statuses are enums:
- CONFIRMED_DETECTION: at least one frame-level non-uncertain detection.
- UNCERTAIN_DETECTION: detections exist, but all are uncertain.
- NO_DETECTION: no retained detections on a GOOD frame.
- DEGRADED_FRAME: no retained detections on a DEGRADED or UNUSABLE frame.
- INVALID_FRAME: invalid dtype, shape, empty array or non-array; no inference.
- INFERENCE_ERROR: inference or result validation failed; never treated as absence.

A detection takes precedence over quality in the frame status; image_quality and
warnings remain visible. Quality does not suppress detections. This conservative
policy preserves evidence and existing behavior. In HTTP APIs, model errors retain
the prior 503 response, and invalid uploads retain prior 4xx responses.

The nested frame result describes the raw ML observation. Top-level live detections
may subsequently acquire temporal uncertainty. Its status is deliberately separate
from event_state (NEW/CONTINUATION/etc.) and from camera-session ONLINE/OFFLINE.

## Image quality

`QualityConfig` centralizes validated, immutable, configurable thresholds. Supply
`quality_config=QualityConfig(...)` to analyze_frame or FrameAnalyzer.analyze_frame.
The default HTTP integration uses these same defaults. Metrics use grayscale after
aspect-preserving reduction to at most 640 pixels on the long edge:

| Metric | Default flag rule |
|---|---|
| Mean brightness | TOO_DARK below 25; OVEREXPOSED above 235 (0..255) |
| Standard deviation | LOW_CONTRAST below 12 |
| Variance of Laplacian | BLURRED below 35 |
| Near-black fraction | pixels <=10 |
| Near-white fraction | pixels >=245 |
| Extreme fraction | UNUSABLE when either fraction >=0.98 |
| Low contrast plus low sharpness | POSSIBLE_OBSTRUCTION |

Other flagged frames are DEGRADED; otherwise GOOD. Reasons describe appearance
only. Night scenes, plain walls, smooth backgrounds, noise, compression, resolution,
and infrared illumination can affect these heuristics. Thresholds need validation
on representative field data; these are initial engineering defaults. A single
frame does not establish obstruction, its physical cause, camera failure, or a
maintenance incident. No persistent-condition claim is inferred from one image.

## Detection and color policy

Detector thresholds remain animal 0.20, person 0.25, vehicle 0.50. The legacy global
minimum still combines with class thresholds using max. The service requests low
candidates at 0.05 for its existing animal/person ambiguity checks; these are not
retained observations unless they meet the class policy.

Animal observations below the species gate remain uncertain with null species.
The default gate is 0.35; existing SPECIES_CLASSIFICATION_MIN_DETECTOR_SCORE and
constructor override remain supported. Competing person/animal signals also block
species ranking. People and vehicles never invoke BioCLIP.

MegaDetector receives the original BGR NumPy array; PyTorch-Wildlife forwards it
to Ultralytics, which handles conversion internally. BioCLIP separately converts
BGR crops to PIL RGB at validate_and_preprocess_crop. The shared contract never
swaps channels. Tests assert both boundaries using a color-asymmetric fixture.

## Validation

From the repository root, using the installed system Python (the local .venv
currently lacks pytest):

```powershell
python -m pytest -q
python -m pytest tests/test_frame_analysis.py tests/test_uncertainty.py -q
npm --prefix frontend run build
python scripts/reconcile_detector_benchmark.py
```

See baseline-before-ml-foundation.md for the unchanged baseline results and
benchmark-reconciliation.md for measured results and limits. No frontend redesign
or future camera/notification/transport feature is included.

Final validation (2026-10-16): `python -m pytest -q` passed 131 tests and
4 subtests, with the same 5 deprecation warnings (78.07 seconds). The 24 new
focused tests also passed independently. `npm run build` passed (30.06 seconds)
with the existing bundle-size warning. No pre-existing test failures were found.
`git diff --check` passed. Timing variation in the test/build runs is not a
measurement of production inference performance.

## Final acceptance review of 02b121c

The review found a presentation gap: the live API retained nested quality data,
but the live panel ignored it and showed "Sample clear" for empty detections.
The empty-result LOW/0 response also lacked a visibility qualification.

The compatibility-safe correction keeps event_state, risk scores/levels, alert
booleans, detections and persistence policy unchanged. DEGRADED/UNUSABLE samples
without confirmed detections now include explicit qualifications in the endpoint's
risk reasons/action: absence is not established and a usable image is needed.
LOW/0 is a legacy no-confirmed-detection result, never scene-clearance evidence.
The client shows quality reasons/warnings in the existing sample panel and risk
reasons, including when recent-activity risk overrides the latest sample's risk.
Missing quality on older responses receives an explicit unavailable message.
"Sample clear" has been removed even for GOOD frames: no detector proves absence.

Confirmed detections on poor-quality frames still use existing NEW/CONTINUATION
and contextual risk paths, with explicit frame quality retained. Uncertain/empty
poor frames create no incident, alert, or evidence. A covered gap neither clears
nor refreshes prior confirmed activity and does not cause duplicate incidents.
Recent activity still expires according to its existing time window.

No contextual risk engine, incident persistence, or temporal-state implementation
was changed. Quality persistence on historical incident records, camera-health
persistence, maintenance tickets, notification changes, C-21, offline transport,
and any risk-policy changes remain deferred. This review covers the live-frame
response and its current operator panel, not new historical incident schemas.

Acceptance checks: complete Python suite 141 passed plus 4 subtests (previously
131 plus 4); same 5 deprecation warnings. Ten new API tests cover black, nearly
black, white, low-detail, confident, uncertain, and continuity scenarios. All 14
frontend tests pass, including 4 actual live-panel render tests. Production build
passes with the existing large-bundle warning. No physical webcam trial was
performed; API and rendered component behavior were tested with controlled inputs.
