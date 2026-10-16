from fastapi import APIRouter, HTTPException, Query, Request
from backend.schemas.api import AnalysisResponse, ObjectType

router = APIRouter(prefix='/api/events', tags=['events'])


@router.get('', response_model=list[AnalysisResponse])
def events(request: Request, camera_id: str | None = None,
           event_type: ObjectType | None = None, limit: int = Query(100, ge=1, le=1000)):
    return request.app.state.repository.events(camera_id, event_type, limit)


@router.get('/{event_id}', response_model=AnalysisResponse)
def event(event_id: str, request: Request):
    try:
        return request.app.state.repository.event(event_id)
    except KeyError:
        raise HTTPException(404, 'Unknown event') from None
