"""
VanaDrishti Phase 3: Context-Aware Wildlife Security Domain Models.

Defines schemas for camera context, normalized wildlife events, and explainable risk assessments.
NOTE: All geographic coordinates and forest zones are simulated demonstration data.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid


@dataclass
class CameraContext:
    """
    Metadata representation of a forest camera surveillance node.

    DEMO/SIMULATED:
    Coordinates and zones are synthetic demonstration artifacts and do not reflect
    actual operational or classified camera trap locations in any wildlife sanctuary.
    """
    camera_id: str
    name: str
    latitude: float
    longitude: float
    zone_name: str
    zone_type: str  # 'CORE', 'RESTRICTED', 'BUFFER', 'PUBLIC'
    active: bool = True
    allowed_hours: Optional[Dict[str, str]] = field(
        default_factory=lambda: {"start": "06:00", "end": "18:00"}
    )
    patrol_authorized: bool = False
    notes: Optional[str] = None

    def is_time_allowed(self, dt: Union[datetime, str, time]) -> bool:
        """
        Check if the given time falls within the camera's permitted operating hours.
        """
        if not self.allowed_hours:
            return True

        if isinstance(dt, str):
            # Parse ISO or HH:MM
            try:
                dt_obj = datetime.fromisoformat(dt)
                check_time = dt_obj.time()
            except ValueError:
                parts = dt.split(":")
                check_time = time(int(parts[0]), int(parts[1]))
        elif isinstance(dt, datetime):
            check_time = dt.time()
        elif isinstance(dt, time):
            check_time = dt
        else:
            return True

        start_str = self.allowed_hours.get("start", "00:00")
        end_str = self.allowed_hours.get("end", "23:59")

        sh, sm = [int(p) for p in start_str.split(":")[:2]]
        eh, em = [int(p) for p in end_str.split(":")[:2]]
        start_t = time(sh, sm)
        end_t = time(eh, em)

        if start_t <= end_t:
            return start_t <= check_time <= end_t
        else:
            # Crosses midnight (e.g. 20:00 to 06:00)
            return check_time >= start_t or check_time <= end_t

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type.upper(),
            "active": self.active,
            "allowed_hours": self.allowed_hours,
            "patrol_authorized": self.patrol_authorized,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraContext":
        return cls(
            camera_id=data["camera_id"],
            name=data.get("name", data["camera_id"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            zone_name=data.get("zone_name", "Unknown Zone"),
            zone_type=data.get("zone_type", "BUFFER").upper(),
            active=data.get("active", True),
            allowed_hours=data.get("allowed_hours"),
            patrol_authorized=data.get("patrol_authorized", False),
            notes=data.get("notes"),
        )


@dataclass
class WildlifeEvent:
    """
    Normalized multi-modal event representing an automated vision detection in the forest.
    """
    event_id: str
    camera_id: str
    timestamp: datetime
    object_type: str  # 'animal', 'person', 'vehicle'
    confidence: float
    bbox: Optional[Tuple[float, float, float, float]] = None
    species: Optional[str] = None
    species_score: Optional[float] = None
    top_species_candidates: Optional[List[Dict[str, Any]]] = None
    zone_type: Optional[str] = None
    patrol_authorized: bool = False
    recent_related_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "timestamp": self.timestamp.isoformat(),
            "object_type": self.object_type,
            "confidence": round(float(self.confidence), 4),
            "bbox": [round(float(c), 4) for c in self.bbox] if self.bbox else None,
            "species": self.species,
            "species_score": round(float(self.species_score), 4) if self.species_score is not None else None,
            "top_species_candidates": self.top_species_candidates,
            "zone_type": self.zone_type,
            "patrol_authorized": self.patrol_authorized,
            "recent_related_events": self.recent_related_events,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WildlifeEvent":
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        bbox_val: Optional[Tuple[float, float, float, float]] = None
        raw_bbox = data.get("bbox")
        if raw_bbox is not None and len(raw_bbox) == 4:
            bbox_val = (
                float(raw_bbox[0]),
                float(raw_bbox[1]),
                float(raw_bbox[2]),
                float(raw_bbox[3]),
            )

        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            camera_id=data["camera_id"],
            timestamp=ts,
            object_type=data["object_type"],
            confidence=float(data.get("confidence", 1.0)),
            bbox=bbox_val,
            species=data.get("species"),
            species_score=float(data["species_score"]) if data.get("species_score") is not None else None,
            top_species_candidates=data.get("top_species_candidates"),
            zone_type=data.get("zone_type"),
            patrol_authorized=bool(data.get("patrol_authorized", False)),
            recent_related_events=data.get("recent_related_events", []),
        )


@dataclass
class RiskAssessment:
    """
    Deterministic, explainable security risk evaluation output.
    """
    event_id: str
    risk_score: int
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    alert: bool
    reasons: List[str]
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "alert": self.alert,
            "reasons": list(self.reasons),
            "recommended_action": self.recommended_action,
        }
