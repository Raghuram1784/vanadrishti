"""
VanaDrishti Phase 3: Context-Aware Wildlife Security Risk Engine.

Provides domain models, in-memory multi-camera event history, and deterministic
explainable risk assessment for wildlife protection.
"""

from ml.context.models import (
    CameraContext,
    WildlifeEvent,
    RiskAssessment,
)
from ml.context.engine import (
    CameraRegistry,
    EventStore,
    ContextEngine,
    haversine_distance_meters,
)
from ml.context.risk import (
    RiskEngine,
    DEFAULT_WEIGHTS,
)

__all__ = [
    "CameraContext",
    "WildlifeEvent",
    "RiskAssessment",
    "CameraRegistry",
    "EventStore",
    "ContextEngine",
    "RiskEngine",
    "haversine_distance_meters",
    "DEFAULT_WEIGHTS",
]
