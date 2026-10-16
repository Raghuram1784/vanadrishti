"""
VanaDrishti Phase 3: In-Memory Context Engine and Multi-Camera Spatial Store.

Manages simulated camera network state, in-memory event history, multi-camera
spatial proximity calculations, and temporal correlation windows.
"""

from datetime import datetime, timedelta
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ml.context.models import CameraContext, WildlifeEvent

logger = logging.getLogger("vanadrishti.context")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def haversine_distance_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Compute great-circle distance between two GPS coordinates in meters
    using the Haversine formula.
    """
    R = 6371000.0  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


class CameraRegistry:
    """Registry of known forest cameras and their operational parameters."""

    def __init__(self) -> None:
        self._cameras: Dict[str, CameraContext] = {}

    def register(self, camera: CameraContext) -> None:
        """Register or update a camera node."""
        self._cameras[camera.camera_id] = camera

    def get(self, camera_id: str) -> Optional[CameraContext]:
        """Retrieve camera context by ID."""
        return self._cameras.get(camera_id)

    def list_all(self) -> List[CameraContext]:
        """List all registered cameras."""
        return list(self._cameras.values())

    def get_nearby_cameras(
        self,
        camera_id: str,
        max_distance_meters: float = 1500.0,
    ) -> List[Tuple[CameraContext, float]]:
        """
        Find cameras within max_distance_meters from the specified camera.
        Returns list of tuples: (CameraContext, distance_in_meters), sorted by distance.
        """
        origin = self.get(camera_id)
        if not origin:
            return []

        nearby: List[Tuple[CameraContext, float]] = []
        for other_id, other in self._cameras.items():
            if other_id == camera_id:
                continue
            dist = haversine_distance_meters(
                origin.latitude, origin.longitude, other.latitude, other.longitude
            )
            if dist <= max_distance_meters:
                nearby.append((other, dist))

        nearby.sort(key=lambda item: item[1])
        return nearby

    @classmethod
    def from_geojson(cls, geojson_path: Path) -> "CameraRegistry":
        """Load camera network from GeoJSON FeatureCollection."""
        registry = cls()
        if not geojson_path.exists():
            logger.warning("GeoJSON camera file not found at %s", geojson_path)
            return registry

        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])

            camera = CameraContext(
                camera_id=props["camera_id"],
                name=props.get("name", props["camera_id"]),
                longitude=float(coords[0]),
                latitude=float(coords[1]),
                zone_name=props.get("zone_name", "Demo Zone"),
                zone_type=props.get("zone_type", "BUFFER"),
                active=props.get("active", True),
                allowed_hours=props.get("allowed_hours"),
                patrol_authorized=props.get("patrol_authorized", False),
                notes=props.get("notes"),
            )
            registry.register(camera)

        logger.info("Loaded %d cameras from %s", len(registry._cameras), geojson_path.name)
        return registry


class EventStore:
    """Lightweight in-memory history of recent wildlife and surveillance events."""

    def __init__(self) -> None:
        self._events: List[WildlifeEvent] = []

    def add_event(self, event: WildlifeEvent) -> None:
        """Record an event into the store."""
        self._events.append(event)

    def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()

    def get_recent_events(
        self,
        minutes: int = 60,
        before_time: Optional[datetime] = None,
        camera_id: Optional[str] = None,
    ) -> List[WildlifeEvent]:
        """
        Query events that occurred within the last `minutes` prior to `before_time`.
        Optionally filtered by camera_id.
        """
        ref_time = before_time or datetime.now()
        start_time = ref_time - timedelta(minutes=minutes)

        results = []
        for e in self._events:
            if camera_id and e.camera_id != camera_id:
                continue
            if start_time <= e.timestamp <= ref_time:
                results.append(e)

        return sorted(results, key=lambda x: x.timestamp)

    def count_repeated_events(
        self,
        object_type: str,
        camera_id: str,
        minutes: int = 30,
        before_time: Optional[datetime] = None,
    ) -> int:
        """
        Count prior events of the same object_type at the given camera within the time window.
        Excludes the exact current event if before_time is set.
        """
        events = self.get_recent_events(
            minutes=minutes,
            before_time=before_time,
            camera_id=camera_id,
        )
        # Filter matching object type
        return sum(1 for e in events if e.object_type == object_type)

    def get_recent_wildlife_events(
        self,
        camera_id: str,
        camera_registry: CameraRegistry,
        minutes: int = 60,
        max_distance_meters: float = 1500.0,
        high_value_species: Optional[List[str]] = None,
        before_time: Optional[datetime] = None,
    ) -> List[Tuple[WildlifeEvent, float]]:
        """
        Find wildlife events (object_type == 'animal') that occurred at or near the given camera.
        Returns list of (WildlifeEvent, distance_in_meters).
        """
        ref_time = before_time or datetime.now()
        start_time = ref_time - timedelta(minutes=minutes)
        cam = camera_registry.get(camera_id)

        matched: List[Tuple[WildlifeEvent, float]] = []
        for e in self._events:
            if e.object_type != "animal":
                continue
            if not (start_time <= e.timestamp <= ref_time):
                continue

            # Check species filter if requested
            if high_value_species and e.species:
                sp_norm = e.species.lower()
                is_match = any(hv in sp_norm for hv in high_value_species)
                if not is_match:
                    continue

            # Distance calculation
            if e.camera_id == camera_id:
                dist = 0.0
            elif cam:
                other_cam = camera_registry.get(e.camera_id)
                if other_cam:
                    dist = haversine_distance_meters(
                        cam.latitude, cam.longitude, other_cam.latitude, other_cam.longitude
                    )
                else:
                    dist = float("inf")
            else:
                dist = float("inf")

            if dist <= max_distance_meters:
                matched.append((e, dist))

        matched.sort(key=lambda item: item[0].timestamp, reverse=True)
        return matched

    def find_correlated_nearby_activity(
        self,
        target_event: WildlifeEvent,
        camera_registry: CameraRegistry,
        max_distance_meters: float = 1500.0,
        minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Multi-camera spatial-temporal correlation.
        Identifies possibly related object occurrences at nearby cameras.
        Does NOT perform re-identification or person recognition.
        """
        ref_time = target_event.timestamp
        start_time = ref_time - timedelta(minutes=minutes)
        cam = camera_registry.get(target_event.camera_id)
        if not cam:
            return []

        correlations: List[Dict[str, Any]] = []
        for e in self._events:
            if e.event_id == target_event.event_id:
                continue
            if e.object_type != target_event.object_type:
                continue
            if not (start_time <= e.timestamp <= ref_time):
                continue

            other_cam = camera_registry.get(e.camera_id)
            if not other_cam:
                continue

            dist = haversine_distance_meters(
                cam.latitude, cam.longitude, other_cam.latitude, other_cam.longitude
            )
            if 0 < dist <= max_distance_meters:
                time_delta_min = round((ref_time - e.timestamp).total_seconds() / 60.0, 1)
                correlations.append({
                    "event_id": e.event_id,
                    "camera_id": e.camera_id,
                    "distance_meters": round(dist, 1),
                    "time_delta_minutes": time_delta_min,
                    "description": (
                        f"Possibly related {target_event.object_type} activity at nearby "
                        f"{e.camera_id} ({round(dist)}m away, {time_delta_min} min prior)"
                    ),
                })

        return correlations


class ContextEngine:
    """
    Unified manager for forest camera network metadata and surveillance event history.
    """

    def __init__(
        self,
        camera_registry: Optional[CameraRegistry] = None,
        event_store: Optional[EventStore] = None,
    ) -> None:
        self.cameras = camera_registry or CameraRegistry()
        self.events = event_store or EventStore()

    @classmethod
    def create_default(cls, config_dir: Optional[Path] = None) -> "ContextEngine":
        """Instantiate context engine loaded from default project configuration."""
        if config_dir is None:
            config_dir = PROJECT_ROOT / "config"

        geojson_path = config_dir / "cameras.geojson"
        registry = CameraRegistry.from_geojson(geojson_path)
        return cls(camera_registry=registry, event_store=EventStore())
