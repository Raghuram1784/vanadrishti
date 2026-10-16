"""
Unit tests for VanaDrishti Phase 3 Context Engine and Spatial Store.

Tests:
- Haversine distance calculation
- CameraContext permitted hours evaluation (day, night, cross-midnight)
- CameraRegistry loading and proximity queries
- EventStore temporal filtering and repeated event counting
- Multi-camera spatial correlation without biometric re-identification
"""

from datetime import datetime, time, timedelta
import unittest
from pathlib import Path

from ml.context.models import CameraContext, WildlifeEvent
from ml.context.engine import (
    CameraRegistry,
    EventStore,
    ContextEngine,
    haversine_distance_meters,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestContextEngine(unittest.TestCase):
    """Test suite for spatial and temporal context operations."""

    def test_haversine_distance(self) -> None:
        """Verify Haversine great-circle distance calculation."""
        # CAM-01 (79.361, 20.248) and CAM-02 (79.364, 20.251)
        # Distance is approximately ~450 meters
        dist = haversine_distance_meters(20.248, 79.361, 20.251, 79.364)
        self.assertGreater(dist, 400.0)
        self.assertLess(dist, 550.0)

        # Same point distance should be 0
        self.assertEqual(haversine_distance_meters(20.0, 79.0, 20.0, 79.0), 0.0)

    def test_camera_allowed_hours(self) -> None:
        """Verify permitted operating hours evaluation."""
        cam = CameraContext(
            camera_id="CAM-TEST",
            name="Test Camera",
            latitude=20.0,
            longitude=79.0,
            zone_name="Demo Core",
            zone_type="CORE",
            allowed_hours={"start": "06:00", "end": "18:00"},
        )

        # Daytime at 10:30 AM -> True
        t_day = datetime(2026, 10, 7, 10, 30)
        self.assertTrue(cam.is_time_allowed(t_day))

        # Nighttime at 23:45 PM -> False
        t_night = datetime(2026, 10, 7, 23, 45)
        self.assertFalse(cam.is_time_allowed(t_night))

        # Cross-midnight shift (e.g. 20:00 to 06:00)
        cam_night_shift = CameraContext(
            camera_id="CAM-SHIFT",
            name="Night Shift Cam",
            latitude=20.0,
            longitude=79.0,
            zone_name="Demo Buffer",
            zone_type="BUFFER",
            allowed_hours={"start": "20:00", "end": "06:00"},
        )
        self.assertTrue(cam_night_shift.is_time_allowed(datetime(2026, 10, 7, 22, 0)))
        self.assertTrue(cam_night_shift.is_time_allowed(datetime(2026, 10, 7, 3, 0)))
        self.assertFalse(cam_night_shift.is_time_allowed(datetime(2026, 10, 7, 12, 0)))

    def test_camera_registry_proximity(self) -> None:
        """Verify camera loading from GeoJSON and proximity search."""
        geojson_path = PROJECT_ROOT / "config" / "cameras.geojson"
        registry = CameraRegistry.from_geojson(geojson_path)

        cam1 = registry.get("CAM-01")
        self.assertIsNotNone(cam1)
        self.assertEqual(cam1.zone_type, "CORE")

        # Find nearby cameras within 1000m of CAM-01
        nearby = registry.get_nearby_cameras("CAM-01", max_distance_meters=1000.0)
        nearby_ids = [c[0].camera_id for c in nearby]
        # CAM-02 is ~450m away from CAM-01
        self.assertIn("CAM-02", nearby_ids)
        # Distant CAM-04 (Moharli) should not be within 1000m
        self.assertNotIn("CAM-04", nearby_ids)

    def test_event_store_and_repeated_counts(self) -> None:
        """Verify event store temporal queries and repeated object counting."""
        store = EventStore()
        base_time = datetime(2026, 10, 7, 20, 0)

        evt1 = WildlifeEvent(
            event_id="E1",
            camera_id="CAM-01",
            timestamp=base_time - timedelta(minutes=25),
            object_type="person",
            confidence=0.9,
        )
        evt2 = WildlifeEvent(
            event_id="E2",
            camera_id="CAM-01",
            timestamp=base_time - timedelta(minutes=10),
            object_type="person",
            confidence=0.85,
        )
        evt3 = WildlifeEvent(
            event_id="E3",
            camera_id="CAM-02",
            timestamp=base_time - timedelta(minutes=5),
            object_type="animal",
            confidence=0.95,
            species="Bengal tiger",
        )

        store.add_event(evt1)
        store.add_event(evt2)
        store.add_event(evt3)

        # Count repeated person activity at CAM-01 in last 30 minutes
        count_30m = store.count_repeated_events("person", "CAM-01", minutes=30, before_time=base_time)
        self.assertEqual(count_30m, 2)

        # Count repeated person activity at CAM-01 in last 15 minutes
        count_15m = store.count_repeated_events("person", "CAM-01", minutes=15, before_time=base_time)
        self.assertEqual(count_15m, 1)

        # No repeated vehicle activity
        self.assertEqual(store.count_repeated_events("vehicle", "CAM-01", minutes=30, before_time=base_time), 0)

    def test_multi_camera_spatial_correlation_no_reid(self) -> None:
        """Verify spatial-temporal correlation notes without person re-identification."""
        geojson_path = PROJECT_ROOT / "config" / "cameras.geojson"
        registry = CameraRegistry.from_geojson(geojson_path)
        store = EventStore()

        t0 = datetime(2026, 10, 7, 22, 0)
        # Event at CAM-02 at 22:00
        e_cam2 = WildlifeEvent(
            event_id="E-C2",
            camera_id="CAM-02",
            timestamp=t0,
            object_type="person",
            confidence=0.85,
        )
        store.add_event(e_cam2)

        # Event at CAM-01 10 minutes later (450m away)
        e_cam1 = WildlifeEvent(
            event_id="E-C1",
            camera_id="CAM-01",
            timestamp=t0 + timedelta(minutes=10),
            object_type="person",
            confidence=0.88,
        )

        correlations = store.find_correlated_nearby_activity(
            target_event=e_cam1,
            camera_registry=registry,
            max_distance_meters=1000.0,
            minutes=30,
        )

        self.assertEqual(len(correlations), 1)
        desc = correlations[0]["description"]
        # Must say "Possibly related person activity", NEVER "same person"
        self.assertIn("Possibly related person activity", desc)
        self.assertNotIn("same person", desc.lower())


if __name__ == "__main__":
    unittest.main()
