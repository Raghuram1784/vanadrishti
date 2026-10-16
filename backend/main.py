"""Run from the repository root: uvicorn backend.main:app --reload."""
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api import health, cameras, analyze, events, alerts, demo, evidence, live
from backend.db.database import Repository
from backend.services.context_service import ContextService, ROOT
from backend.services.vision_service import get_vision_service
from backend.services.evidence_service import EvidenceStore
from backend.services.live_service import LiveHub
from backend.services.camera_session_service import CameraSessionService


def create_app(db_path=None, vision_service=None, evidence_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        database_path = Path(db_path or os.environ.get('VANADRISHTI_DB', ROOT / 'data/vanadrishti.db'))
        app.state.live = LiveHub()
        repository = Repository(database_path, publish=app.state.live.publish)
        app.state.repository = repository
        try:
            app.state.evidence = EvidenceStore(evidence_dir or os.environ.get('VANADRISHTI_EVIDENCE_DIR', database_path.parent / 'evidence'))
            app.state.context = ContextService(repository, app.state.evidence)
            app.state.vision = vision_service if vision_service is not None else get_vision_service()
            app.state.sessions = CameraSessionService()
            yield
        finally:
            await app.state.live.close()
            repository.close()

    app = FastAPI(title='VanaDrishti API', version='0.1.0', lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
                       allow_origin_regex=r"^https?://.*",
                       allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                       allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'], allow_headers=['*'])
    for module in (health, cameras, analyze, events, alerts, demo, evidence, live):
        app.include_router(module.router)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logging.getLogger(__name__).error('API request failed', exc_info=error)
        return JSONResponse(status_code=500, content={'detail': 'Internal service error; check server logs'})

    return app


app = create_app()
