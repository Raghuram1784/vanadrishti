"""Species gating, ambiguity and observation persistence contracts."""
import unittest
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.services.vision_service import VisionService
from ml.detector.detector import WildlifeDetector


def candidate(kind='animal', score=.2146, bbox=None):
    return dict(class_name=kind, score=score, bbox=bbox or [.1,.1,.8,.8])


class TestUncertainty(unittest.TestCase):
    def service(self, kind='animal', score=.2146, rivals=(), gate=.35):
        service = VisionService(gate)
        detector, species = MagicMock(), MagicMock()
        def detect(frame, conf_threshold, candidate_sink):
            candidate_sink.extend(rivals)
            return [{'class':kind,'confidence':score,'bbox':[.1,.1,.8,.8]}]
        detector.detect.side_effect = detect
        species.classify_animal_detection.return_value = {
            'species':'tiger', 'confidence':.9,
            'top_k':[{'species':label,'confidence':score} for label,score in [('tiger',.9),('leopard',.07),('gaur',.03)]]}
        service._detector, service._species = detector, species
        return service, species

    def test_weak_animal_retained_without_species(self):
        service, species = self.service()
        result=service.analyze(np.zeros((16,16,3)))[0]
        self.assertTrue(result['uncertain'])
        self.assertEqual(result['score'],.2146)
        self.assertIsNone(result['species'])
        species.classify_animal_detection.assert_not_called()

    def test_gate_boundary_and_strong_animal(self):
        for score in [.35,.9]:
            service,species=self.service(score=score)
            result=service.analyze(None)[0]
            self.assertFalse(result.get('uncertain',False))
            self.assertEqual(len(result['species']['top3']),3)
            species.classify_animal_detection.assert_called_once()

    def test_person_vehicle_never_run_bioclip(self):
        for kind in ['person','vehicle']:
            service,species=self.service(kind=kind,score=.9)
            self.assertIsNone(service.analyze(None)[0]['species'])
            species.classify_animal_detection.assert_not_called()

    def test_overlapping_competing_signal_withholds_species(self):
        rival={'class':'person','confidence':.19,'bbox':[.1,.1,.8,.8]}
        service,species=self.service(score=.36,rivals=[rival])
        result=service.analyze(None)[0]
        self.assertTrue(result['uncertain'])
        self.assertEqual(result['candidate_signals'][1]['score'],.19)
        species.classify_animal_detection.assert_not_called()

    def test_unrelated_person_does_not_veto_animal(self):
        service,species=self.service(score=.9,rivals=[{'class':'person','confidence':.9,'bbox':[.85,.85,1,1]}])
        self.assertIsNotNone(service.analyze(None)[0]['species'])

    def test_configuration_validation(self):
        with patch.dict('os.environ',{'SPECIES_CLASSIFICATION_MIN_DETECTOR_SCORE':'.30'}):
            self.assertEqual(VisionService().species_min_detector_score,.30)
        for value in [.1,1.1,float('nan')]:
            with self.assertRaises(ValueError): VisionService(value)

    def test_detector_preserves_bgr_and_retention_with_candidates(self):
        detector=object.__new__(WildlifeDetector)
        detector.default_conf_threshold=.2
        detector._model=MagicMock()
        raw=MagicMock()
        raw.__len__.return_value=4
        raw.xyxy=np.array([[0,0,8,8]]*4)
        raw.confidence=np.array([.2146,.19,.25,.49])
        raw.class_id=np.array([0,1,1,2])
        detector._model.single_image_detection.return_value={'detections':raw}
        frame=np.zeros((8,8,3),dtype=np.uint8);frame[:,:,0]=200
        signals=[]
        retained=detector.detect(frame,candidate_sink=signals)
        passed=detector._model.single_image_detection.call_args.args[0]
        np.testing.assert_array_equal(passed,frame)
        self.assertEqual(detector._model.single_image_detection.call_args.kwargs['det_conf_thres'],.05)
        self.assertEqual([d['class'] for d in retained],['animal','person'])
        self.assertEqual(len(signals),4)

    def test_uncertain_live_no_event_alert_evidence_or_publication(self):
        service,_=self.service()
        buffer=BytesIO();Image.new('RGB',(16,16)).save(buffer,format='JPEG')
        with TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'db.sqlite',vision_service=service)
            with TestClient(app) as client, patch.object(app.state.repository,'publish') as publish:
                for _ in range(3):
                    response=client.post('/api/cameras/C-18/frame',files={'file':('test.jpg',buffer.getvalue(),'image/jpeg')})
                    self.assertEqual(response.status_code,200,response.text)
                    result=response.json()
                    self.assertEqual(result['event_state'],'UNCERTAIN_DETECTION')
                    self.assertFalse(result['risk']['alert'])
                    self.assertIsNone(result['event_id'])
                self.assertEqual(app.state.repository.connection.execute('select count(*) from events').fetchone()[0],0)
                self.assertEqual(app.state.repository.connection.execute('select count(*) from alerts').fetchone()[0],0)
                publish.assert_not_called()
                self.assertFalse((Path(tmp)/'evidence').exists())

    def test_static_retains_uncertain_without_context_pollution(self):
        service,_=self.service()
        buffer=BytesIO();Image.new('RGB',(16,16)).save(buffer,format='JPEG')
        with TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'db.sqlite',vision_service=service)
            with TestClient(app) as client:
                result=client.post('/api/analyze-image',files={'file':('test.jpg',buffer.getvalue(),'image/jpeg')}).json()
                self.assertTrue(result['detections'][0]['uncertain'])
                self.assertIsNone(result['detections'][0]['species'])
                self.assertFalse(result['risk']['alert'])
                row=app.state.repository.connection.execute('select domain_events from events').fetchone()
                self.assertEqual(row[0],'[]')

    def test_mixed_confirmed_and_uncertain_uses_confirmed_for_dedupe(self):
        service,_=self.service()
        uncertain=service.analyze(None)[0]
        service.analyze=MagicMock(return_value=[uncertain,{'type':'person','score':.9,'bbox':[0,0,1,1],'species':None}])
        buffer=BytesIO();Image.new('RGB',(16,16)).save(buffer,format='JPEG')
        with TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'db.sqlite',vision_service=service)
            with TestClient(app) as client:
                states=[]
                for _ in range(2):
                    result=client.post('/api/cameras/C-18/frame',files={'file':('test.jpg',buffer.getvalue(),'image/jpeg')}).json()
                    states.append(result['event_state'])
                    self.assertIsNone(result['detections'][0]['species'])
                self.assertEqual(states,['NEW','CONTINUATION'])
                import json
                domain=json.loads(app.state.repository.connection.execute('select domain_events from events').fetchone()[0])
                self.assertEqual(len(domain),1)
                self.assertEqual(domain[0]['object_type'],'person')

    def test_temporal_consistency_weak_detection_requires_two_samples(self):
        """Weak detection (< 0.35) must be observed in 2 of 3 samples before promotion."""
        service, _ = self.service()
        # Weak unflagged person detection (score 0.28) - use side_effect to return fresh dicts
        service.analyze = MagicMock(side_effect=lambda frame: [{'type': 'person', 'score': 0.28, 'bbox': [0, 0, 1, 1], 'species': None}])
        buffer = BytesIO(); Image.new('RGB', (16, 16)).save(buffer, format='JPEG')
        with TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / 'db.sqlite', vision_service=service)
            with TestClient(app) as client:
                # Frame 1: Only 1 sample with 'person'. Must be UNCERTAIN_DETECTION
                r1 = client.post('/api/cameras/C-18/frame', files={'file': ('f1.jpg', buffer.getvalue(), 'image/jpeg')}).json()
                self.assertEqual(r1['event_state'], 'UNCERTAIN_DETECTION')
                self.assertTrue(r1['detections'][0]['uncertain'])
                self.assertIn('awaiting class-level confirmation', r1['detections'][0]['uncertainty_reason'])
                self.assertEqual(app.state.repository.connection.execute('select count(*) from events').fetchone()[0], 0)

                # Frame 2: Second sample with 'person' (2 of last 3). Must be promoted to NEW event!
                r2 = client.post('/api/cameras/C-18/frame', files={'file': ('f2.jpg', buffer.getvalue(), 'image/jpeg')}).json()
                self.assertEqual(r2['event_state'], 'NEW')
                self.assertFalse(r2['detections'][0].get('uncertain', False))
                self.assertEqual(app.state.repository.connection.execute('select count(*) from events').fetchone()[0], 1)

    def test_temporal_consistency_dissimilar_weak_classes_not_promoted(self):
        """Weak detections with changing classes (e.g. vehicle then person) do not cross-promote."""
        service, _ = self.service()
        buffer = BytesIO(); Image.new('RGB', (16, 16)).save(buffer, format='JPEG')
        with TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / 'db.sqlite', vision_service=service)
            with TestClient(app) as client:
                # Frame 1: Weak vehicle (0.30)
                service.analyze = MagicMock(return_value=[{'type': 'vehicle', 'score': 0.30, 'bbox': [0, 0, 1, 1], 'species': None}])
                r1 = client.post('/api/cameras/C-18/frame', files={'file': ('f1.jpg', buffer.getvalue(), 'image/jpeg')}).json()
                self.assertEqual(r1['event_state'], 'UNCERTAIN_DETECTION')

                # Frame 2: Weak person (0.28) - different class, only 1 sample with person
                service.analyze = MagicMock(return_value=[{'type': 'person', 'score': 0.28, 'bbox': [0, 0, 1, 1], 'species': None}])
                r2 = client.post('/api/cameras/C-18/frame', files={'file': ('f2.jpg', buffer.getvalue(), 'image/jpeg')}).json()
                self.assertEqual(r2['event_state'], 'UNCERTAIN_DETECTION')
                self.assertEqual(app.state.repository.connection.execute('select count(*) from events').fetchone()[0], 0)

    def test_temporal_consistency_strong_detection_never_delayed(self):
        """Strong detections (>= 0.35) immediately produce NEW events on the first frame."""
        service, _ = self.service()
        service.analyze = MagicMock(return_value=[{'type': 'person', 'score': 0.45, 'bbox': [0, 0, 1, 1], 'species': None}])
        buffer = BytesIO(); Image.new('RGB', (16, 16)).save(buffer, format='JPEG')
        with TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / 'db.sqlite', vision_service=service)
            with TestClient(app) as client:
                r1 = client.post('/api/cameras/C-18/frame', files={'file': ('f1.jpg', buffer.getvalue(), 'image/jpeg')}).json()
                self.assertEqual(r1['event_state'], 'NEW')
                self.assertFalse(r1['detections'][0].get('uncertain', False))
                self.assertEqual(app.state.repository.connection.execute('select count(*) from events').fetchone()[0], 1)


if __name__=='__main__': unittest.main()
