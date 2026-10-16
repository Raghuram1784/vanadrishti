from fastapi import APIRouter, HTTPException, Request
from backend.schemas.api import AlertAction, AlertResponse

router = APIRouter(prefix='/api/alerts', tags=['alerts'])


@router.get('', response_model=list[AlertResponse])
def alerts(request: Request, include_resolved: bool = False):
    return request.app.state.repository.alerts(include_resolved)


@router.post('/{alert_id}/action', response_model=AlertResponse)
def action(alert_id: str, body: AlertAction, request: Request):
    try:
        return request.app.state.repository.action(alert_id, body.action)
    except KeyError:
        raise HTTPException(404, 'Unknown alert') from None
    except ValueError:
        raise HTTPException(409, 'Invalid alert status transition') from None
