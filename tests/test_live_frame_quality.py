"""Acceptance: poor visibility cannot imply scene clearance or alter incidents."""
from io import BytesIO
from unittest.mock import patch
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app


class FakeVision:
    def __init__(self): self.items = []
    def analyze(self, frame): return self.items
    def status(self): return {'detector_ready': True, 'species_model_ready': False}


@pytest.fixture
def live(tmp_path):
    vision = FakeVision()
    app = create_app(tmp_path / 'test.db', vision_service=vision)
    with TestClient(app) as client:
        yield app, client, vision


def upload(client, value=0, second=0):
    pixels = (np.full((64,64,3), value, dtype=np.uint8) if value is not None else
              np.random.default_rng(42).integers(30,226,(64,64,3),dtype=np.uint8))
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format='PNG')
    response = client.post('/api/cameras/C-18/frame',
        data={'timestamp': f'2026-10-16T22:00:{second:02d}+05:30'},
        files={'file': ('sample.png',buffer.getvalue(),'image/png')})
    assert response.status_code == 200, response.text
    return response.json()


def counts(app):
    connection = app.state.repository.connection
    return tuple(connection.execute(f'select count(*) from {table}').fetchone()[0]
                 for table in ('events', 'alerts'))


def person():
    return {'type':'person','score':.9,'bbox':[.1,.1,.8,.8],'species':None}


@pytest.mark.parametrize('pixels,quality', [(0,'UNUSABLE'), (5,'UNUSABLE'), (255,'UNUSABLE'), (128,'DEGRADED')])
def test_empty_poor_frame_is_explicitly_not_clear_and_has_no_incident(live, pixels, quality):
    app, client, _ = live
    with patch.object(app.state.context, 'analyze', wraps=app.state.context.analyze) as persist, \
         patch.object(app.state.context, 'assess_only', wraps=app.state.context.assess_only) as assess, \
         patch.object(app.state.repository, 'publish') as publish:
        result = upload(client, pixels)
        persist.assert_not_called()
        assess.assert_not_called()
        publish.assert_not_called()
    assert result['event_state'] == 'NO_DETECTION'  # Existing contract retained.
    assert result['event_id'] is None and result['evidence_image_url'] is None
    assert result['frame_analysis']['status'] == 'DEGRADED_FRAME'
    assert result['frame_analysis']['image_quality']['status'] == quality
    assert result['frame_analysis']['warnings']
    assert result['frame_analysis']['image_quality']['reasons']
    assert result['risk']['score'] == 0 and result['risk']['level'] == 'LOW'
    assert result['risk']['alert'] is False
    assert 'not evidence that the area is clear' in ' '.join(result['risk']['reasons'])
    assert 'not a scene safety assessment' in ' '.join(result['risk']['reasons'])
    assert 'usable image' in result['risk']['recommended_action']
    assert counts(app) == (0,0)
    assert not result['recent_activity']['active']


@pytest.mark.parametrize('pixels,quality', [(0,'UNUSABLE'), (128,'DEGRADED')])
def test_confident_detection_preserved_with_quality_on_new_and_continuation(live, pixels, quality):
    app, client, vision = live
    vision.items = [person()]
    first = upload(client, pixels)
    before = counts(app)
    second = upload(client, pixels, second=1)
    assert first['event_state'] == 'NEW' and first['event_id']
    assert before == (1,1)
    assert second['event_state'] == 'CONTINUATION'
    assert second['event_id'] == first['event_id']
    assert counts(app) == before
    for result in (first, second):
        assert result['detections'][0]['score'] == .9
        assert result['detections'][0]['uncertain'] is False
        assert result['frame_analysis']['status'] == 'CONFIRMED_DETECTION'
        assert result['frame_analysis']['image_quality']['status'] == quality
        assert result['frame_analysis']['warnings']
        assert result['risk']['alert'] is True
        assert result['evidence_image_url']


@pytest.mark.parametrize('pixels', [0,128])
def test_uncertain_poor_frame_keeps_both_warnings_without_incident(live, pixels):
    app, client, vision = live
    vision.items = [dict(type='animal',score=.25,bbox=[.1,.1,.8,.8],species=None,
                        uncertain=True,uncertainty_reason='Below species gate.')]
    result = upload(client, pixels)
    assert result['event_state'] == 'UNCERTAIN_DETECTION'
    assert result['frame_analysis']['status'] == 'UNCERTAIN_DETECTION'
    assert result['frame_analysis']['warnings']
    assert result['detections'][0]['uncertain'] is True
    assert result['detections'][0]['species'] is None
    assert 'Uncertain object evidence' in result['risk']['reasons'][0]
    assert 'not evidence that the area is clear' in ' '.join(result['risk']['reasons'])
    assert counts(app) == (0,0)


def test_covered_gap_preserves_recent_incident_without_duplicates(live):
    app, client, vision = live
    vision.items = [person()]
    first = upload(client, None)
    before = counts(app)
    vision.items = []
    gap = upload(client, 0, second=1)
    assert gap['recent_activity']['active'] is True
    assert gap['recent_activity']['last_event_id'] == first['event_id']
    assert gap['recent_activity']['last_risk_level'] == first['risk']['level']
    assert gap['recent_activity']['last_confirmed_at'] == first['recent_activity']['last_confirmed_at']
    assert gap['frame_analysis']['image_quality']['status'] == 'UNUSABLE'
    assert counts(app) == before
    vision.items = [person()]
    resumed = upload(client, None, second=2)
    assert resumed['event_state'] == 'CONTINUATION'
    assert resumed['event_id'] == first['event_id']
    assert counts(app) == before


def test_good_empty_frame_retains_existing_response(live):
    app, client, _ = live
    result = upload(client, None)
    assert result['event_state'] == 'NO_DETECTION'
    assert result['frame_analysis']['status'] == 'NO_DETECTION'
    assert result['frame_analysis']['image_quality']['status'] == 'GOOD'
    assert result['frame_analysis']['warnings'] == []
    assert result['risk']['reasons'] == ['No retained detections.']
    assert counts(app) == (0,0)
