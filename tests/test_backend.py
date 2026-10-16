"""API contract/integration tests; fake vision avoids model downloads here."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.services.vision_service import VisionService


class FakeVision:
    def __init__(self):
        self.detections = []
        self.failure = False

    def status(self):
        return {'detector_ready': False, 'species_model_ready': False}

    def analyze(self, frame):
        assert frame.shape == (16, 16, 3)
        if self.failure:
            raise RuntimeError('private model details')
        return self.detections


class TestBackend(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.vision = FakeVision()
        self.client = TestClient(create_app(self.path, self.vision))
        self.client.__enter__()
        buffer = BytesIO()
        Image.new('RGB', (16, 16), 'red').save(buffer, format='PNG')
        self.image = buffer.getvalue()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def upload(self, **data):
        return self.client.post('/api/analyze-image', data=data,
                                files={'file': ('test.png', self.image, 'image/png')})

    def detection(self, kind='person'):
        return {'type': kind, 'score': .9, 'bbox': [.1, .1, .9, .9], 'species': None}

    def run_demo(self, name='scenario_02_person_core_night'):
        response = self.client.post(f'/api/demo/scenarios/{name}/run')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_health_and_docs(self):
        response = self.client.get('/health').json()
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['service'], 'vanadrishti-api')
        self.assertFalse(response['detector_ready'])
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertEqual(self.client.get('/openapi.json').json()['info']['version'], '0.1.0')

    def test_cameras(self):
        data = self.client.get('/api/cameras').json()
        self.assertTrue(data['simulated'])
        self.assertEqual(len(data['cameras']), 7)
        for camera in data['cameras']:
            self.assertTrue(camera['simulated'])
            self.assertIn('not real Tadoba', camera['disclaimer'])
        self.assertTrue(self.client.get('/api/cameras/CAM-01').json()['simulated'])
        self.assertTrue(self.client.get('/api/cameras/C-18').json()['simulated'])
        self.assertTrue(self.client.get('/api/cameras/C-21').json()['simulated'])

    def test_unknown_camera(self):
        self.assertEqual(self.client.get('/api/cameras/missing').status_code, 404)
        self.assertEqual(self.upload(camera_id='missing').status_code, 404)

    def test_risk_levels(self):
        cases = [('animal', 'CAM-01', False, 'LOW', 0),
                 ('person', 'CAM-04', True, 'MEDIUM', 25),
                 ('person', 'CAM-03', False, 'HIGH', 65),
                 ('person', 'CAM-01', False, 'CRITICAL', 95)]
        for index, (kind, camera, authorized, level, score) in enumerate(cases):
            with self.subTest(level=level):
                self.vision.detections = [self.detection(kind)]
                hour = 23 if level == 'CRITICAL' else 10
                response = self.upload(camera_id=camera, authorized_patrol=str(authorized).lower(),
                                       timestamp=f'2026-10-{index+1:02}T{hour}:00:00')
                self.assertEqual(response.status_code, 200, response.text)
                risk = response.json()['risk']
                self.assertEqual((risk['level'], risk['score']), (level, score))
                self.assertEqual(risk['alert'], level in ('HIGH', 'CRITICAL'))
                if risk['alert']:
                    self.assertEqual(risk['recommended_action'],
                                     'Review evidence and notify ranger supervisor for response.')

    def test_invalid_images(self):
        for mime, status in [('text/plain', 415), ('image/png', 422)]:
            response = self.client.post('/api/analyze-image', files={'file': ('bad', b'broken', mime)})
            self.assertEqual(response.status_code, status)

    def test_upload_size_limit(self):
        with patch('backend.api.analyze.MAX_UPLOAD_BYTES', 4):
            self.assertEqual(self.upload().status_code, 413)

    def test_invalid_timestamp_and_boolean(self):
        for value in ['bad', '2026-10-14', '2026-99-14T10:00:00']:
            self.assertEqual(self.upload(timestamp=value).status_code, 422)
        self.assertEqual(self.upload(authorized_patrol='maybe').status_code, 422)

    def test_timezone_and_explicit_false(self):
        self.vision.detections = [self.detection()]
        data = self.upload(camera_id='CAM-04', timestamp='2026-10-14T04:30:00Z',
                           authorized_patrol='false').json()
        self.assertEqual(data['context']['hour'], 10)
        self.assertFalse(data['context']['authorized_patrol'])
        self.assertEqual(data['risk']['score'], 45)
        self.assertTrue(data['timestamp'].endswith('+05:30'))

    def test_no_detections_default_camera(self):
        data = self.upload().json()
        self.assertEqual(data['camera']['id'], 'CAM-01')
        self.assertEqual(data['detections'], [])
        self.assertFalse(data['risk']['alert'])
        self.assertEqual(len(self.client.get('/api/events').json()), 1)

    def test_model_failure(self):
        self.vision.failure = True
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private', response.text)
        self.assertEqual(self.client.get('/api/events').json(), [])

    def test_demo_scenarios(self):
        listing = self.client.get('/api/demo/scenarios').json()
        self.assertEqual(len(listing['scenarios']), 5)
        for scenario in listing['scenarios']:
            data = self.run_demo(scenario['scenario_id'])
            self.assertEqual(data['events'][-1]['risk']['level'], scenario['expected_risk_level'])
            for event in data['events']:
                self.assertTrue(event['simulated'])
                self.assertNotRegex(str(event['risk']).lower(), 'poacher|criminal|illegal hunter|dispatch')
        self.assertEqual(self.client.post('/api/demo/scenarios/missing/run').status_code, 404)

    def test_demo_isolation_and_unique_ids(self):
        first = self.run_demo('scenario_04_tiger_then_person')['events'][-1]
        second = self.run_demo('scenario_04_tiger_then_person')['events'][-1]
        self.assertEqual(first['risk'], second['risk'])
        self.assertNotEqual(first['event_id'], second['event_id'])
        self.vision.detections = [self.detection()]
        result = self.upload(timestamp='2026-10-07T22:31:00').json()
        self.assertEqual(result['risk']['score'], 95)
        self.assertEqual(result['context']['recent_wildlife_events'], [])

    def test_alert_workflow(self):
        event = self.run_demo()['events'][0]
        alert_id = event['event_id']
        url = f'/api/alerts/{alert_id}/action'
        self.assertEqual(len(self.client.get('/api/alerts').json()), 1)
        self.assertEqual(self.client.post(url, json={'action': 'INVALID'}).status_code, 422)
        self.assertEqual(self.client.post(url, json={'action': 'PATROL_ASSIGNED'}).status_code, 409)
        for status in ['REVIEWING', 'PATROL_ASSIGNED', 'ESCALATED', 'RESOLVED']:
            response = self.client.post(url, json={'action': status})
            self.assertEqual(response.json()['status'], status)
        self.assertEqual(self.client.post(url, json={'action': 'REVIEWING'}).status_code, 409)
        self.assertEqual(self.client.get('/api/alerts').json(), [])
        self.assertEqual(len(self.client.get('/api/alerts?include_resolved=true').json()), 1)
        self.assertEqual(self.client.post('/api/alerts/missing/action', json={'action': 'REVIEWING'}).status_code, 404)

    def test_events_filters_order_and_limit(self):
        self.run_demo('scenario_04_tiger_then_person')
        events = self.client.get('/api/events').json()
        self.assertGreater(events[0]['timestamp'], events[1]['timestamp'])
        self.assertEqual(len(self.client.get('/api/events?event_type=animal').json()), 1)
        self.assertEqual(len(self.client.get('/api/events?camera_id=CAM-01&limit=1').json()), 1)
        self.assertEqual(self.client.get('/api/events?limit=0').status_code, 422)
        self.assertEqual(self.client.get('/api/events?event_type=unknown').status_code, 422)

    def test_multi_detection_same_frame(self):
        self.vision.detections = [self.detection(), self.detection()]
        data = self.upload(camera_id='CAM-04', authorized_patrol='true', timestamp='2026-10-14T10:00:00').json()
        self.assertEqual(data['risk']['score'], 25)
        self.assertEqual(len(data['detections']), 2)

    def test_persistence_and_context_restoration(self):
        self.vision.detections = [self.detection('animal') | {
            'species': {'top1': 'Bengal tiger', 'ranking_score': .9,
                        'top3': [{'label': 'Bengal tiger', 'ranking_score': .9}]}}]
        self.upload(camera_id='CAM-02', timestamp='2026-10-14T10:00:00')
        self.run_demo()
        with TestClient(create_app(self.path, self.vision)) as other:
            self.assertEqual(len(other.get('/api/events').json()), 2)
            self.assertEqual(len(other.get('/api/alerts').json()), 1)
            self.vision.detections = [self.detection()]
            response = other.post('/api/analyze-image', data={'timestamp': '2026-10-14T10:15:00'},
                                  files={'file': ('test.png', self.image, 'image/png')})
            self.assertEqual(response.json()['risk']['score'], 100)
            self.assertEqual(len(response.json()['context']['recent_wildlife_events']), 1)

    def test_cors(self):
        response = self.client.options('/api/analyze-image', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')


class TestVisionAdapter(unittest.TestCase):
    def test_models_cached_and_animal_routing_under_concurrency(self):
        detector, species = MagicMock(), MagicMock()
        detector.detect.return_value = [
            {'class': kind, 'confidence': .9, 'bbox': [.1, .1, .9, .9]}
            for kind in ['person', 'animal', 'vehicle']]
        species.classify_animal_detection.return_value = {
            'species': 'tiger', 'confidence': .91,
            'top_k': [{'species': 'tiger', 'confidence': .91}]}
        service = VisionService()
        with patch('ml.detector.detector.get_detector', return_value=detector) as get_detector, \
             patch('ml.species.classifier.get_species_classifier', return_value=species) as get_species:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(service.analyze, [np.zeros((16, 16, 3))] * 4))
            get_detector.assert_called_once()
            get_species.assert_called_once()
        self.assertEqual(species.classify_animal_detection.call_count, 4)
        self.assertEqual(detector.detect.call_args.kwargs['conf_threshold'], .20)
        self.assertEqual(results[0][1]['species']['ranking_score'], .91)
        self.assertNotIn('confidence', str(results[0]))
        self.assertTrue(all(service.status().values()))


if __name__ == '__main__':
    unittest.main()
