"""Original image bytes on disk; only generated relative paths are persisted."""
from io import BytesIO
from pathlib import Path
from uuid import UUID
import os
from PIL import Image

FORMATS = {'JPEG': ('.jpg', 'image/jpeg'), 'PNG': ('.png', 'image/png'),
           'WEBP': ('.webp', 'image/webp'), 'BMP': ('.bmp', 'image/bmp'),
           'TIFF': ('.tiff', 'image/tiff')}


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def resolve(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError('Invalid evidence path')
        return path

    def save(self, event_id, timestamp, data):
        safe_id = str(UUID(event_id))
        with Image.open(BytesIO(data)) as image:
            extension, mime = FORMATS[image.format]
        relative = f'{timestamp[:4]}/{timestamp[5:7]}/{safe_id}{extension}'
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        try:
            with temporary.open('xb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return {'evidence_image_path': relative,
                'evidence_image_url': f'/api/evidence/{safe_id}',
                'evidence_media_type': mime}

    def remove(self, relative):
        self.resolve(relative).unlink(missing_ok=True)
