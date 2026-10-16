from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix='/api/evidence', tags=['evidence'])


@router.get('/{event_id}')
def evidence(event_id: str, request: Request):
    try:
        # Never use a request path or uploaded filename to locate a disk file.
        if str(UUID(event_id)) != event_id:
            raise ValueError('Invalid event ID')
        event = request.app.state.repository.event(event_id)
        relative = event.get('evidence_image_path')
        if not relative:
            raise KeyError(event_id)
        path = request.app.state.evidence.resolve(relative)
        if not path.is_file():
            raise KeyError(event_id)
    except (KeyError, ValueError, OSError):
        raise HTTPException(404, 'No stored image evidence for this event.') from None
    return FileResponse(path, media_type=event.get('evidence_media_type', 'application/octet-stream'),
                        headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=3600'})
