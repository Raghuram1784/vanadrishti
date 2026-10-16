"""Public API contracts; species scores are rankings only."""
from typing import Literal
from pydantic import BaseModel
from ml.pipeline.models import (
    Detection, Species, SpeciesCandidate, CandidateSignal, FrameAnalysisResult, ObjectType,
)

AlertStatus = Literal['NEW', 'REVIEWING', 'PATROL_ASSIGNED', 'FALSE_ALARM', 'ESCALATED', 'RESOLVED']


class Risk(BaseModel):
    score: int
    level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    alert: bool
    reasons: list[str]
    recommended_action: str


class AnalysisResponse(BaseModel):
    frame_analysis: FrameAnalysisResult | None = None
    event_id: str
    timestamp: str
    simulated: Literal[True] = True
    source: Literal['image', 'demo', 'live_camera']
    camera: dict
    detections: list[Detection]
    context: dict
    risk: Risk
    evidence_image_path: str | None = None
    evidence_image_url: str | None = None
    evidence_media_type: str | None = None
    policy: str | None = None


class AlertAction(BaseModel):
    action: AlertStatus


class AlertResponse(BaseModel):
    id: str
    timestamp: str
    camera_id: str
    simulated: Literal[True] = True
    risk_score: int
    risk_level: Literal['HIGH', 'CRITICAL']
    reasons: list[str]
    status: AlertStatus
    source: Literal['image', 'demo', 'live_camera'] | None = None
    evidence_image_url: str | None = None
    policy: str | None = None


class CameraPolicyRequest(BaseModel):
    policy: str


class CameraPolicyResponse(BaseModel):
    camera_id: str
    policy: str
    status: str = 'ok'


EventState = Literal['NEW', 'CONTINUATION', 'NO_DETECTION', 'UNCERTAIN_DETECTION']
SessionStatus = Literal['ONLINE', 'DEGRADED', 'OFFLINE']


class CreateSessionRequest(BaseModel):
    device_name: str = 'Laptop Webcam'
    device_type: str = 'laptop_webcam'


class HeartbeatRequest(BaseModel):
    session_id: str


class CameraSessionResponse(BaseModel):
    camera_id: str
    session_id: str
    device_name: str
    device_type: str
    connected_at: str
    last_seen: str
    last_frame_at: str | None = None
    frames_received: int = 0
    frames_analyzed: int = 0
    status: SessionStatus


class RecentActivity(BaseModel):
    active: bool = False
    type: str | None = None
    last_confirmed_at: str | None = None
    last_event_id: str | None = None
    last_risk_level: str | None = None
    last_risk_score: int | None = None
    last_risk_alert: bool | None = None
    last_risk_reasons: list[str] | None = None
    last_recommended_action: str | None = None
    seconds_since_last_confirmed: float | None = None
    monitoring_status: str | None = None


class LiveFrameResponse(BaseModel):
    frame_analysis: FrameAnalysisResult | None = None
    event_state: EventState
    event_id: str | None = None
    timestamp: str
    simulated: Literal[True] = True
    camera_id: str
    camera: dict
    detections: list[Detection]
    context: dict
    risk: Risk
    evidence_image_url: str | None = None
    session_id: str | None = None
    recent_activity: RecentActivity | None = None
    policy: str | None = None
