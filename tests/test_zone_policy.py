"""
Focused tests for VanaDrishti Phase 3-5: Zone-Aware Risk Intelligence,
Camera Operational Policies, and Ranger Notifications.
"""
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.db.database import Repository

LOCAL_TZ = timezone(timedelta(hours=5, minutes=30), 'Asia/Kolkata')


class FakeVision:
    def __init__(self):
        self.detections = []
        self.failure = False

    def status(self):
        return {'detector_ready': True, 'species_model_ready': True}

    def analyze(self, frame):
        assert frame.shape == (16, 16, 3)
        if self.failure:
            raise RuntimeError('Model failure simulation')
        return self.detections


class TestZonePolicyAndNotifications(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.vision = FakeVision()
        self.app = create_app(self.path, self.vision)
        self.client = TestClient(self.app)
        self.client.__enter__()

        buffer = BytesIO()
        Image.new('RGB', (16, 16), 'green').save(buffer, format='JPEG')
        self.image_bytes = buffer.getvalue()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def upload_frame(self, camera_id='C-18', timestamp=None, session_id=None):
        data = {}
        if timestamp:
            data['timestamp'] = timestamp
        if session_id:
            data['session_id'] = session_id
        return self.client.post(
            f'/api/cameras/{camera_id}/frame',
            data=data,
            files={'file': ('live_frame.jpg', self.image_bytes, 'image/jpeg')},
        )

    def detection(self, kind='person', score=0.9, bbox=None, uncertain=False, reason=None):
        return {
            'type': kind,
            'score': score,
            'bbox': bbox or [0.1, 0.1, 0.9, 0.9],
            'species': None,
            'uncertain': uncertain,
            'uncertainty_reason': reason,
        }

    def test_safe_person_detection_produces_nonurgent_observation(self):
        """1. SAFE person detection produces nonurgent observation (score <= 20, alert=False)."""
        # Set C-18 policy to SAFE
        r_set = self.client.post('/api/cameras/C-18/policy', json={'policy': 'SAFE'})
        self.assertEqual(r_set.status_code, 200)
        self.assertEqual(r_set.json()['policy'], 'SAFE')

        self.vision.detections = [self.detection('person', score=0.9)]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        res = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data['risk']['level'], 'LOW')
        self.assertLessEqual(data['risk']['score'], 20)
        self.assertFalse(data['risk']['alert'])
        self.assertTrue(any('SAFE' in r for r in data['risk']['reasons']))

        # No urgent ranger alert is created in alerts queue
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(alerts), 0)

    def test_restricted_person_detection_produces_ranger_review_notification(self):
        """2. RESTRICTED person detection produces ranger review notification (HIGH, alert=True)."""
        # Set C-18 policy to RESTRICTED
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'RESTRICTED'})

        self.vision.detections = [self.detection('person', score=0.9)]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        res = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn(data['risk']['level'], ('HIGH', 'CRITICAL'))
        self.assertGreaterEqual(data['risk']['score'], 65)
        self.assertTrue(data['risk']['alert'])
        self.assertTrue(any('RESTRICTED' in r for r in data['risk']['reasons']))

        # Alert is created and visible in review queue
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['camera_id'], 'C-18')
        self.assertEqual(alerts[0]['status'], 'NEW')
        self.assertEqual(alerts[0]['policy'], 'RESTRICTED')

    def test_critical_person_detection_receives_appropriate_priority(self):
        """3. CRITICAL person detection receives priority CRITICAL status and ranger alert."""
        # Set C-18 policy to CRITICAL
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'CRITICAL'})

        self.vision.detections = [self.detection('person', score=0.9)]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        res = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data['risk']['level'], 'CRITICAL')
        self.assertGreaterEqual(data['risk']['score'], 85)
        self.assertTrue(data['risk']['alert'])
        self.assertTrue(any('CRITICAL' in r for r in data['risk']['reasons']))

    def test_animal_detections_preserve_existing_wildlife_behavior(self):
        """4. Animal detections preserve biological wildlife behavior regardless of zone policy."""
        # Even with CRITICAL policy, animal detection is a normal ecological observation
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'CRITICAL'})

        self.vision.detections = [self.detection('animal', score=0.88)]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        res = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data['risk']['level'], 'LOW')
        self.assertEqual(data['risk']['score'], 0)
        self.assertFalse(data['risk']['alert'])

    def test_uncertain_detections_do_not_generate_confirmed_alerts(self):
        """5. Uncertain detections do not generate unjustified confirmed alerts."""
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'CRITICAL'})

        # Detection flagged uncertain (e.g. backlit silhouette ambiguity)
        self.vision.detections = [self.detection('person', score=0.45, uncertain=True, reason='Backlit candidate conflict')]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        res = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat())
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data['event_state'], 'UNCERTAIN_DETECTION')
        self.assertFalse(data['risk']['alert'])
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(alerts), 0)

    def test_repeated_frames_do_not_create_duplicate_notifications(self):
        """6. Repeated frames within deduplication window do not create duplicate notifications."""
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'RESTRICTED'})

        # Sample 1 at T=0s
        self.vision.detections = [self.detection('person', score=0.9)]
        t0 = datetime(2026, 10, 16, 12, 0, 0, tzinfo=LOCAL_TZ)
        r1 = self.upload_frame(camera_id='C-18', timestamp=t0.isoformat()).json()
        self.assertEqual(r1['event_state'], 'NEW')

        # Sample 2 at T=3s (repeated frame of same ongoing incident)
        t1 = t0 + timedelta(seconds=3)
        r2 = self.upload_frame(camera_id='C-18', timestamp=t1.isoformat()).json()
        self.assertEqual(r2['event_state'], 'CONTINUATION')
        self.assertEqual(r2['event_id'], r1['event_id'])

        # Exactly 1 alert must exist in review queue
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(alerts), 1)

    def test_c18_and_c21_retain_independent_policies_and_sessions(self):
        """7. C-18 and C-21 retain completely independent policies and sessions."""
        # Set C-18 to SAFE and C-21 to CRITICAL
        self.client.post('/api/cameras/C-18/policy', json={'policy': 'SAFE'})
        self.client.post('/api/cameras/C-21/policy', json={'policy': 'CRITICAL'})

        pol_c18 = self.client.get('/api/cameras/C-18/policy').json()
        pol_c21 = self.client.get('/api/cameras/C-21/policy').json()
        self.assertEqual(pol_c18['policy'], 'SAFE')
        self.assertEqual(pol_c21['policy'], 'CRITICAL')

        # Verify cameras list payload reflects both independent policies
        cams = {c['id']: c for c in self.client.get('/api/cameras').json()['cameras']}
        self.assertEqual(cams['C-18']['policy'], 'SAFE')
        self.assertEqual(cams['C-21']['policy'], 'CRITICAL')

    def test_policy_persists_across_database_restarts(self):
        """8. Policy settings persist across database reload / restart."""
        self.client.post('/api/cameras/C-21/policy', json={'policy': 'SAFE'})

        # Open fresh repository directly from SQLite file
        repo = Repository(self.path)
        self.assertEqual(repo.get_camera_policy('C-21'), 'SAFE')
        repo.close()

    def test_invalid_policy_raises_validation_error(self):
        """9. Invalid policy values raise 422 Unprocessable Entity."""
        res = self.client.post('/api/cameras/C-18/policy', json={'policy': 'INVALID_POLICY'})
        self.assertEqual(res.status_code, 422)


if __name__ == '__main__':
    unittest.main()
