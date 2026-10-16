"""
Unit tests for VanaDrishti Phase 3 Explainable Wildlife Security Risk Engine.

Tests:
- Normal animal detections yield zero score and no security alarm
- Authorized ranger in permitted hours yields low/medium score
- Unauthorized person in CORE zone at night yields CRITICAL score
- Vehicle in RESTRICTED zone at night yields CRITICAL score
- Wildlife context (tiger nearby) appropriately elevates score
- Scores are strictly capped at 100
- Risk levels (LOW, MEDIUM, HIGH, CRITICAL) trigger correct boundaries and actions
- Every score increment produces a human-readable explanation
- Ethical constraint: Persons are NEVER labeled 'poachers' or 'criminals'
"""

from datetime import datetime, timedelta
from pathlib import Path
import unittest

from ml.context.engine import CameraRegistry, ContextEngine, EventStore
from ml.context.models import CameraContext, WildlifeEvent
from ml.context.risk import RiskEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRiskEngine(unittest.TestCase):
    """Test suite for deterministic explainable risk assessment."""

    def setUp(self) -> None:
        self.context = ContextEngine.create_default(PROJECT_ROOT / "config")
        self.engine = RiskEngine(context_engine=self.context)

    def test_normal_animal_produces_no_alert(self) -> None:
        """Verify animal detections yield score 0, alert False, and are stored as context."""
        event = WildlifeEvent(
            event_id="EVT-ANIMAL-01",
            camera_id="CAM-02",
            timestamp=datetime(2026, 10, 7, 21, 0),
            object_type="animal",
            confidence=0.95,
            species="Bengal tiger",
            species_score=0.98,
            zone_type="CORE",
        )

        assessment = self.engine.evaluate(event)
        self.assertEqual(assessment.risk_score, 0)
        self.assertEqual(assessment.risk_level, "LOW")
        self.assertFalse(assessment.alert)
        self.assertIn("Bengal tiger detected (normal ecological activity)", assessment.reasons)
        self.assertEqual(assessment.recommended_action, "Log event for wildlife monitoring.")

        # Event must be saved in context memory for subsequent correlation
        stored = self.context.events.get_recent_events(minutes=60, before_time=datetime(2026, 10, 7, 21, 30))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].event_id, "EVT-ANIMAL-01")

    def test_authorized_ranger_daytime(self) -> None:
        """Verify authorized ranger during permitted hours yields baseline medium score."""
        event = WildlifeEvent(
            event_id="EVT-PATROL-01",
            camera_id="CAM-04",  # BUFFER zone, allowed 05:00-21:00
            timestamp=datetime(2026, 10, 7, 10, 30),
            object_type="person",
            confidence=0.90,
            zone_type="BUFFER",
            patrol_authorized=True,
        )

        assessment = self.engine.evaluate(event)
        # Base person (+25), no zone penalty, permitted hours, patrol authorized
        self.assertEqual(assessment.risk_score, 25)
        self.assertEqual(assessment.risk_level, "MEDIUM")
        self.assertTrue(assessment.alert)
        self.assertIn("Person detected", assessment.reasons)
        self.assertNotIn("No authorized patrol active in sector", assessment.reasons)
        self.assertNotIn("Activity occurred outside allowed hours", assessment.reasons)

    def test_unauthorized_person_core_night(self) -> None:
        """Verify unauthorized person in CORE zone at night produces CRITICAL assessment."""
        event = WildlifeEvent(
            event_id="EVT-NIGHT-01",
            camera_id="CAM-01",  # CORE zone, allowed 06:00-18:00
            timestamp=datetime(2026, 10, 7, 23, 41),
            object_type="person",
            confidence=0.88,
            zone_type="CORE",
            patrol_authorized=False,
        )

        assessment = self.engine.evaluate(event)
        # Person (+25) + CORE (+30) + outside hours (+20) + unauthorized (+20) = 95
        self.assertEqual(assessment.risk_score, 95)
        self.assertEqual(assessment.risk_level, "CRITICAL")
        self.assertTrue(assessment.alert)
        self.assertIn("Person detected", assessment.reasons)
        self.assertIn("Camera is in CORE protected zone", assessment.reasons)
        self.assertIn("Activity occurred outside allowed hours", assessment.reasons)
        self.assertIn("No authorized patrol active in sector", assessment.reasons)

    def test_unauthorized_vehicle_restricted_night(self) -> None:
        """Verify unauthorized vehicle in RESTRICTED zone at night produces CRITICAL score."""
        event = WildlifeEvent(
            event_id="EVT-VEHICLE-01",
            camera_id="CAM-03",  # RESTRICTED zone, allowed 06:00-19:00
            timestamp=datetime(2026, 10, 8, 2, 15),
            object_type="vehicle",
            confidence=0.82,
            zone_type="RESTRICTED",
            patrol_authorized=False,
        )

        assessment = self.engine.evaluate(event)
        # Vehicle (+20) + RESTRICTED (+20) + outside hours (+20) + unauthorized (+15) = 75
        self.assertEqual(assessment.risk_score, 75)
        self.assertEqual(assessment.risk_level, "CRITICAL")
        self.assertTrue(assessment.alert)
        self.assertIn("Vehicle detected", assessment.reasons)
        self.assertIn("Camera is in RESTRICTED zone", assessment.reasons)
        self.assertIn("Activity occurred outside allowed hours", assessment.reasons)
        self.assertIn("No authorized patrol active in sector", assessment.reasons)

    def test_wildlife_context_elevates_score(self) -> None:
        """Verify prior high-value wildlife event increases human-event risk score."""
        # 1. Tiger event at CAM-02 at 22:15
        tiger_evt = WildlifeEvent(
            event_id="EVT-TIGER-01",
            camera_id="CAM-02",  # ~450m from CAM-01
            timestamp=datetime(2026, 10, 7, 22, 15),
            object_type="animal",
            confidence=0.95,
            species="Bengal tiger",
            species_score=0.99,
            zone_type="CORE",
        )
        self.engine.evaluate(tiger_evt)

        # 2. Person at CAM-01 at 22:30 (15 min later)
        person_evt = WildlifeEvent(
            event_id="EVT-PERSON-02",
            camera_id="CAM-01",
            timestamp=datetime(2026, 10, 7, 22, 30),
            object_type="person",
            confidence=0.90,
            zone_type="CORE",
            patrol_authorized=False,
        )

        assessment = self.engine.evaluate(person_evt)
        # Base 95 + 15 (high-value tiger nearby) + 10 (animal shortly before) = 120 -> capped at 100
        self.assertEqual(assessment.risk_score, 100)
        self.assertEqual(assessment.risk_level, "CRITICAL")
        self.assertTrue(any("tiger" in r.lower() for r in assessment.reasons))
        self.assertTrue(any("shortly before" in r.lower() for r in assessment.reasons))

    def test_score_strictly_capped_at_100(self) -> None:
        """Verify scores do not exceed 100 even with accumulated penalties."""
        # Pre-seed repeated activity and wildlife events
        base_t = datetime(2026, 10, 7, 23, 0)
        self.context.events.add_event(WildlifeEvent(
            event_id="E-PREV",
            camera_id="CAM-01",
            timestamp=base_t - timedelta(minutes=10),
            object_type="person",
            confidence=0.8,
        ))
        self.context.events.add_event(WildlifeEvent(
            event_id="E-TIG",
            camera_id="CAM-01",
            timestamp=base_t - timedelta(minutes=20),
            object_type="animal",
            species="Bengal tiger",
            confidence=0.9,
        ))

        evt = WildlifeEvent(
            event_id="E-CAP",
            camera_id="CAM-01",
            timestamp=base_t,
            object_type="person",
            confidence=0.9,
            zone_type="CORE",
            patrol_authorized=False,
        )
        assessment = self.engine.evaluate(evt)
        self.assertLessEqual(assessment.risk_score, 100)
        self.assertEqual(assessment.risk_score, 100)

    def test_risk_level_boundaries(self) -> None:
        """Verify LOW (0-24), MEDIUM (25-49), HIGH (50-74), and CRITICAL (75-100) thresholds."""
        lvl_0, a_0, _ = self.engine.get_risk_level_info(0)
        self.assertEqual(lvl_0, "LOW")
        self.assertFalse(a_0)

        lvl_24, a_24, _ = self.engine.get_risk_level_info(24)
        self.assertEqual(lvl_24, "LOW")
        self.assertFalse(a_24)

        lvl_25, a_25, _ = self.engine.get_risk_level_info(25)
        self.assertEqual(lvl_25, "MEDIUM")
        self.assertTrue(a_25)

        lvl_49, a_49, _ = self.engine.get_risk_level_info(49)
        self.assertEqual(lvl_49, "MEDIUM")
        self.assertTrue(a_49)

        lvl_50, a_50, _ = self.engine.get_risk_level_info(50)
        self.assertEqual(lvl_50, "HIGH")
        self.assertTrue(a_50)

        lvl_74, a_74, _ = self.engine.get_risk_level_info(74)
        self.assertEqual(lvl_74, "HIGH")
        self.assertTrue(a_74)

        lvl_75, a_75, _ = self.engine.get_risk_level_info(75)
        self.assertEqual(lvl_75, "CRITICAL")
        self.assertTrue(a_75)

        lvl_100, a_100, _ = self.engine.get_risk_level_info(100)
        self.assertEqual(lvl_100, "CRITICAL")
        self.assertTrue(a_100)

    def test_ethical_language_compliance(self) -> None:
        """Verify that persons are NEVER labeled as 'poacher', 'criminal', or 'illegal hunter'."""
        forbidden_terms = ["poacher", "criminal", "illegal hunter", "lawbreaker", "felon"]

        event = WildlifeEvent(
            event_id="EVT-ETHICS",
            camera_id="CAM-01",
            timestamp=datetime(2026, 10, 7, 23, 50),
            object_type="person",
            confidence=0.95,
            zone_type="CORE",
            patrol_authorized=False,
        )

        assessment = self.engine.evaluate(event)
        full_text = " ".join(assessment.reasons) + " " + assessment.recommended_action
        for term in forbidden_terms:
            self.assertNotIn(term, full_text.lower(), f"Forbidden label '{term}' found in output!")

        # Verify decision-support phrasing
        self.assertIn("review", assessment.recommended_action.lower())


if __name__ == "__main__":
    unittest.main()
