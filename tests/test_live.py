from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.main import create_app


class Vision:
    kind = 'person'

    def status(self):
        return {'detector_ready': True, 'species_model_ready': True}

    def analyze(self, frame):
        return [{'type': self.kind, 'score': .9, 'bbox': [.1,.1,.9,.9], 'species': None}]


class TestLive(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.vision = Vision()
        self.app = create_app(Path(self.temp.name) / 'test.db', self.vision)
        self.client = TestClient(self.app)
        self.client.__enter__()
        buffer = BytesIO()
        Image.new('RGB', (16,16)).save(buffer, format='PNG')
        self.data = buffer.getvalue()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.temp.cleanup()

    def upload(self, **fields):
        return self.client.post('/api/analyze-image', data=fields,
                                files={'file': ('image.png', self.data, 'image/png')})

    def ready(self, socket):
        self.assertEqual(socket.receive_json()['type'], 'connection.ready')

    def test_connection_and_origin_validation(self):
        with self.client.websocket_connect('/ws/events', headers={'origin': 'http://127.0.0.1:5173'}) as socket:
            self.ready(socket)
            socket.send_text('ping')
            self.assertEqual(socket.receive_json()['type'], 'connection.pong')
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws/events', headers={'origin': 'https://unrelated.example'}):
                pass

    def test_analysis_broadcasts_committed_event_and_alert_to_two_clients(self):
        with self.client.websocket_connect('/ws/events') as first, self.client.websocket_connect('/ws/events') as second:
            self.ready(first); self.ready(second)
            event = self.upload(timestamp='2026-10-14T23:00:00').json()
            for socket in (first, second):
                message = socket.receive_json()
                self.assertEqual(message['type'], 'event.created')
                self.assertEqual(message['data']['event_id'], event['event_id'])
                self.assertEqual(self.client.get(message['data']['evidence_image_url']).status_code, 200)
                self.assertEqual(self.client.get('/api/events/' + event['event_id']).status_code, 200)
                alert = socket.receive_json()
                self.assertEqual(alert['type'], 'alert.created')
                self.assertEqual(alert['data']['risk_level'], 'CRITICAL')

    def test_high_alert_created(self):
        with self.client.websocket_connect('/ws/events') as socket:
            self.ready(socket)
            self.upload(camera_id='CAM-03', timestamp='2026-10-14T10:00:00')
            self.assertEqual(socket.receive_json()['type'], 'event.created')
            self.assertEqual(socket.receive_json()['data']['risk_level'], 'HIGH')

    def test_low_and_medium_do_not_emit_alert(self):
        with self.client.websocket_connect('/ws/events') as socket:
            self.ready(socket)
            for kind, expected in [('animal','LOW'), ('person','MEDIUM')]:
                self.vision.kind = kind
                response = self.upload(camera_id='CAM-04', authorized_patrol='true', timestamp=f"2026-10-{'14' if kind == 'animal' else '15'}T10:00:00")
                self.assertEqual(response.json()['risk']['level'], expected)
                self.assertEqual(socket.receive_json()['type'], 'event.created')
                socket.send_text('ping')
                self.assertEqual(socket.receive_json()['type'], 'connection.pong')

    def test_action_emits_updated_only_after_success(self):
        event = self.upload(timestamp='2026-10-14T23:00:00').json()
        with self.client.websocket_connect('/ws/events') as socket:
            self.ready(socket)
            url = '/api/alerts/' + event['event_id'] + '/action'
            self.assertEqual(self.client.post(url, json={'action':'PATROL_ASSIGNED'}).status_code, 409)
            socket.send_text('ping')
            self.assertEqual(socket.receive_json()['type'], 'connection.pong')
            self.client.post(url, json={'action':'REVIEWING'})
            message = socket.receive_json()
            self.assertEqual(message['type'], 'alert.updated')
            self.assertEqual(message['data']['status'], 'REVIEWING')
            self.client.post(url, json={'action':'REVIEWING'})
            socket.send_text('ping')
            self.assertEqual(socket.receive_json()['type'], 'connection.pong')

    def test_demo_broadcast_preserves_source_and_isolation(self):
        with self.client.websocket_connect('/ws/events') as socket:
            self.ready(socket)
            result = self.client.post('/api/demo/scenarios/scenario_02_person_core_night/run').json()
            event = socket.receive_json()
            self.assertEqual(event['data']['source'], 'demo')
            self.assertFalse(event['data'].get('evidence_image_url'))
            self.assertEqual(socket.receive_json()['type'], 'alert.created')
            self.assertEqual(result['events'][0]['risk']['score'], 95)
            self.assertEqual(self.app.state.context.context.events._events, [])

    def test_model_failure_emits_nothing(self):
        with self.client.websocket_connect('/ws/events') as socket:
            self.ready(socket)
            with patch.object(self.vision, 'analyze', side_effect=RuntimeError('failed')):
                self.assertEqual(self.upload().status_code, 503)
            socket.send_text('ping')
            self.assertEqual(socket.receive_json()['type'], 'connection.pong')

    def test_rest_succeeds_if_broadcast_fails(self):
        with patch.object(self.app.state.repository, 'publish', side_effect=RuntimeError('socket unavailable')):
            response = self.upload(timestamp='2026-10-14T23:00:00')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(response.json()['evidence_image_url']).status_code, 200)
