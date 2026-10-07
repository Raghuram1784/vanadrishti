# VanaDrishti — Phase 1: MegaDetector V6 Wildlife Surveillance Engine

This directory contains the core detection subsystem for **VanaDrishti**, an AI-powered surveillance and ranger decision-support system designed for protected forest environments such as **Tadoba-Andhari Tiger Reserve (TATR)**.

Phase 1 focuses on real-time and prerecorded detection of three primary classes:
- **`animal`**: Wildlife species (e.g., tigers, leopards, deer, elephants, gaurs)
- **`person`**: Humans (rangers, tourists, or potential unauthorized poachers/trespassers)
- **`vehicle`**: Safari jeeps, ranger patrol motorcycles, trucks, or unauthorized vehicles

---

## Architecture & Technology

- **Detector Model**: [Microsoft MegaDetector V6](https://github.com/microsoft/Pytorch-Wildlife) (`MDV6-yolov10-c`)
- **Framework**: `PytorchWildlife` + PyTorch + OpenCV
- **Compute Optimization**: Automatic hardware acceleration detection (`CUDA` when available, fallback to CPU)
- **Memory Footprint**: Thread-safe singleton pattern ensures model weights load into memory **only once**
- **Decoupled Design**: Pure ML inference logic in `detector.py` is strictly separated from visual rendering (`visualization.py`), making it ready for direct integration into the FastAPI backend (Phase 4).

---

## Output Data Format

The detector accepts standard OpenCV frames (BGR format) and returns standardized, normalized detection objects:

```json
[
  {
    "class": "animal",
    "confidence": 0.94,
    "bbox": [0.3214, 0.2150, 0.7641, 0.8420]
  },
  {
    "class": "person",
    "confidence": 0.91,
    "bbox": [0.1250, 0.3400, 0.3120, 0.9250]
  }
]
```

- `class`: One of `"animal"`, `"person"`, or `"vehicle"`.
- `confidence`: Confidence score between `0.0` and `1.0`.
- `bbox`: Normalized coordinates `[x1, y1, x2, y2]` where:
  - `x1`: Left relative coordinate (`0.0` to `1.0`)
  - `y1`: Top relative coordinate (`0.0` to `1.0`)
  - `x2`: Right relative coordinate (`0.0` to `1.0`)
  - `y2`: Bottom relative coordinate (`0.0` to `1.0`)

---

## File Structure

```
ml/detector/
├── __init__.py           # Package exports & public API
├── detector.py           # Core WildlifeDetector singleton & inference
├── visualization.py      # Tactical bounding boxes, HUD status bar, & overlays
├── webcam.py             # Live camera stream detection script
├── video.py              # Prerecorded footage analysis & export script
└── README.md             # Subsystem documentation
```

---

## How to Run

### 1. Live Webcam Surveillance
Run continuous detection from your laptop or connected field webcam:

```bash
# Run default webcam with standard confidence threshold (0.25)
python -m ml.detector.webcam

# Optional flags:
# Use specific camera ID, confidence threshold, or headless mode
python -m ml.detector.webcam --camera-id 0 --conf-threshold 0.30
```
- Controls: Press **`Q`** or **`ESC`** in the video window to stop.

### 2. Prerecorded Video Footage Analysis
Process camera-trap video, drone patrol footage, or gate CCTV clips:

```bash
# Display detections in real-time preserving original FPS
python -m ml.detector.video --input data/demo/patrol_sample.mp4

# Save annotated footage to output file
python -m ml.detector.video --input data/demo/patrol_sample.mp4 --output data/demo/annotated.mp4

# Run offline batch processing without GUI display
python -m ml.detector.video --input data/demo/patrol_sample.mp4 --output data/demo/annotated.mp4 --no-display
```
- Controls: Press **`Q`** in the window to stop early.

---

## Programmatic API (for FastAPI / Python Modules)

```python
import cv2
from ml.detector import get_detector, detect_frame, denormalize_bbox

# 1. Using the singleton detector instance
detector = get_detector(conf_threshold=0.25)

frame = cv2.imread("sample_forest.jpg")
detections = detector.detect(frame)

for det in detections:
    print(f"Detected {det['class']} with {det['confidence']*100:.1f}% confidence")
    # Convert normalized box to pixel coordinates
    x1, y1, x2, y2 = denormalize_bbox(det['bbox'], width=frame.shape[1], height=frame.shape[0])

# 2. Or using the one-line convenience function
detections = detect_frame(frame, conf_threshold=0.25)
```
