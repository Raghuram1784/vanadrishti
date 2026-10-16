"""One frame contract for decoded images from any capture source."""
from datetime import datetime, timezone
from functools import lru_cache
from time import perf_counter
import logging
from .models import Detection, FrameAnalysisResult, FrameStatus, QualityStatus
from .quality import assess_quality, valid_frame


@lru_cache(maxsize=1)
def get_frame_analyzer():
    from .service import FrameAnalyzer
    return FrameAnalyzer()


def analyze_frame(frame, camera_id, metadata=None, *, inference=None, quality_config=None):
    """Analyze uint8 BGR pixels; metadata optionally supplies captured_at.

    Naive timestamps are interpreted as UTC. HTTP adapters normalize local time
    before calling. An injected legacy inference callable returns Detection dicts.
    Quality never suppresses retained detections or mutates session state.
    """
    started = perf_counter()
    captured_at = (metadata or {}).get('captured_at') or datetime.now(timezone.utc)
    if isinstance(captured_at, str):
        captured_at = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    result = FrameAnalysisResult(camera_id=camera_id, captured_at=captured_at,
                                 processing_ms=0, status=FrameStatus.INVALID_FRAME)
    try:
        if not valid_frame(frame):
            result.warnings.append('Expected a nonempty uint8 H x W x 3 BGR frame.')
            return result
        result.image_quality = assess_quality(frame, quality_config)
        if result.image_quality.status != QualityStatus.GOOD:
            result.warnings.append('Image quality degraded; a negative detection does not establish absence.')
        infer = inference if inference is not None else get_frame_analyzer().analyze
        result.detections = [Detection.model_validate(d) for d in infer(frame)]
        if any(not d.uncertain for d in result.detections):
            result.status = FrameStatus.CONFIRMED_DETECTION
        elif result.detections:
            result.status = FrameStatus.UNCERTAIN_DETECTION
        elif result.image_quality.status != QualityStatus.GOOD:
            result.status = FrameStatus.DEGRADED_FRAME
        else:
            result.status = FrameStatus.NO_DETECTION
    except Exception:
        logging.getLogger(__name__).exception('Frame inference failed')
        result.status = FrameStatus.INFERENCE_ERROR
        result.detections = []
        result.warnings.append('Inference unavailable or failed; this is not a negative detection.')
    finally:
        result.processing_ms = (perf_counter() - started) * 1000
    return result
