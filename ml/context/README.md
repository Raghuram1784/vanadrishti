# VanaDrishti Phase 3: Context-Aware Wildlife Security Risk Engine

Phase 3 introduces an **explainable, deterministic security risk engine** that translates raw vision detections into contextual decision-support alerts for forest rangers and anti-poaching patrols.

---

## 1. System Philosophy & Ethical Principles

> [!IMPORTANT]
> **Ethical Wildlife Surveillance Standards:**
> - **No Presumption of Guilt:** VanaDrishti flags *suspicious circumstances* and *unauthorized presence*, never individuals. Persons are **never** automatically labeled as "poachers", "criminals", or "illegal hunters".
> - **No Facial or Identity Classification:** The system does not classify faces, clothing, ethnicity, or personal appearance.
> - **Human Decision Support:** Recommendations advise rangers to *"Review evidence"* or *"Dispatch patrol"*; the system **never** automates law-enforcement or lethal measures.
> - **Simulated / Demo Data:** All camera coordinates and forest reserve boundaries in this repository are synthetic demonstration artifacts.

---

## 2. Context Pipeline Flow

```
Camera Trap Frame
         │
         ▼
MegaDetector V6 (Phase 1)
         │
         ├── Class: "animal" ──► BioCLIP 2 (Phase 2) ──► Wildlife Event (Score: 0, Logged into Context Memory)
         │
         └── Class: "person" or "vehicle"
                  │
                  ▼
         Context-Aware Risk Engine (Phase 3)
                  ├── Camera Metadata (Zone: CORE/RESTRICTED/BUFFER, Operating Hours)
                  ├── Patrol Status (Authorized vs. Unauthorized)
                  ├── Temporal Memory (Repeated activity at node within 30 min)
                  └── Spatial Ecological Context (Nearby high-value wildlife activity within 60 min)
                  │
                  ▼
         Explainable Assessment (Score 0-100, Transparent Reasons, Recommended Action)
```

---

## 3. Explainable Deterministic Scoring

The risk score begins at **0** and increments only when explicit rules trigger. Every score increment produces a corresponding human-readable reason.

### Person Detections:
- `+25`: Person detected (base object presence)
- `+30`: Camera located in **CORE** protected forest zone
- `+20`: Camera located in **RESTRICTED** fireline/boundary zone
- `+20`: Activity occurred **outside allowed operating hours**
- `+20`: **No authorized patrol** active in sector
- `+10`: **Repeated person activity** recorded at node within recent window (30 min)

### Vehicle Detections:
- `+20`: Vehicle detected (base object presence)
- `+30`: Camera located in **CORE** protected forest zone
- `+20`: Camera located in **RESTRICTED** zone
- `+20`: Activity occurred **outside allowed hours**
- `+15`: **No authorized patrol** active in sector
- `+10`: **Repeated vehicle activity** recorded at node within 30 min

### Ecological Wildlife Context:
- `+15`: Recent **high-value wildlife** (e.g., tiger, leopard) recorded nearby ($\le 1500$m, within 60 min)
- `+10`: Recent **wildlife presence** occurred shortly before human/vehicle event (within 30 min)

### Normal Wildlife:
- Score: `0`, Risk Level: `LOW`, Alert: `False`.
- Stored into context memory for spatial-temporal ecological correlation.

---

## 4. Risk Levels & Decision-Support Actions

| Score Range | Risk Level | Alert | Recommended Decision-Support Action |
| :---: | :---: | :---: | :--- |
| **0 – 24** | `LOW` | `False` | Log event for wildlife monitoring. |
| **25 – 49** | `MEDIUM` | `True` | Monitor camera feed and log event on ranger dashboard. |
| **50 – 74** | `HIGH` | `True` | Review camera footage and alert nearest field patrol. |
| **75 – 100** | `CRITICAL` | `True` | Review evidence immediately and dispatch rapid response patrol. |

Scores are strictly capped at **100**.

---

## 5. Multi-Camera Spatial Correlation

The engine uses the great-circle **Haversine formula** to measure inter-camera distances.
When an event occurs:
- Cameras within $1,500$m are queried for correlated temporal activity within 30 minutes.
- Multi-camera correlations are logged as *"possibly related activity at nearby camera"* without attempting biometric person re-identification.
