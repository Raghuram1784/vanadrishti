from datetime import datetime
import logging
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from backend.api.analyze import decode_image
from backend.services.context_service import camera_payload, DISCLAIMER, local_timestamp
from backend.schemas.api import (
    CreateSessionRequest,
    HeartbeatRequest,
    CameraSessionResponse,
    LiveFrameResponse,
)

router = APIRouter(tags=['cameras'])


@router.get('/api/cameras')
def cameras(request: Request):
    return {'simulated': True, 'disclaimer': DISCLAIMER,
            'cameras': [camera_payload(c) for c in request.app.state.context.context.cameras.list_all()]}


@router.get('/api/camera-sessions', response_model=list[CameraSessionResponse])
@router.get('/api/cameras/sessions', response_model=list[CameraSessionResponse], include_in_schema=False)
def list_sessions(request: Request):
    sessions = getattr(request.app.state, 'sessions', None)
    if not sessions:
        return []
    return sessions.list_sessions()


@router.post('/api/cameras/{camera_id}/session', response_model=CameraSessionResponse)
def create_session(camera_id: str, request: Request, body: CreateSessionRequest | None = None):
    try:
        request.app.state.context.camera(camera_id)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None

    sessions = request.app.state.sessions
    device_name = body.device_name if body else 'Laptop Webcam'
    device_type = body.device_type if body else 'laptop_webcam'
    return sessions.create_session(camera_id, device_name=device_name, device_type=device_type)


@router.post('/api/cameras/{camera_id}/heartbeat', response_model=CameraSessionResponse)
def heartbeat(camera_id: str, body: HeartbeatRequest, request: Request):
    try:
        request.app.state.context.camera(camera_id)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None

    sessions = request.app.state.sessions
    try:
        return sessions.heartbeat(camera_id, body.session_id)
    except KeyError:
        raise HTTPException(404, 'Session not found for camera') from None


@router.delete('/api/cameras/{camera_id}/session/{session_id}')
def close_session(camera_id: str, session_id: str, request: Request):
    try:
        request.app.state.context.camera(camera_id)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None

    sessions = request.app.state.sessions
    try:
        return sessions.close_session(camera_id, session_id)
    except KeyError:
        raise HTTPException(404, 'Session not found for camera') from None


@router.get('/api/cameras/{camera_id}/session', response_model=CameraSessionResponse | None)
def get_camera_session(camera_id: str, request: Request):
    try:
        request.app.state.context.camera(camera_id)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None

    sessions = request.app.state.sessions
    active = sessions.get_active_session_for_camera(camera_id)
    if not active:
        raise HTTPException(404, 'No active session for camera')
    return active


@router.post('/api/cameras/{camera_id}/frame', response_model=LiveFrameResponse)
def live_frame(
    camera_id: str,
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    timestamp: str | None = Form(None),
    authorized_patrol: bool | None = Form(None),
):
    try:
        camera = request.app.state.context.camera(camera_id)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None

    parsed_time = None
    if timestamp is not None:
        try:
            if 'T' not in timestamp and ' ' not in timestamp:
                raise ValueError('Date without time')
            parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(422, 'Invalid timestamp; use an ISO datetime') from None

    ts = local_timestamp(parsed_time)
    frame, raw_bytes = decode_image(file)

    sessions = getattr(request.app.state, 'sessions', None)
    if sessions:
        sessions.record_frame_received(camera_id, session_id=session_id)

    try:
        detections = request.app.state.vision.analyze(frame)
    except Exception:
        logging.getLogger(__name__).exception('Vision inference failed on live frame')
        raise HTTPException(503, 'Vision model unavailable or inference failed') from None

    if sessions:
        sessions.record_frame_analyzed(camera_id, session_id=session_id)
        # Apply conservative class-level temporal consistency for weak detections (< 0.35)
        for d in detections:
            if not d.get('uncertain') and d.get('score', 1.0) < 0.35:
                is_consistent, reason = sessions.check_temporal_consistency(
                    camera_id, d.get('type', 'animal'), d.get('score', 0.0)
                )
                if not is_consistent:
                    d['uncertain'] = True
                    d['uncertainty_reason'] = reason

        # Record detected classes in rolling sample history
        sample_classes = {d['type'] for d in detections if d.get('type')}
        sessions.record_sample_classes(camera_id, sample_classes)

    # 1. NO DETECTION / UNCERTAIN DETECTION: Return analysis without persisting event or evidence
    confirmed = [d for d in detections if not d.get('uncertain')]
    if not confirmed:
        recent_activity = sessions.get_recent_activity(camera_id, current_time=ts) if sessions else None
        return LiveFrameResponse(
            event_state='UNCERTAIN_DETECTION' if detections else 'NO_DETECTION',
            event_id=None,
            timestamp=ts.isoformat(),
            simulated=True,
            camera_id=camera_id,
            camera=camera_payload(camera),
            detections=detections,
            context={
                'zone': camera.zone_type,
                'hour': ts.hour,
                'timezone': 'Asia/Kolkata',
                'simulated': True,
                'authorized_patrol': camera.patrol_authorized if authorized_patrol is None else authorized_patrol,
                'recent_wildlife_events': [],
            },
            risk={
                'score': 0,
                'level': 'LOW',
                'alert': False,
                'reasons': ['Uncertain object evidence; species not classified.'] if detections else ['No retained detections.'],
                'recommended_action': 'Additional observation recommended.' if detections else 'Continue observation.',
            },
            evidence_image_url=None,
            session_id=session_id,
            recent_activity=recent_activity,
        )

    # 2. MEANINGFUL DETECTION: Check deduplication
    is_continuation, existing_event_id, primary_category, primary_species, evidence_url = (
        False, None, None, None, None
    )
    if sessions:
        is_continuation, existing_event_id, primary_category, primary_species, evidence_url = (
            sessions.check_deduplication(camera_id, confirmed, current_time=ts)
        )

    if is_continuation and existing_event_id:
        # CONTINUATION: Evaluate context/risk for display only; do NOT persist new event or alert
        assessment = request.app.state.context.assess_only(
            detections, camera_id, ts, authorized_patrol, source='live_camera'
        )
        recent_activity = sessions.record_confirmed_activity(
            camera_id=camera_id,
            activity_type=primary_category or 'animal',
            event_id=existing_event_id,
            risk_level=assessment['risk']['level'],
            risk_score=assessment['risk']['score'],
            risk_alert=assessment['risk']['alert'],
            risk_reasons=assessment['risk']['reasons'],
            recommended_action=assessment['risk']['recommended_action'],
            timestamp=ts,
            evidence_url=evidence_url,
        ) if sessions else None

        return LiveFrameResponse(
            event_state='CONTINUATION',
            event_id=existing_event_id,
            timestamp=assessment['timestamp'],
            simulated=True,
            camera_id=camera_id,
            camera=assessment['camera'],
            detections=assessment['detections'],
            context=assessment['context'],
            risk=assessment['risk'],
            evidence_image_url=evidence_url,
            session_id=session_id,
            recent_activity=recent_activity,
        )

    # 3. NEW MEANINGFUL ACTIVITY: Persist event and evidence, notify WebSockets if alert
    entry = request.app.state.context.analyze(
        detections, camera_id, ts, authorized_patrol, evidence_bytes=raw_bytes, source='live_camera'
    )
    if sessions and primary_category:
        sessions.record_new_event(
            camera_id,
            entry['event_id'],
            primary_category,
            primary_species,
            timestamp=ts,
            evidence_url=entry.get('evidence_image_url'),
        )
    recent_activity = sessions.record_confirmed_activity(
        camera_id=camera_id,
        activity_type=primary_category or 'animal',
        event_id=entry['event_id'],
        risk_level=entry['risk']['level'],
        risk_score=entry['risk']['score'],
        risk_alert=entry['risk']['alert'],
        risk_reasons=entry['risk']['reasons'],
        recommended_action=entry['risk']['recommended_action'],
        timestamp=ts,
        evidence_url=entry.get('evidence_image_url'),
    ) if sessions else None

    return LiveFrameResponse(
        event_state='NEW',
        event_id=entry['event_id'],
        timestamp=entry['timestamp'],
        simulated=True,
        camera_id=camera_id,
        camera=entry['camera'],
        detections=entry['detections'],
        context=entry['context'],
        risk=entry['risk'],
        evidence_image_url=entry.get('evidence_image_url'),
        session_id=session_id,
        recent_activity=recent_activity,
    )


@router.get('/api/cameras/{camera_id}')
def camera(camera_id: str, request: Request):
    try:
        return camera_payload(request.app.state.context.camera(camera_id))
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None
