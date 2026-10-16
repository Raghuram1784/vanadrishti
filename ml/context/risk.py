"""
VanaDrishti Phase 3: Explainable Wildlife Security Risk Engine.

Evaluates surveillance events deterministically against spatial, temporal,
and ecological context without automated accusations or black-box risk scores.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ml.context.engine import ContextEngine
from ml.context.models import CameraContext, RiskAssessment, WildlifeEvent

logger = logging.getLogger("vanadrishti.risk")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Default rule weights if config file is not provided
DEFAULT_WEIGHTS = {
    "person": {
        "base_detection": 25,
        "zone_core": 30,
        "zone_restricted": 20,
        "outside_allowed_hours": 20,
        "patrol_unauthorized": 20,
        "repeated_activity": 10,
    },
    "vehicle": {
        "base_detection": 20,
        "zone_core": 30,
        "zone_restricted": 20,
        "outside_allowed_hours": 20,
        "patrol_unauthorized": 15,
        "repeated_activity": 10,
    },
    "wildlife_context": {
        "recent_high_value_wildlife_nearby": 15,
        "recent_animal_activity_prior": 10,
    },
}

DEFAULT_HIGH_VALUE_SPECIES = [
    "tiger",
    "bengal_tiger",
    "leopard",
    "indian_leopard",
    "sloth_bear",
    "gaur",
]


class RiskEngine:
    """
    Deterministic Wildlife Security Risk Assessment Engine.

    Evaluates circumstances surrounding automated vision detections:
    - Object classification (person, vehicle, animal)
    - Protected forest zone type (CORE, RESTRICTED, BUFFER, PUBLIC)
    - Permitted operating schedule
    - Active ranger patrol authorization
    - Prior wildlife presence and animal movement
    - Multi-camera spatial correlation

    ETHICAL GUARANTEES:
    - Never uses terms 'poacher', 'criminal', or 'illegal hunter'.
    - Does not classify or evaluate human faces, clothing, or appearance.
    - Every score increment produces a human-readable explanation.
    - All output actions are ranger decision support, never automated enforcement.
    """

    def __init__(
        self,
        context_engine: Optional[ContextEngine] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.context = context_engine or ContextEngine.create_default()
        self.config = self._load_config(config_path)

        self.weights = self.config.get("scoring_weights", DEFAULT_WEIGHTS)
        self.high_value_species = self.config.get("high_value_species", DEFAULT_HIGH_VALUE_SPECIES)
        self.time_windows = self.config.get(
            "time_windows",
            {
                "repeated_activity_minutes": 30,
                "recent_wildlife_minutes": 60,
                "prior_animal_minutes": 30,
            },
        )
        self.max_distance = float(
            self.config.get("proximity_meters", {}).get("nearby_camera_max_distance", 1500.0)
        )

    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load risk rules from JSON configuration."""
        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as err:
                logger.warning("Failed to load risk rules from %s: %s", config_path, err)

        # Fallback to default project config
        default_path = Path(__file__).resolve().parent.parent.parent / "config" / "risk_rules.json"
        if default_path.exists():
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {}

    def get_risk_level_info(self, score: int) -> Tuple[str, bool, str]:
        """
        Map numerical score (0-100) to level name, alert flag, and recommended action.

        Boundaries:
        0-24   LOW
        25-49  MEDIUM
        50-74  HIGH
        75+    CRITICAL
        """
        if score >= 75:
            return (
                "CRITICAL",
                True,
                "Review evidence immediately and dispatch rapid response patrol.",
            )
        elif score >= 50:
            return (
                "HIGH",
                True,
                "Review camera footage and alert nearest field patrol.",
            )
        elif score >= 25:
            return (
                "MEDIUM",
                True,
                "Monitor camera feed and log event on ranger dashboard.",
            )
        else:
            return (
                "LOW",
                False,
                "Log event for wildlife monitoring.",
            )

    def evaluate(
        self,
        event: WildlifeEvent,
        camera: Optional[CameraContext] = None,
    ) -> RiskAssessment:
        """
        Evaluate a wildlife or security event deterministically.

        Args:
            event: The WildlifeEvent to assess.
            camera: Optional CameraContext override (defaults to camera registry lookup).

        Returns:
            RiskAssessment with score, level, alert flag, reasons, and decision-support action.
        """
        cam = camera or self.context.cameras.get(event.camera_id)
        zone_type = (event.zone_type or (cam.zone_type if cam else "BUFFER")).upper()
        patrol_auth = event.patrol_authorized if event.patrol_authorized else (cam.patrol_authorized if cam else False)

        reasons: List[str] = []
        score: int = 0

        # RULE GROUP 1: ANIMAL EVENTS
        # Animals themselves are normal biological events and do not generate security alarms
        if event.object_type == "animal":
            sp_name = event.species or "Wildlife"
            reasons.append(f"{sp_name} detected (normal ecological activity)")
            # Record into context memory for subsequent correlation
            self.context.events.add_event(event)
            return RiskAssessment(
                event_id=event.event_id,
                risk_score=0,
                risk_level="LOW",
                alert=False,
                reasons=reasons,
                recommended_action="Log event for wildlife monitoring.",
            )

        # RULE GROUP 2: PERSON DETECTIONS
        elif event.object_type == "person":
            w = self.weights.get("person", DEFAULT_WEIGHTS["person"])
            score += w.get("base_detection", 25)
            reasons.append("Person detected")

            # Zone rules
            if zone_type == "CORE":
                score += w.get("zone_core", 30)
                reasons.append("Camera is in CORE protected zone")
            elif zone_type == "RESTRICTED":
                score += w.get("zone_restricted", 20)
                reasons.append("Camera is in RESTRICTED zone")

            # Operating hours check
            if cam and not cam.is_time_allowed(event.timestamp):
                score += w.get("outside_allowed_hours", 20)
                reasons.append("Activity occurred outside allowed hours")

            # Patrol authorization
            if not patrol_auth:
                score += w.get("patrol_unauthorized", 20)
                reasons.append("No authorized patrol active in sector")

            # Repeated activity at this camera
            rep_mins = self.time_windows.get("repeated_activity_minutes", 30)
            rep_count = self.context.events.count_repeated_events(
                object_type="person",
                camera_id=event.camera_id,
                minutes=rep_mins,
                before_time=event.timestamp,
            )
            if rep_count > 0:
                score += w.get("repeated_activity", 10)
                reasons.append(f"Repeated person activity recorded within {rep_mins} minutes")

        # RULE GROUP 3: VEHICLE DETECTIONS
        elif event.object_type == "vehicle":
            w = self.weights.get("vehicle", DEFAULT_WEIGHTS["vehicle"])
            score += w.get("base_detection", 20)
            reasons.append("Vehicle detected")

            # Zone rules
            if zone_type == "CORE":
                score += w.get("zone_core", 30)
                reasons.append("Camera is in CORE protected zone")
            elif zone_type == "RESTRICTED":
                score += w.get("zone_restricted", 20)
                reasons.append("Camera is in RESTRICTED zone")

            # Operating hours check
            if cam and not cam.is_time_allowed(event.timestamp):
                score += w.get("outside_allowed_hours", 20)
                reasons.append("Activity occurred outside allowed hours")

            # Patrol authorization
            if not patrol_auth:
                score += w.get("patrol_unauthorized", 15)
                reasons.append("No authorized patrol active in sector")

            # Repeated activity
            rep_mins = self.time_windows.get("repeated_activity_minutes", 30)
            rep_count = self.context.events.count_repeated_events(
                object_type="vehicle",
                camera_id=event.camera_id,
                minutes=rep_mins,
                before_time=event.timestamp,
            )
            if rep_count > 0:
                score += w.get("repeated_activity", 10)
                reasons.append(f"Repeated vehicle activity recorded within {rep_mins} minutes")

        # RULE GROUP 4: WILDLIFE CONTEXT FOR HUMAN / VEHICULAR ACTIVITY
        if event.object_type in ("person", "vehicle"):
            w_ctx = self.weights.get("wildlife_context", DEFAULT_WEIGHTS["wildlife_context"])

            # Check 1: High-value wildlife activity nearby (e.g. tiger, leopard)
            wl_mins = self.time_windows.get("recent_wildlife_minutes", 60)
            recent_high_val = self.context.events.get_recent_wildlife_events(
                camera_id=event.camera_id,
                camera_registry=self.context.cameras,
                minutes=wl_mins,
                max_distance_meters=self.max_distance,
                high_value_species=self.high_value_species,
                before_time=event.timestamp,
            )
            if recent_high_val:
                sp_detected = recent_high_val[0][0].species or "high-value wildlife"
                score += w_ctx.get("recent_high_value_wildlife_nearby", 15)
                reasons.append(f"Recent {sp_detected} activity recorded nearby")

            # Check 2: Any animal activity shortly before (e.g. within 30 mins)
            prior_mins = self.time_windows.get("prior_animal_minutes", 30)
            prior_animals = self.context.events.get_recent_wildlife_events(
                camera_id=event.camera_id,
                camera_registry=self.context.cameras,
                minutes=prior_mins,
                max_distance_meters=self.max_distance,
                high_value_species=None,
                before_time=event.timestamp,
            )
            if prior_animals:
                score += w_ctx.get("recent_animal_activity_prior", 10)
                reasons.append("Recent animal activity occurred shortly before event")

            # Check 3: Multi-camera spatial correlation (for record / explanation)
            correlations = self.context.events.find_correlated_nearby_activity(
                target_event=event,
                camera_registry=self.context.cameras,
                max_distance_meters=self.max_distance,
                minutes=30,
            )
            if correlations:
                event.recent_related_events.extend(correlations)
                for corr in correlations[:2]:
                    reasons.append(corr["description"])

        # Cap score between 0 and 100
        final_score = min(100, max(0, score))
        risk_level, alert, action = self.get_risk_level_info(final_score)

        # Store current event into event memory for future context
        self.context.events.add_event(event)

        return RiskAssessment(
            event_id=event.event_id,
            risk_score=final_score,
            risk_level=risk_level,
            alert=alert,
            reasons=reasons,
            recommended_action=action,
        )
