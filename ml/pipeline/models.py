"""Shared frame-level contracts; no camera-session or risk state."""
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

ObjectType = Literal['animal', 'person', 'vehicle']


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


class FrameStatus(str, Enum):
    CONFIRMED_DETECTION = 'CONFIRMED_DETECTION'
    UNCERTAIN_DETECTION = 'UNCERTAIN_DETECTION'
    NO_DETECTION = 'NO_DETECTION'
    DEGRADED_FRAME = 'DEGRADED_FRAME'
    INVALID_FRAME = 'INVALID_FRAME'
    INFERENCE_ERROR = 'INFERENCE_ERROR'


class QualityStatus(str, Enum):
    GOOD = 'GOOD'
    DEGRADED = 'DEGRADED'
    UNUSABLE = 'UNUSABLE'


class QualityFlag(str, Enum):
    TOO_DARK = 'TOO_DARK'
    OVEREXPOSED = 'OVEREXPOSED'
    BLURRED = 'BLURRED'
    LOW_CONTRAST = 'LOW_CONTRAST'
    POSSIBLE_OBSTRUCTION = 'POSSIBLE_OBSTRUCTION'


class ImageQuality(BaseModel):
    status: QualityStatus
    brightness: float
    contrast: float
    blur_score: float
    near_black_ratio: float
    near_white_ratio: float
    possible_obstruction: bool = False
    flags: list[QualityFlag] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class FrameAnalysisResult(BaseModel):
    camera_id: str
    captured_at: datetime
    processing_ms: float = Field(ge=0)
    status: FrameStatus
    detections: list[Detection] = Field(default_factory=list)
    image_quality: ImageQuality | None = None
    warnings: list[str] = Field(default_factory=list)
