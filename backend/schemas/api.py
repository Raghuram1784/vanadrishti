"""Public API contracts; species scores are rankings only."""
from typing import Literal
from pydantic import BaseModel, Field

ObjectType = Literal['animal', 'person', 'vehicle']
AlertStatus = Literal['NEW', 'REVIEWING', 'PATROL_ASSIGNED', 'FALSE_ALARM', 'ESCALATED', 'RESOLVED']


class SpeciesCandidate(BaseModel):
    label: str
    ranking_score: float


class Species(BaseModel):
    top1: str
    ranking_score: float
    top3: list[SpeciesCandidate]


class CandidateSignal(BaseModel):
    type: ObjectType
    score: float


class Detection(BaseModel):
    uncertain: bool = False
    uncertainty_reason: str | None = None
    candidate_signals: list[CandidateSignal] = Field(default_factory=list)
    type: ObjectType
    score: float
    bbox: list[float] | None = Field(default=None, description='Normalized x1,y1,x2,y2 coordinates')
    species: Species | None = None


class Risk(BaseModel):
    score: int
    level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    alert: bool
    reasons: list[str]
    recommended_action: str


class AnalysisResponse(BaseModel):
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
