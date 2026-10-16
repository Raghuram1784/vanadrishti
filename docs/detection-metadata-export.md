# VanaDrishti: Detection Metadata and Export Specification

## 1. Overview and Export Locations

VanaDrishti provides standardized metadata export for all recorded observations, model inferences, and risk assessments. This allows teammates and external services to ingest detection records, evaluate model confidence, and conduct offline analytics.

### Where to Access Metadata in the Dashboard:
1. **Events Page (`/events`)**:
   - **Single Event Export**: Click any row in the Events Table to open the Event Details drawer. Scroll to the **Detection Metadata & Export** panel. From there, you can:
     - **Inspect**: View structured key-value tables of the camera, detections, species, and risk.
     - **Copy JSON**: Copy the normalized JSON structure directly to your clipboard.
     - **Download JSON**: Download `{event_id}-metadata.json`.
     - **Download CSV**: Download a single-event CSV (`event-{event_id}-detections.csv`).
   - **Batch Filtered Export**: In the filter caption toolbar on `/events`, click **Export Filtered (N) CSV** to download all currently filtered events in a single RFC 4180-compliant CSV file.
2. **Monitor Page (`/monitor`)**:
   - After analyzing any static image or running a scenario, the **Detection Metadata & Export** panel renders directly below the risk assessment results for immediate export.
3. **REST API Direct Access**:
   - All events can be queried programmatically via:
     - `GET /api/events` (supports query params: `camera_id`, `event_type`, `limit`)
     - `GET /api/events/{event_id}`

---

## 2. Standardized JSON Schema (v1.0)

Every exported JSON follows this contract:

```json
{
  "schema_version": "1.0",
  "event_id": "8fa21e54-5a3d-4c31-97b4-6a8b792e31d4",
  "timestamp": "2026-10-16T18:25:30.142000+05:30",
  "camera": {
    "id": "C-18",
    "name": "Sector C-18 Trail Camera (Laptop Prototype)",
    "source": "live_camera",
    "hardware_node": "Sector C-18 Laptop Webcam (Prototype Node)",
    "geographic_zone": "CORE ZONE A",
    "zone_type": "CORE",
    "operational_policy": "CRITICAL",
    "coordinates": {
      "latitude": 20.25,
      "longitude": 79.363,
      "coordinate_type": "configured_geographic_metadata"
    }
  },
  "detections": [
    {
      "index": 0,
      "type": "animal",
      "detector_score": 0.9421,
      "bbox_normalized": [0.125, 0.312, 0.654, 0.821],
      "uncertain": false,
      "uncertainty_reason": null,
      "candidate_signals": null,
      "species": {
        "top1": "Panthera tigris",
        "ranking_score": 0.8924,
        "top3": [
          { "label": "Panthera tigris", "ranking_score": 0.8924 },
          { "label": "Panthera pardus", "ranking_score": 0.0812 },
          { "label": "Cuon alpinus", "ranking_score": 0.0153 }
        ]
      }
    }
  ],
  "risk": {
    "score": 15,
    "level": "LOW",
    "alert_required": false,
    "reasons": [
      "Activity in designated wildlife habitat",
      "Tiger presence recorded in core conservation sector"
    ],
    "recommended_action": "Routine observation logged"
  },
  "incident": {
    "alert_id": null,
    "status": "NONE",
    "policy": "CRITICAL",
    "review_timestamp": null
  },
  "frame_evidence": {
    "evidence_image_url": "/api/evidence/8fa21e54-5a3d-4c31-97b4-6a8b792e31d4.jpg",
    "media_type": "image/jpeg",
    "disclaimer": "Metadata reflects recorded observation rather than complete raw inference history."
  }
}
```

### Field Definitions:

| Section | Field | Type | Description |
|---|---|---|---|
| **Root** | `schema_version` | String | Format version (`"1.0"`). |
| | `event_id` | UUID String | Unique observation identifier. |
| | `timestamp` | ISO 8601 String | Observation time with Asia/Kolkata (`+05:30`) timezone offset. |
| **Camera** | `camera.id` | String | Sensor identifier (`C-18`, `C-21`, `CAM-01` to `CAM-04`). |
| | `camera.name` | String | Sensor label. |
| | `camera.source` | Enum String | Ingestion channel: `"live_camera"`, `"image"`, or `"demo"`. |
| | `camera.hardware_node` | String | Physical hardware description (`Laptop Webcam`, `Android Mobile Patrol`, or `Synthetic Slot`). |
| | `camera.geographic_zone`| String | Conservation zone label (e.g. `"CORE ZONE A"`). |
| | `camera.zone_type` | String | Regulatory zone category (`"CORE"`, `"BUFFER"`, `"FIRELINE"`). |
| | `camera.operational_policy`| Enum String | Alert policy: `"SAFE"`, `"RESTRICTED"`, or `"CRITICAL"`. |
| | `camera.coordinates` | Object | Configured Tadoba-Andhari coordinates (`latitude`, `longitude`). |
| **Detections** | `detections[].index` | Integer | Zero-based object index in frame. |
| | `detections[].type` | Enum String | Detected category: `"animal"`, `"person"`, or `"vehicle"`. |
| | `detections[].detector_score` | Float | MegaDetector confidence score (range `0.0` to `1.0`). |
| | `detections[].bbox_normalized` | Array [4] | Normalized coordinates `[x1, y1, x2, y2]`. |
| | `detections[].uncertain` | Boolean | `true` if frame is backlit, blurred, or class-ambiguous. |
| | `detections[].uncertainty_reason`| String/null | Explanation for uncertain flag. |
| | `detections[].candidate_signals`| Array/null | Competing detector candidate scores. |
| | `detections[].species` | Object/null | BioCLIP classification (populated **only** for `animal`). |
| **Risk** | `risk.score` | Integer | Aggregated risk score (`0` to `100`). |
| | `risk.level` | Enum String | Risk category: `"LOW"`, `"MEDIUM"`, `"HIGH"`, or `"CRITICAL"`. |
| | `risk.alert_required` | Boolean | Whether an urgent ranger notification was triggered. |
| | `risk.reasons` | String[] | Human-readable explanation strings including policy impact. |
| | `risk.recommended_action`| String | Recommended ranger protocol. |
| **Incident** | `incident.alert_id` | String/null | Corresponding alert record UUID if escalated. |
| | `incident.status` | Enum String | `"NEW"`, `"REVIEWING"`, `"PATROL_ASSIGNED"`, `"RESOLVED"`, etc. |
| | `incident.policy` | String/null | Operational policy active during incident creation. |
| **Frame** | `frame_evidence.evidence_image_url` | String/null | Relative endpoint path to persisted JPEG. |

---

## 3. CSV Column Definitions

Exported CSVs adhere to RFC 4180 (comma-delimited, double-quote escaped, UTF-8 encoded). Each row corresponds to **one detected object**.

| Column | Data Type | Description |
|---|---|---|
| `event_id` | UUID String | Observation identifier. |
| `timestamp_iso` | ISO 8601 String | Event timestamp (`YYYY-MM-DDTHH:MM:SS+05:30`). |
| `camera_id` | String | Camera identifier (`C-18`, `C-21`, etc.). |
| `camera_name` | String | Full camera label. |
| `camera_source` | String | Source medium (`live_camera`, `image`, `demo`). |
| `geographic_zone` | String | Administrative sector (e.g. `CORE ZONE A`). |
| `zone_type` | String | Zone classification (`CORE`, `BUFFER`, `FIRELINE`). |
| `operational_policy`| String | Alert policy (`SAFE`, `RESTRICTED`, `CRITICAL`). |
| `latitude` | Float | Sensor latitude coordinate. |
| `longitude` | Float | Sensor longitude coordinate. |
| `detection_index` | Integer/empty | 0-based index of object in frame. Empty if no detections. |
| `detection_type` | String | `animal`, `person`, `vehicle`, or `none`. |
| `detector_score` | Float/empty | MegaDetector confidence score. |
| `bbox_x1` | Float/empty | Left normalized boundary (`0.0` to `1.0`). |
| `bbox_y1` | Float/empty | Top normalized boundary (`0.0` to `1.0`). |
| `bbox_x2` | Float/empty | Right normalized boundary (`0.0` to `1.0`). |
| `bbox_y2` | Float/empty | Bottom normalized boundary (`0.0` to `1.0`). |
| `uncertain` | Boolean | Whether detection is ambiguous. |
| `uncertainty_reason`| String/empty | Reason for uncertainty. |
| `species_top1` | String/empty | BioCLIP top species scientific name (animals only). |
| `species_ranking_score`| Float/empty | BioCLIP species ranking score. |
| `risk_level` | String | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `risk_score` | Integer | Overall risk assessment (`0` to `100`). |
| `alert_required` | Boolean | Whether alert was dispatched. |
| `risk_reasons` | String | Pipe-separated (`\|`) list of risk rationale strings. |
| `recommended_action`| String | Recommended protocol. |
| `incident_status` | String | Review status (`NEW`, `REVIEWING`, `RESOLVED`, etc.). |
| `evidence_image_url`| String/empty | Stored evidence image path. |

> **Zero-Detection Event Handling**: When an event frame has 0 detected objects, the exporter still outputs exactly 1 row with `detection_type="none"` and empty detection columns. This ensures that camera surveillance activity records are never omitted during audit logs.

---

## 4. Detector Score vs. Species Ranking Score

- **MegaDetector Confidence Score (`detector_score`)**:
  - Generated by MegaDetector V6 (YOLO-based architecture).
  - Represents the model's confidence that an object belongs to the coarse taxonomic category (`animal`, `person`, `vehicle`).
  - Range: `0.00` to `1.00`.
- **BioCLIP Species Ranking Score (`species_ranking_score`)**:
  - Generated by BioCLIP 2 (vision-language contrastive zero-shot embedding).
  - Computed as softmax similarity over scientific taxonomic species embeddings for cropped animal patches.
  - **Important**: This is a *ranking score* among candidates, **not a calibrated Bayesian probability of species occurrence**.
  - Species ranking is **never** generated for human or vehicle detections.

---

## 5. Bounding-Box Coordinate Conventions

Coordinates are normalized relative to the original image dimensions:
- Format: `[x1, y1, x2, y2]`
- Range: `0.0 <= x1 < x2 <= 1.0` and `0.0 <= y1 < y2 <= 1.0`
- Coordinate mapping to absolute pixel coordinates:
  ```python
  pixel_x1 = int(bbox_normalized[0] * image_width)
  pixel_y1 = int(bbox_normalized[1] * image_height)
  pixel_x2 = int(bbox_normalized[2] * image_width)
  pixel_y2 = int(bbox_normalized[3] * image_height)
  ```

---

## 6. Sensor and Operational Relationships

- **Physical Feeds vs. Simulated Metadata**:
  - `C-18` (Laptop camera) and `C-21` (Android mobile patrol camera) are **real, live physical camera inputs** capturing live frames and running real-time AI inference.
  - Their geographic location coordinates (`[20.250° N, 79.363° E]` etc.) represent configured conservation deployment positions within the demonstration scenario.
  - Slots `CAM-01` to `CAM-04` represent inactive synthetic corridors.
- **Event ID vs. Alert ID**:
  - Every analyzed frame produces a unique `event_id`.
  - Only events that meet high or critical risk criteria generate a corresponding `alert_id` (accessible in `/alerts`).
  - Repetitive video frames of the same ongoing event within a 20-second window are marked as `CONTINUATION` by temporal deduplication and do not generate duplicate alert records.

---

## 7. How to Consume Exports (Python Integration Example)

```python
import json
import pandas as pd
import requests

# 1. Fetching live event data from the VanaDrishti REST API
BASE_URL = "http://localhost:8000"
response = requests.get(f"{BASE_URL}/api/events?limit=50")
events = response.json()

print(f"Retrieved {len(events)} events.")

# 2. Loading exported CSV with pandas
df = pd.read_csv("vanadrishti-detections-export.csv")
print("Export summary by object type:")
print(df["detection_type"].value_counts())

# Filter for high-risk human presence in restricted/critical zones
restricted_alerts = df[(df["detection_type"] == "person") & (df["risk_level"].isin(["HIGH", "CRITICAL"]))]
print(f"High-priority human detections: {len(restricted_alerts)}")

# 3. Reading single-event JSON
with open("vanadrishti-event-sample.json", "r") as f:
    event_data = json.load(f)

print(f"Event {event_data['event_id']} on camera {event_data['camera']['id']}")
for det in event_data["detections"]:
    print(f" - {det['type']} (score: {det['detector_score']:.2f})")
```
