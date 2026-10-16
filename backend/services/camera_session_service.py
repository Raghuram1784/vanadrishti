"""
In-memory camera session and live event deduplication service for Phase 5A.
Browser/device connectivity status is dynamically calculated from heartbeat and frame intervals.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import os
from threading import RLock
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

ONLINE_THRESHOLD_SECONDS = 20.0
DEGRADED_THRESHOLD_SECONDS = 45.0
DEFAULT_DEDUPE_WINDOW_SECONDS = 20.0
DEFAULT_ACTIVITY_TTL_SECONDS = 15.0
LOCAL_TZ = timezone(timedelta(hours=5, minutes=30), 'Asia/Kolkata')


def current_ist() -> datetime:
    return datetime.now(LOCAL_TZ)


@dataclass
class LiveSession:
    camera_id: str
    session_id: str
    device_name: str
    device_type: str
    connected_at: str
    last_seen: str
    last_seen_epoch: float
    last_frame_at: Optional[str] = None
    frames_received: int = 0
    frames_analyzed: int = 0
    is_closed: bool = False

    def compute_status(self, now_epoch: Optional[float] = None) -> str:
        if self.is_closed:
            return "OFFLINE"
        current_time = now_epoch if now_epoch is not None else time.time()
        elapsed = current_time - self.last_seen_epoch
        if elapsed <= ONLINE_THRESHOLD_SECONDS:
            return "ONLINE"
        elif elapsed <= DEGRADED_THRESHOLD_SECONDS:
            return "DEGRADED"
        return "OFFLINE"

    def to_dict(self, now_epoch: Optional[float] = None) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "session_id": self.session_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "connected_at": self.connected_at,
            "last_seen": self.last_seen,
            "last_frame_at": self.last_frame_at,
            "frames_received": self.frames_received,
            "frames_analyzed": self.frames_analyzed,
            "status": self.compute_status(now_epoch),
        }


class CameraSessionService:
    def __init__(
        self,
        online_threshold: float = ONLINE_THRESHOLD_SECONDS,
        degraded_threshold: float = DEGRADED_THRESHOLD_SECONDS,
        dedupe_window: float = DEFAULT_DEDUPE_WINDOW_SECONDS,
        activity_ttl: Optional[float] = None,
    ):
        self.online_threshold = online_threshold
        self.degraded_threshold = degraded_threshold
        self.dedupe_window = dedupe_window
        self.activity_ttl = float(
            activity_ttl if activity_ttl is not None else
            os.environ.get("VANADRISHTI_ACTIVITY_TTL_SECONDS", str(DEFAULT_ACTIVITY_TTL_SECONDS))
        )
        self.lock = RLock()
        self._sessions: Dict[str, LiveSession] = {}
        self._dedupe_state: Dict[str, Dict[str, Any]] = {}
        # Rolling class-level history per camera_id for temporal consistency: List[set[str]]
        self._sample_history: Dict[str, List[set]] = {}
        # Camera-level ongoing activity state: { camera_id: { activity_type, last_confirmed_at, last_event_id, ... } }
        self._activity_state: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        camera_id: str,
        device_name: str = "Laptop Webcam",
        device_type: str = "laptop_webcam",
    ) -> Dict[str, Any]:
        with self.lock:
            # If an existing session for this camera is active, close it
            for session in self._sessions.values():
                if session.camera_id == camera_id and not session.is_closed:
                    session.is_closed = True

            session_id = str(uuid4())
            now_dt = current_ist()
            now_iso = now_dt.isoformat()
            now_epoch = time.time()

            session = LiveSession(
                camera_id=camera_id,
                session_id=session_id,
                device_name=device_name,
                device_type=device_type,
                connected_at=now_iso,
                last_seen=now_iso,
                last_seen_epoch=now_epoch,
                frames_received=0,
                frames_analyzed=0,
                is_closed=False,
            )
            self._sessions[session_id] = session
            return session.to_dict(now_epoch)

    def heartbeat(self, camera_id: str, session_id: str) -> Dict[str, Any]:
        with self.lock:
            session = self._sessions.get(session_id)
            if not session or session.camera_id != camera_id:
                raise KeyError(f"Session {session_id} not found for camera {camera_id}")
            now_dt = current_ist()
            now_epoch = time.time()
            session.last_seen = now_dt.isoformat()
            session.last_seen_epoch = now_epoch
            session.is_closed = False
            return session.to_dict(now_epoch)

    def record_frame_received(
        self,
        camera_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        with self.lock:
            now_dt = current_ist()
            now_epoch = time.time()
            session = self._sessions.get(session_id) if session_id else None
            if not session:
                for s in self._sessions.values():
                    if s.camera_id == camera_id and not s.is_closed:
                        session = s
                        break
            if session:
                session.frames_received += 1
                session.last_frame_at = now_dt.isoformat()
                session.last_seen = now_dt.isoformat()
                session.last_seen_epoch = now_epoch

    def record_frame_analyzed(
        self,
        camera_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        with self.lock:
            now_dt = current_ist()
            now_epoch = time.time()
            session = self._sessions.get(session_id) if session_id else None
            if not session:
                for s in self._sessions.values():
                    if s.camera_id == camera_id and not s.is_closed:
                        session = s
                        break
            if session:
                session.frames_analyzed += 1
                session.last_frame_at = now_dt.isoformat()
                session.last_seen = now_dt.isoformat()
                session.last_seen_epoch = now_epoch

    def close_session(self, camera_id: str, session_id: str) -> Dict[str, Any]:
        with self.lock:
            session = self._sessions.get(session_id)
            if not session or session.camera_id != camera_id:
                raise KeyError(f"Session {session_id} not found for camera {camera_id}")
            session.is_closed = True
            return {
                "message": "Session closed",
                "session_id": session_id,
                "camera_id": camera_id,
                "status": "OFFLINE",
            }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            session = self._sessions.get(session_id)
            return session.to_dict() if session else None

    def get_active_session_for_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            for session in reversed(list(self._sessions.values())):
                if session.camera_id == camera_id:
                    return session.to_dict()
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self.lock:
            now_epoch = time.time()
            return [s.to_dict(now_epoch) for s in self._sessions.values()]

    def check_deduplication(
        self,
        camera_id: str,
        detections: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
        window_seconds: Optional[float] = None,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Evaluate if detections constitute a CONTINUATION of a recent active event.
        Returns:
            (is_continuation, event_id, primary_category, primary_species, evidence_url)
        """
        if not detections:
            return False, None, None, None, None

        window = window_seconds if window_seconds is not None else self.dedupe_window
        now = current_time or current_ist()
        if now.tzinfo is None:
            now = now.replace(tzinfo=LOCAL_TZ)

        # Determine primary object: priority person (highest risk) > vehicle > animal
        priority_map = {"person": 3, "vehicle": 2, "animal": 1}
        sorted_detections = sorted(
            detections,
            key=lambda d: (priority_map.get(d.get("type", ""), 0), d.get("score", 0.0)),
            reverse=True,
        )
        primary = sorted_detections[0]
        category = primary.get("type", "animal")
        species_info = primary.get("species") or {}
        species = species_info.get("top1") if category == "animal" else None

        with self.lock:
            last = self._dedupe_state.get(camera_id)
            if last:
                last_ts = last["timestamp"]
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=LOCAL_TZ)
                elapsed = (now - last_ts).total_seconds()

                if 0 <= elapsed <= window:
                    # Same primary category required
                    if last["category"] == category:
                        # For animals, match top species if known
                        species_match = True
                        if category == "animal" and last.get("species") and species:
                            species_match = (last["species"].lower() == species.lower())

                        if species_match:
                            # Continuation confirmed: update timestamp to slide window
                            last["timestamp"] = now
                            return True, last["event_id"], category, species, last.get("evidence_url")

            return False, None, category, species, None

    def record_new_event(
        self,
        camera_id: str,
        event_id: str,
        category: str,
        species: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        evidence_url: Optional[str] = None,
    ) -> None:
        with self.lock:
            now = timestamp or current_ist()
            if now.tzinfo is None:
                now = now.replace(tzinfo=LOCAL_TZ)
            self._dedupe_state[camera_id] = {
                "event_id": event_id,
                "timestamp": now,
                "category": category,
                "species": species,
                "evidence_url": evidence_url,
            }

    def check_temporal_consistency(
        self,
        camera_id: str,
        class_name: str,
        confidence: float,
        threshold: float = 0.35,
        window_samples: int = 3,
        required_count: int = 2,
    ) -> Tuple[bool, str]:
        """
        Conservative class-level temporal consistency for weak ambiguous detections.
        If confidence >= threshold: immediately confirmed.
        If confidence < threshold: requires class presence in at least (required_count)
        of the last (window_samples) samples before creating a meaningful event.
        Does NOT identify individuals or claim 'same person' / 'same animal'.
        """
        if confidence >= threshold:
            return True, ""

        with self.lock:
            history = self._sample_history.get(camera_id, [])
            # Count prior samples containing this class within recent history
            prior_matches = sum(1 for classes in history[-(window_samples - 1):] if class_name in classes)
            total_matches = prior_matches + 1
            if total_matches >= required_count:
                return True, ""
            return False, (
                f"Preliminary weak detection (score {confidence:.4f}); "
                f"awaiting class-level confirmation ({total_matches}/{required_count} samples)."
            )

    def record_sample_classes(
        self,
        camera_id: str,
        detected_classes: set,
        max_history: int = 5,
    ) -> None:
        """Record class-level evidence for a sample frame in rolling history."""
        with self.lock:
            if camera_id not in self._sample_history:
                self._sample_history[camera_id] = []
            self._sample_history[camera_id].append(set(detected_classes))
            if len(self._sample_history[camera_id]) > max_history:
                self._sample_history[camera_id] = self._sample_history[camera_id][-max_history:]

    def record_confirmed_activity(
        self,
        camera_id: str,
        activity_type: str,
        event_id: str,
        risk_level: str = "LOW",
        risk_score: int = 0,
        risk_alert: bool = False,
        risk_reasons: Optional[List[str]] = None,
        recommended_action: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        evidence_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a confirmed detection event as recent camera activity.
        Only refreshed by confirmed detections (never by weak/uncertain ones).
        """
        with self.lock:
            now = timestamp or current_ist()
            if now.tzinfo is None:
                now = now.replace(tzinfo=LOCAL_TZ)
            state = {
                "activity_type": activity_type,
                "last_confirmed_at": now,
                "last_event_id": event_id,
                "last_risk_level": risk_level,
                "last_risk_score": risk_score,
                "last_risk_alert": risk_alert,
                "last_risk_reasons": risk_reasons or [],
                "last_recommended_action": recommended_action or "",
                "last_evidence_url": evidence_url,
            }
            self._activity_state[camera_id] = state
            return self._format_activity_dict(camera_id, state, now)

    def get_recent_activity(
        self,
        camera_id: str,
        current_time: Optional[datetime] = None,
        ttl_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve recent camera-level ongoing activity state.
        Activity remains active within TTL even if the latest individual sample misses.
        """
        with self.lock:
            state = self._activity_state.get(camera_id)
            now = current_time or current_ist()
            if now.tzinfo is None:
                now = now.replace(tzinfo=LOCAL_TZ)
            return self._format_activity_dict(camera_id, state, now, ttl_seconds)

    def _format_activity_dict(
        self,
        camera_id: str,
        state: Optional[Dict[str, Any]],
        now: datetime,
        ttl_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not state:
            return {"active": False}

        last_dt = state["last_confirmed_at"]
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=LOCAL_TZ)

        elapsed = max(0.0, (now - last_dt).total_seconds())
        ttl = ttl_seconds if ttl_seconds is not None else self.activity_ttl

        act_type = state["activity_type"]
        is_active = elapsed <= ttl

        return {
            "active": is_active,
            "type": act_type,
            "last_confirmed_at": last_dt.isoformat(),
            "last_event_id": state.get("last_event_id"),
            "last_risk_level": state.get("last_risk_level", "LOW"),
            "last_risk_score": state.get("last_risk_score", 0),
            "last_risk_alert": state.get("last_risk_alert", False),
            "last_risk_reasons": state.get("last_risk_reasons") or [],
            "last_recommended_action": state.get("last_recommended_action") or "",
            "seconds_since_last_confirmed": round(elapsed, 1),
            "monitoring_status": (
                f"{act_type.capitalize()} activity observed recently · Monitoring continues"
                if is_active
                else "Activity ended (TTL expired) · Monitoring continues"
            ),
        }

    def clear_camera_dedupe(self, camera_id: str) -> None:
        with self.lock:
            self._dedupe_state.pop(camera_id, None)
            self._sample_history.pop(camera_id, None)
            self._activity_state.pop(camera_id, None)
