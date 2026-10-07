# VanaDrishti (वनदृष्टि) 🐅🌲

> **AI-Powered Wildlife Surveillance & Ranger Decision-Support System**  
> Tailored for Protected Forest Environments such as **Tadoba-Andhari Tiger Reserve (TATR)**.

---

## Overview

**VanaDrishti** (*Sanskrit: Vision of the Forest*) is a mission-critical AI-driven surveillance and decision-support platform designed to assist forest rangers and wildlife conservationists. Protected ecosystems such as the Tadoba-Andhari Tiger Reserve face escalating challenges including human-wildlife conflict, poaching threats, and illegal vehicular intrusions along sensitive buffer corridors.

VanaDrishti combines edge camera-trap feeds, drone footage, and guard checkpoint streams to detect, identify, and assess risk in real-time.

---

## Current Status: Phase 1 — Detection Engine 🎯

We are developing VanaDrishti strictly **phase-by-phase**. Currently, **Phase 0 (Project Structure)** and **Phase 1 (Person / Vehicle / Animal Detection)** are fully set up and functional.

- [x] **Phase 0 — Repository Setup & Project Structure**
- [x] **Phase 1 — Core Person / Vehicle / Animal Detection (MegaDetector V6)**
- [ ] Phase 2 — Species Recognition (BioCLIP / Specialized Classifiers)
- [ ] Phase 3 — Spatiotemporal Context & Risk Assessment Engine
- [ ] Phase 4 — High-Performance FastAPI Backend
- [ ] Phase 5 — Ranger Operations Command Dashboard (React / Tailwind)
- [ ] Phase 6 — Multi-Camera Correlation & Movement Trajectory Tracking
- [ ] Phase 7 — End-to-End Field Demonstration & Hardening

---

## Technology Stack (Phase 1)

- **Language**: Python 3.12+ (tested & supported on Python 3.12 – 3.14)
- **Wildlife Detection Model**: [Microsoft MegaDetector V6](https://github.com/microsoft/Pytorch-Wildlife) (`MDV6-yolov10-c`) via `PytorchWildlife`
- **Inference Backends**: PyTorch & Ultralytics
- **Acceleration**: Automatic CUDA GPU acceleration if available; CPU fallback with multi-threaded optimizations
- **Computer Vision**: OpenCV (`cv2`) for frame capture, stream decoding, video rendering, and HUD overlays

---

## Repository Structure

```
vanadrishti/
├── backend/
│   └── app/                  # FastAPI application (Phase 4)
├── frontend/                 # React Command Dashboard (Phase 5)
├── ml/
│   ├── detector/             # Phase 1: MegaDetector V6 Subsystem
│   │   ├── __init__.py       # Package exports & public API
│   │   ├── detector.py       # Core WildlifeDetector singleton & inference
│   │   ├── visualization.py  # Tactical HUD and bounding box rendering
│   │   ├── webcam.py         # Live webcam surveillance stream runner
│   │   ├── video.py          # Prerecorded video analysis & export runner
│   │   └── README.md         # Subsystem documentation
│   ├── species/              # Phase 2: Species Recognition models
│   └── pipeline/             # Full ML processing pipeline
├── config/
│   ├── cameras.json          # TATR camera network layout and endpoints
│   ├── patrols.json          # Anti-poaching squad patrols and routes
│   └── zones.geojson         # Core & Buffer zone geospatial boundaries
├── data/
│   ├── demo/                 # Demonstration media (git-ignored)
│   └── samples/              # Test sample clips (git-ignored)
├── tests/
│   └── test_detector.py      # Unit & integration tests for detection
├── scripts/                  # Automation & setup utilities
├── docs/                     # Architectural documentation & reserve specs
├── .gitignore                # Git ignore rules
├── requirements.txt          # Python dependencies
└── README.md                 # Project README
```

---

## Installation & Setup

### 1. Prerequisites
- **Python**: Version 3.12 or 3.13/3.14 (64-bit)
- **Git**

### 2. Clone Repository
```bash
git clone https://github.com/Raghuram1784/vanadrishti.git
cd vanadrishti
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

> **Note**: On initial run, model weights for Microsoft MegaDetector V6 (`MDV6-yolov10-c`) will automatically download from HuggingFace to your local cache (`~/.cache/huggingface` or `AppData`). Subsequent runs will use the cached weights instantly.

---

## Usage Guide

### 1. Live Webcam Detection
Run continuous surveillance on your default laptop webcam or connected USB field camera:

```bash
# Run with default settings
python -m ml.detector.webcam

# Specify camera index and custom confidence threshold
python -m ml.detector.webcam --camera-id 0 --conf-threshold 0.30

# Run in headless mode (useful for remote/cloud servers)
python -m ml.detector.webcam --headless --max-frames 100
```
- **Controls**: Press **`Q`** or **`ESC`** in the window to quit.

### 2. Prerecorded Video Footage Analysis
Process recorded camera-trap footage, patrol video, or entry gate CCTV files:

```bash
# View real-time annotated playback preserving original video FPS
python -m ml.detector.video --input data/demo/patrol_sample.mp4

# Analyze video and export annotated video with tactical HUD overlay
python -m ml.detector.video --input data/demo/patrol_sample.mp4 --output data/demo/annotated.mp4

# Run offline batch processing without UI display window
python -m ml.detector.video --input data/demo/patrol_sample.mp4 --output data/demo/annotated.mp4 --no-display
```
- **Controls**: Press **`Q`** to terminate playback early.

---

## Expected Output (Phase 1)

### Standard Detection Schema
The `WildlifeDetector` produces normalized detection objects:

```json
[
  {
    "class": "animal",
    "confidence": 0.9412,
    "bbox": [0.3214, 0.2150, 0.7641, 0.8420]
  },
  {
    "class": "person",
    "confidence": 0.9125,
    "bbox": [0.1250, 0.3400, 0.3120, 0.9250]
  },
  {
    "class": "vehicle",
    "confidence": 0.8870,
    "bbox": [0.5520, 0.4100, 0.8900, 0.7850]
  }
]
```

- **`class`**: Category detected (`"animal"`, `"person"`, or `"vehicle"`).
- **`confidence`**: Floating-point score between `0.0` and `1.0`.
- **`bbox`**: Normalized coordinates `[x1, y1, x2, y2]` where all coordinates are clamped in `[0.0, 1.0]`.

---

## Running Automated Tests

Run the complete Phase 1 test suite covering model singleton behavior, false-alert immunity on empty frames, normalized coordinate schema, and test scenarios:

```bash
python -m unittest tests/test_detector.py
```

---

## Project Roadmap

| Phase | Milestone | Status | Description |
|---|---|---|---|
| **Phase 0** | Project Structure | ✅ Completed | Clean modular repository structure with configurations for TATR |
| **Phase 1** | Target Detection | ✅ Completed | MegaDetector V6 person, animal, vehicle detection on webcam & video |
| **Phase 2** | Species Recognition | ⏳ Upcoming | BioCLIP / specialized fine-tuned models for wildlife species identification |
| **Phase 3** | Context & Risk Engine | ⏳ Upcoming | Spatial (core vs buffer) & temporal (night/day) poaching risk scoring |
| **Phase 4** | FastAPI Service | ⏳ Upcoming | REST + WebSocket endpoints for video streaming and live incident alerts |
| **Phase 5** | Ranger Dashboard | ⏳ Upcoming | Interactive map, camera feeds, alert feed, and ranger dispatch interface |
| **Phase 6** | Multi-Camera Correlation | ⏳ Upcoming | Cross-camera sighting correlation and animal trajectory tracking |
| **Phase 7** | Field Demo & Hardening | ⏳ Upcoming | Simulated field drill with demo scenarios and end-to-end evaluation |

---

## License & Attribution

- Built for wildlife conservation and protected reserve management.
- Powered by [Microsoft AI for Good Lab MegaDetector](https://github.com/microsoft/Pytorch-Wildlife).
