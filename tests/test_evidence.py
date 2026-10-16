from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app


class Vision:
    def status(self):
        return {'detector_ready': True, 'species_model_ready': True}

    def analyze(self, frame):
        return [{'type': 'person', 'score': .9, 'bbox': [.1, .1, .9, .9], 'species': None}]


class TestEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.app = create_app(self.path / 'test.db', Vision())
        self.client = TestClient(self.app)
        self.client.__enter__()
        buffer = BytesIO()
        Image.new('RGB', (16, 16), 'red').save(buffer, format='PNG')
        self.data = buffer.getvalue()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def upload(self):
        return self.client.post('/api/analyze-image', data={'timestamp': '2026-10-14T23:00:00'},
                                files={'file': ('../../unsafe.png', self.data, 'image/png')})

    def test_original_bytes_persist_and_url_serves_image(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.text)
        event = response.json()
        path = self.path / 'evidence' / event['evidence_image_path']
        self.assertEqual(path.read_bytes(), self.data)
        self.assertEqual(path.name, event['event_id'] + '.png')
        image = self.client.get(event['evidence_image_url'])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.content, self.data)
        self.assertEqual(image.headers['content-type'], 'image/png')
        self.assertEqual(self.client.get('/api/alerts').json()[0]['evidence_image_url'], event['evidence_image_url'])

    def test_evidence_survives_app_restart(self):
        event = self.upload().json()
        with TestClient(create_app(self.path / 'test.db', Vision())) as other:
            self.assertEqual(other.get(event['evidence_image_url']).content, self.data)
            self.assertEqual(other.get('/api/events/' + event['event_id']).json()['evidence_image_url'], event['evidence_image_url'])

    def test_unknown_missing_and_traversal_return_404(self):
        for value in ['missing', '00000000-0000-0000-0000-000000000000', '..%2F..%2Fconfig%2Frisk_rules.json', '..%5C..%5Cconfig%5Crisk_rules.json']:
            self.assertEqual(self.client.get('/api/evidence/' + value).status_code, 404)
        event = self.upload().json()
        (self.path / 'evidence' / event['evidence_image_path']).unlink()
        self.assertEqual(self.client.get(event['evidence_image_url']).status_code, 404)

    def test_tampered_database_cannot_expose_outside_file(self):
        event = self.upload().json()
        event['evidence_image_path'] = '../private.txt'
        (self.path / 'private.txt').write_text('private')
        with self.app.state.repository.connection as connection:
            connection.execute('UPDATE events SET payload=? WHERE id=?', (json.dumps(event), event['event_id']))
        self.assertEqual(self.client.get(event['evidence_image_url']).status_code, 404)

    def test_legacy_event_without_evidence_and_demo_still_work(self):
        event = self.client.post('/api/demo/scenarios/scenario_02_person_core_night/run').json()['events'][0]
        stored = self.client.get('/api/events/' + event['event_id'])
        self.assertEqual(stored.status_code, 200)
        self.assertIsNone(stored.json()['evidence_image_url'])
        self.assertEqual(self.client.get('/api/evidence/' + event['event_id']).status_code, 404)

    def test_failed_commit_removes_evidence_and_history(self):
        with patch.object(self.app.state.repository, 'save', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertEqual(list((self.path / 'evidence').rglob('*.png')), [])
        self.assertEqual(self.client.get('/api/events').json(), [])
        self.assertEqual(self.app.state.context.context.events._events, [])

    def test_failed_model_does_not_store_evidence(self):
        with patch.object(self.app.state.vision, 'analyze', side_effect=RuntimeError('failed')):
            self.assertEqual(self.upload().status_code, 503)
        self.assertFalse((self.path / 'evidence').exists())
