from fastapi import APIRouter, Request

router = APIRouter()


@router.get('/health')
def health(request: Request):
    return {'status': 'ok', 'service': 'vanadrishti-api', **request.app.state.vision.status()}
