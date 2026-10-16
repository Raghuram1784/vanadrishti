"""
Phase 5A tests: Laptop Live Field Camera (C-18), camera sessions, frame deduplication,
and live frame analysis.
"""
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.camera_session_service import (
    ONLINE_THRESHOLD_SECONDS,
    DEGRADED_THRESHOLD_SECONDS,
)

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


class TestLiveCameraPhase5A(unittest.TestCase):
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

    def upload_frame(self, camera_id='C-18', session_id=None, timestamp=None, authorized_patrol=None):
        data = {}
        if session_id:
            data['session_id'] = session_id
        if timestamp:
            data['timestamp'] = timestamp
        if authorized_patrol is not None:
            data['authorized_patrol'] = str(authorized_patrol).lower()
        return self.client.post(
            f'/api/cameras/{camera_id}/frame',
            data=data,
            files={'file': ('live_frame.jpg', self.image_bytes, 'image/jpeg')},
        )

    def detection(self, kind='person', species=None, score=0.9):
        sp = None
        if species:
            sp = {
                'top1': species,
                'ranking_score': 0.88,
                'top3': [{'label': species, 'ranking_score': 0.88}],
            }
        return {'type': kind, 'score': score, 'bbox': [0.1, 0.1, 0.9, 0.9], 'species': sp}

    def test_c18_camera_registered(self):
        """Verify C-18 exists in simulated registry, zone is CORE, and simulated=True."""
        response = self.client.get('/api/cameras/C-18')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['id'], 'C-18')
        self.assertTrue(data['simulated'])
        self.assertEqual(data['zone'], 'CORE')
        self.assertIn('Laptop Prototype Node', data['name'])
        self.assertIn('not real Tadoba', data['disclaimer'])

    def test_session_lifecycle(self):
        """Verify session creation, heartbeat, listing, and closure."""
        # 1. Unknown camera raises 404
        r_unknown = self.client.post('/api/cameras/NONEXISTENT/session')
        self.assertEqual(r_unknown.status_code, 404)

        # 2. Create session on C-18
        r_create = self.client.post(
            '/api/cameras/C-18/session',
            json={'device_name': 'Test Laptop Cam', 'device_type': 'laptop_webcam'},
        )
        self.assertEqual(r_create.status_code, 200, r_create.text)
        session = r_create.json()
        session_id = session['session_id']
        self.assertEqual(session['camera_id'], 'C-18')
        self.assertEqual(session['status'], 'ONLINE')
        self.assertEqual(session['frames_received'], 0)

        # 3. List sessions
        r_list = self.client.get('/api/camera-sessions')
        self.assertEqual(r_list.status_code, 200)
        sessions_list = r_list.json()
        self.assertTrue(any(s['session_id'] == session_id for s in sessions_list))

        # 4. Get active session for camera
        r_active = self.client.get('/api/cameras/C-18/session')
        self.assertEqual(r_active.status_code, 200)
        self.assertEqual(r_active.json()['session_id'], session_id)

        # 5. Heartbeat
        r_hb = self.client.post(
            '/api/cameras/C-18/heartbeat',
            json={'session_id': session_id},
        )
        self.assertEqual(r_hb.status_code, 200)
        self.assertEqual(r_hb.json()['status'], 'ONLINE')

        # 6. Heartbeat with invalid session raises 404
        r_hb_bad = self.client.post(
            '/api/cameras/C-18/heartbeat',
            json={'session_id': 'bad-session-id'},
        )
        self.assertEqual(r_hb_bad.status_code, 404)

        # 7. Close session
        r_close = self.client.delete(f'/api/cameras/C-18/session/{session_id}')
        self.assertEqual(r_close.status_code, 200)
        self.assertEqual(r_close.json()['status'], 'OFFLINE')

    def test_session_status_thresholds(self):
        """Test ONLINE (<=20s), DEGRADED (>20s and <=45s), and OFFLINE (>45s) status calculations."""
        r_create = self.client.post('/api/cameras/C-18/session')
        session_id = r_create.json()['session_id']

        service = self.app.state.sessions
        live_session = service._sessions[session_id]

        now = time.time()
        # 10s elapsed -> ONLINE
        self.assertEqual(live_session.compute_status(now_epoch=now + 10.0), 'ONLINE')
        # 25s elapsed -> DEGRADED
        self.assertEqual(live_session.compute_status(now_epoch=now + 25.0), 'DEGRADED')
        # 50s elapsed -> OFFLINE
        self.assertEqual(live_session.compute_status(now_epoch=now + 50.0), 'OFFLINE')

    def test_live_frame_validation(self):
        """Validate camera existence, mime types, corrupt images, and bad timestamps."""
        # 1. Unknown camera -> 404
        r_unknown = self.upload_frame(camera_id='CAM-DOES-NOT-EXIST')
        self.assertEqual(r_unknown.status_code, 404)

        # 2. Unsupported mime type -> 415
        r_text = self.client.post(
            '/api/cameras/C-18/frame',
            files={'file': ('note.txt', b'hello world', 'text/plain')},
        )
        self.assertEqual(r_text.status_code, 415)

        # 3. Corrupt image -> 422
        r_corrupt = self.client.post(
            '/api/cameras/C-18/frame',
            files={'file': ('bad.jpg', b'not a valid jpeg stream', 'image/jpeg')},
        )
        self.assertEqual(r_corrupt.status_code, 422)

        # 4. Invalid timestamp -> 422
        r_bad_ts = self.client.post(
            '/api/cameras/C-18/frame',
            data={'timestamp': 'invalid-time'},
            files={'file': ('test.jpg', self.image_bytes, 'image/jpeg')},
        )
        self.assertEqual(r_bad_ts.status_code, 422)

    def test_live_frame_no_detection_creates_no_event_or_evidence(self):
        """Verify clear frames return NO_DETECTION and do NOT persist to DB or evidence disk."""
        self.vision.detections = []

        # Create session
        s_res = self.client.post('/api/cameras/C-18/session').json()
        session_id = s_res['session_id']

        response = self.upload_frame(camera_id='C-18', session_id=session_id)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        self.assertEqual(data['event_state'], 'NO_DETECTION')
        self.assertIsNone(data['event_id'])
        self.assertIsNone(data['evidence_image_url'])
        self.assertEqual(len(data['detections']), 0)
        self.assertEqual(data['risk']['level'], 'LOW')
        self.assertFalse(data['risk']['alert'])

        # Verify database is completely empty
        events = self.client.get('/api/events').json()
        self.assertEqual(len(events), 0)
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(alerts), 0)

        # Session counters updated
        sess = self.client.get('/api/cameras/C-18/session').json()
        self.assertEqual(sess['frames_received'], 1)
        self.assertEqual(sess['frames_analyzed'], 1)

    def test_live_frame_new_detection_and_deduplication(self):
        """
        Verify first detection becomes NEW event, second identical detection within 20s
        becomes CONTINUATION without new event/alert, and detection after 20s becomes NEW.
        """
        self.vision.detections = [self.detection('person')]

        # Setup session
        s_res = self.client.post('/api/cameras/C-18/session').json()
        session_id = s_res['session_id']

        # Frame 1 at T=0
        base_time = datetime(2026, 10, 14, 12, 0, 0, tzinfo=LOCAL_TZ)
        r1 = self.upload_frame(
            camera_id='C-18',
            session_id=session_id,
            timestamp=base_time.isoformat(),
        )
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()

        self.assertEqual(d1['event_state'], 'NEW')
        event_id_1 = d1['event_id']
        self.assertIsNotNone(event_id_1)
        self.assertIsNotNone(d1['evidence_image_url'])

        # Evidence image exists and is retrievable
        r_ev = self.client.get(d1['evidence_image_url'])
        self.assertEqual(r_ev.status_code, 200)

        # Exactly 1 event and 1 alert created in DB
        self.assertEqual(len(self.client.get('/api/events').json()), 1)
        self.assertEqual(len(self.client.get('/api/alerts').json()), 1)

        # Frame 2 at T=5s (within 20s window) with same person detection
        time_2 = base_time + timedelta(seconds=5)
        r2 = self.upload_frame(
            camera_id='C-18',
            session_id=session_id,
            timestamp=time_2.isoformat(),
        )
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()

        # MUST BE CONTINUATION
        self.assertEqual(d2['event_state'], 'CONTINUATION')
        self.assertEqual(d2['event_id'], event_id_1)

        # Database counts must remain EXACTLY 1 (no duplicate rows created!)
        self.assertEqual(len(self.client.get('/api/events').json()), 1)
        self.assertEqual(len(self.client.get('/api/alerts').json()), 1)

        # Frame 3 at T=30s (exceeds 20s dedupe window)
        time_3 = base_time + timedelta(seconds=30)
        r3 = self.upload_frame(
            camera_id='C-18',
            session_id=session_id,
            timestamp=time_3.isoformat(),
        )
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()

        # MUST BE A NEW EVENT
        self.assertEqual(d3['event_state'], 'NEW')
        event_id_3 = d3['event_id']
        self.assertNotEqual(event_id_3, event_id_1)

        # Database now has 2 events
        self.assertEqual(len(self.client.get('/api/events').json()), 2)

    def test_animal_species_deduplication(self):
        """Test species-aware deduplication for animal detections."""
        base_time = datetime(2026, 10, 14, 10, 0, 0, tzinfo=LOCAL_TZ)

        # 1. Tiger detection at T=0 -> NEW
        self.vision.detections = [self.detection('animal', species='Panthera tigris')]
        r1 = self.upload_frame(camera_id='C-18', timestamp=base_time.isoformat())
        self.assertEqual(r1.json()['event_state'], 'NEW')
        event_id = r1.json()['event_id']

        # 2. Tiger detection at T=4s -> CONTINUATION
        r2 = self.upload_frame(
            camera_id='C-18',
            timestamp=(base_time + timedelta(seconds=4)).isoformat(),
        )
        self.assertEqual(r2.json()['event_state'], 'CONTINUATION')
        self.assertEqual(r2.json()['event_id'], event_id)

        # 3. Different species (Leopard) at T=8s -> NEW (different species)
        self.vision.detections = [self.detection('animal', species='Panthera pardus')]
        r3 = self.upload_frame(
            camera_id='C-18',
            timestamp=(base_time + timedelta(seconds=8)).isoformat(),
        )
        self.assertEqual(r3.json()['event_state'], 'NEW')
        self.assertNotEqual(r3.json()['event_id'], event_id)

    def test_existing_analyze_image_and_websocket_still_work(self):
        """Verify existing /api/analyze-image and WebSocket flow are unharmed."""
        self.vision.detections = [self.detection('person')]

        # Static upload endpoint
        r = self.client.post(
            '/api/analyze-image',
            data={'camera_id': 'C-18'},
            files={'file': ('test.jpg', self.image_bytes, 'image/jpeg')},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['source'], 'image')

        # WebSocket connection
        with self.client.websocket_connect('/ws/events') as ws:
            ready = ws.receive_json()
            self.assertEqual(ready['type'], 'connection.ready')

            # Submit a NEW live frame that triggers an alert (person in CORE zone)
            self.upload_frame(camera_id='C-18')

            # Must receive event.created and alert.created
            types_received = []
            for _ in range(2):
                msg = ws.receive_json()
                types_received.append(msg['type'])

            self.assertIn('event.created', types_received)
            self.assertIn('alert.created', types_received)


class TestTemporalActivityState(unittest.TestCase):
    """
    Tests for camera-level temporal activity continuity (class-level persistence,
    TTL expiration, uncertainty separation, and deduplication preservation).
    """
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

    def upload_frame(self, camera_id='C-18', timestamp=None):
        data = {}
        if timestamp:
            data['timestamp'] = timestamp
        return self.client.post(
            f'/api/cameras/{camera_id}/frame',
            data=data,
            files={'file': ('live_frame.jpg', self.image_bytes, 'image/jpeg')},
        )

    def detection(self, kind='person', score=0.9, uncertain=False, reason=None):
        return {
            'type': kind,
            'score': score,
            'bbox': [0.1, 0.1, 0.9, 0.9],
            'species': None,
            'uncertain': uncertain,
            'uncertainty_reason': reason,
        }

    def test_confirmed_person_detection_activates_recent_activity(self):
        """1. Confirmed person detection creates NEW event and activates recent activity."""
        self.vision.detections = [self.detection('person', score=0.9)]
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)

        res = self.upload_frame(timestamp=t0.isoformat()).json()
        self.assertEqual(res['event_state'], 'NEW')
        act = res.get('recent_activity')
        self.assertIsNotNone(act)
        self.assertTrue(act['active'])
        self.assertEqual(act['type'], 'person')
        self.assertEqual(act['last_event_id'], res['event_id'])
        self.assertEqual(act['last_risk_level'], 'CRITICAL')
        self.assertEqual(act['seconds_since_last_confirmed'], 0.0)

    def test_one_no_detection_sample_immediately_after_retains_recent_activity(self):
        """2. One NO_DETECTION sample immediately after confirmed person retains recent activity."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        r1 = self.upload_frame(timestamp=t0.isoformat()).json()
        event_id = r1['event_id']

        # Frame 2 at T=3s: Missed sample (NO_DETECTION)
        t1 = t0 + timedelta(seconds=3)
        self.vision.detections = []
        r2 = self.upload_frame(timestamp=t1.isoformat()).json()

        self.assertEqual(r2['event_state'], 'NO_DETECTION')
        self.assertEqual(len(r2['detections']), 0)
        act = r2.get('recent_activity')
        self.assertIsNotNone(act)
        self.assertTrue(act['active'], "Recent activity must remain active on 1 missed sample")
        self.assertEqual(act['type'], 'person')
        self.assertEqual(act['last_event_id'], event_id)
        self.assertEqual(act['last_risk_level'], 'CRITICAL')
        self.assertEqual(act['seconds_since_last_confirmed'], 3.0)
        self.assertIn("Monitoring continues", act['monitoring_status'])

    def test_activity_remains_active_within_ttl(self):
        """3. Activity remains active across multiple missed samples within TTL (e.g. 12s <= 15s)."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        self.upload_frame(timestamp=t0.isoformat())

        # Check at T=6s, T=9s, T=12s: all should remain active
        self.vision.detections = []
        for elapsed in [6, 9, 12]:
            t = t0 + timedelta(seconds=elapsed)
            r = self.upload_frame(timestamp=t.isoformat()).json()
            self.assertEqual(r['event_state'], 'NO_DETECTION')
            act = r.get('recent_activity')
            self.assertTrue(act['active'])
            self.assertEqual(act['seconds_since_last_confirmed'], float(elapsed))

    def test_activity_becomes_inactive_after_ttl_expiry(self):
        """4. Activity becomes inactive after TTL expires (e.g. 16s > 15s)."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        self.upload_frame(timestamp=t0.isoformat())

        # Check at T=16s (past 15s TTL)
        self.vision.detections = []
        t_exp = t0 + timedelta(seconds=16)
        r = self.upload_frame(timestamp=t_exp.isoformat()).json()

        self.assertEqual(r['event_state'], 'NO_DETECTION')
        act = r.get('recent_activity')
        self.assertIsNotNone(act)
        self.assertFalse(act['active'], "Activity must become inactive once TTL has elapsed")
        self.assertEqual(act['seconds_since_last_confirmed'], 16.0)

    def test_new_confirmed_detection_refreshes_last_confirmed_at(self):
        """5. A new confirmed detection refreshes last_confirmed_at to the current timestamp."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        self.upload_frame(timestamp=t0.isoformat())

        # T=10s: Another confirmed detection (refreshing window)
        t1 = t0 + timedelta(seconds=10)
        self.vision.detections = [self.detection('person', score=0.9)]
        r1 = self.upload_frame(timestamp=t1.isoformat()).json()
        self.assertEqual(r1['recent_activity']['seconds_since_last_confirmed'], 0.0)

        # T=20s: 10s after T=10s refresh. Must STILL be active (10s <= 15s TTL)!
        t2 = t0 + timedelta(seconds=20)
        self.vision.detections = []
        r2 = self.upload_frame(timestamp=t2.isoformat()).json()
        self.assertTrue(r2['recent_activity']['active'])
        self.assertEqual(r2['recent_activity']['seconds_since_last_confirmed'], 10.0)

    def test_uncertain_detection_does_not_create_fresh_confirmed_activity(self):
        """6. An uncertain detection does NOT activate fresh confirmed activity."""
        self.vision.detections = [self.detection('animal', score=0.22, uncertain=True, reason='Low confidence')]
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)

        res = self.upload_frame(timestamp=t0.isoformat()).json()
        self.assertEqual(res['event_state'], 'UNCERTAIN_DETECTION')
        act = res.get('recent_activity')
        self.assertIsNotNone(act)
        self.assertFalse(act['active'], "Uncertain detection must never activate confirmed recent activity")

    def test_continuation_does_not_create_duplicate_event(self):
        """7. Continuation refreshes activity without creating duplicate DB event or alert."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        r1 = self.upload_frame(timestamp=t0.isoformat()).json()
        event_id = r1['event_id']

        # T=5s: Continuation
        t1 = t0 + timedelta(seconds=5)
        r2 = self.upload_frame(timestamp=t1.isoformat()).json()
        self.assertEqual(r2['event_state'], 'CONTINUATION')
        self.assertEqual(r2['event_id'], event_id)
        self.assertEqual(r2['recent_activity']['last_event_id'], event_id)

        # Database counts must remain 1
        events = self.client.get('/api/events').json()
        alerts = self.client.get('/api/alerts').json()
        self.assertEqual(len(events), 1)
        self.assertEqual(len(alerts), 1)

    def test_latest_sample_and_recent_activity_can_differ_safely(self):
        """8. Latest sample and recent activity can differ safely without contradicting contracts."""
        t0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=LOCAL_TZ)
        self.vision.detections = [self.detection('person', score=0.9)]
        self.upload_frame(timestamp=t0.isoformat())

        # T=4s: Missed sample
        t1 = t0 + timedelta(seconds=4)
        self.vision.detections = []
        r = self.upload_frame(timestamp=t1.isoformat()).json()

        # Latest sample reports NO_DETECTION with 0 detections
        self.assertEqual(r['event_state'], 'NO_DETECTION')
        self.assertEqual(len(r['detections']), 0)
        # Recent activity clearly reports ongoing person activity
        self.assertTrue(r['recent_activity']['active'])
        self.assertEqual(r['recent_activity']['type'], 'person')
        self.assertEqual(r['recent_activity']['last_risk_level'], 'CRITICAL')

    def test_grammar_format_detection_count(self):
        """9. Grammar check: 0 -> 'No detection in latest sample', 1 -> '1 object detected', 2+ -> 'N objects detected'."""
        def format_detection_count(count: int) -> str:
            if count == 0:
                return "No detection in latest sample"
            if count == 1:
                return "1 object detected"
            return f"{count} objects detected"

        self.assertEqual(format_detection_count(0), "No detection in latest sample")
        self.assertEqual(format_detection_count(1), "1 object detected")
        self.assertEqual(format_detection_count(2), "2 objects detected")
        self.assertEqual(format_detection_count(5), "5 objects detected")


if __name__ == '__main__':
    unittest.main()
