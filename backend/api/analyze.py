from datetime import datetime
from io import BytesIO
import logging
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from backend.schemas.api import AnalysisResponse
from backend.services.context_service import DEMO_CAMERA_ID

router = APIRouter(prefix='/api', tags=['analysis'])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 25_000_000


def decode_image(file):
    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'):
        raise HTTPException(415, 'Unsupported file; upload a JPEG, PNG, WebP, BMP, or TIFF image')
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'Image exceeds 20 MiB upload limit')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP', 'BMP', 'TIFF'):
                    raise HTTPException(415, 'Unsupported image format')
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(413, 'Image exceeds 25 megapixel limit')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                rgb = np.array(ImageOps.exif_transpose(image).convert('RGB'))
                return rgb[:, :, ::-1].copy(), data
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise HTTPException(422, 'Corrupt or invalid image') from None


@router.post('/analyze-image', response_model=AnalysisResponse)
def analyze_image(request: Request, file: UploadFile = File(...),
                  camera_id: str | None = Form(None), timestamp: str | None = Form(None),
                  authorized_patrol: bool | None = Form(None)):
    selected = camera_id or DEMO_CAMERA_ID
    try:
        request.app.state.context.camera(selected)
    except KeyError:
        raise HTTPException(404, 'Unknown camera') from None
    parsed = None
    if timestamp is not None:
        try:
            if 'T' not in timestamp and ' ' not in timestamp:
                raise ValueError('Date without time')
            parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(422, 'Invalid timestamp; use an ISO datetime') from None
    frame, original_bytes = decode_image(file)
    try:
        detections = request.app.state.vision.analyze(frame)
    except Exception:
        logging.getLogger(__name__).exception('Vision inference failed')
        raise HTTPException(503, 'Vision model unavailable or inference failed; check server logs') from None
    return request.app.state.context.analyze(detections, selected, parsed, authorized_patrol,
                                            evidence_bytes=original_bytes)
