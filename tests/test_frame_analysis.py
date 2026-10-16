"""Frame-contract and quality tests use fake inference; no model downloads."""
from io import BytesIO
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.services.vision_service import VisionService
from ml.pipeline import analyze_frame, FrameStatus, QualityConfig
from ml.pipeline.models import FrameAnalysisResult, QualityStatus, QualityFlag
from ml.pipeline.quality import assess_quality


def detailed():
    return np.random.default_rng(42).integers(30, 226, (128, 128, 3), dtype=np.uint8)


def detection(kind='person', score=.8, **extra):
    return dict(type=kind, score=score, bbox=[.1,.1,.8,.8], species=None, **extra)


@pytest.mark.parametrize('state,items', [
    (FrameStatus.NO_DETECTION, []),
    (FrameStatus.CONFIRMED_DETECTION, [detection()]),
    (FrameStatus.UNCERTAIN_DETECTION, [detection('animal', .25, uncertain=True)]),
])
def test_contract_serialization(state, items):
    frame = detailed()
    infer = MagicMock(return_value=items)
    result = analyze_frame(frame, 'future-node', {'captured_at': '2026-10-16T12:00:00+05:30'}, inference=infer)
    assert result.status == state
    payload = result.model_dump(mode='json')
    assert payload['camera_id'] == 'future-node'
    assert payload['captured_at'].endswith('+05:30')
    assert payload['processing_ms'] >= 0
    assert payload['status'] == state.value
    assert FrameAnalysisResult.model_validate_json(result.model_dump_json()) == result
    assert infer.call_args.args[0] is frame


@pytest.mark.parametrize('value,flag', [(0, QualityFlag.TOO_DARK), (5, QualityFlag.TOO_DARK), (255, QualityFlag.OVEREXPOSED)])
def test_extreme_quality(value, flag):
    frame = np.full((64,64,3), value, dtype=np.uint8)
    quality = assess_quality(frame)
    assert quality.status == QualityStatus.UNUSABLE
    assert flag in quality.flags
    result = analyze_frame(frame, 'test', inference=lambda _: [])
    assert result.status == FrameStatus.DEGRADED_FRAME
    assert result.warnings


def test_blur_and_normal_detail():
    frame = detailed()
    assert assess_quality(frame).status == QualityStatus.GOOD
    blurred = cv2.GaussianBlur(frame, (31,31), 8)
    result = assess_quality(blurred)
    assert result.status == QualityStatus.DEGRADED
    assert QualityFlag.BLURRED in result.flags
    assert result.blur_score < assess_quality(frame).blur_score


def test_thresholds_configurable_and_validated():
    blurred = cv2.GaussianBlur(detailed(), (31,31), 8)
    assert assess_quality(blurred, QualityConfig(blur_threshold=0, low_contrast=0)).status == QualityStatus.GOOD
    for kwargs in [{'blur_threshold': float('nan')}, {'max_dimension': 0}, {'near_black': 250, 'near_white': 240}]:
        with pytest.raises(ValueError): QualityConfig(**kwargs)


@pytest.mark.parametrize('frame', [None, [], np.zeros((0,5,3),dtype=np.uint8), np.zeros((8,8),dtype=np.uint8),
                                    np.zeros((8,8,4),dtype=np.uint8), np.zeros((8,8,3)), np.full((8,8,3),np.nan)])
def test_invalid_frame_skips_inference(frame):
    infer = MagicMock()
    result = analyze_frame(frame, 'test', inference=infer)
    assert result.status == FrameStatus.INVALID_FRAME
    assert result.detections == [] and result.image_quality is None
    assert result.processing_ms >= 0
    infer.assert_not_called()


def test_inference_error_is_not_no_detection():
    result = analyze_frame(detailed(), 'test', inference=MagicMock(side_effect=RuntimeError('internal secret detail')))
    assert result.status == FrameStatus.INFERENCE_ERROR
    assert result.image_quality is not None
    assert 'internal secret detail' not in result.model_dump_json()


def test_quality_does_not_suppress_detection():
    result = analyze_frame(np.zeros((32,32,3), dtype=np.uint8), 'test', inference=lambda _: [detection()])
    assert result.status == FrameStatus.CONFIRMED_DETECTION
    assert result.image_quality.status == QualityStatus.UNUSABLE
    assert len(result.detections) == 1


@pytest.mark.parametrize('kind,score,should_classify,uncertain', [
    ('person', .8, False, False), ('vehicle', .8, False, False),
    ('animal', .3499, False, True), ('animal', .35, True, False), ('animal', .9, True, False),
])
def test_shared_pipeline_species_gate(kind, score, should_classify, uncertain):
    service = VisionService()
    service._detector = MagicMock()
    service._detector.detect.return_value = [{'class':kind, 'confidence':score, 'bbox':[.1,.1,.8,.8]}]
    service._species = MagicMock()
    service._species.classify_animal_detection.return_value = {
        'species':'tiger', 'confidence':.8, 'top_k':[{'species':'tiger','confidence':.8}]}
    result = service.analyze_frame(detailed(), 'source-independent')
    assert result.detections[0].uncertain is uncertain
    assert service._species.classify_animal_detection.called is should_classify
    assert (result.detections[0].species is not None) is should_classify


def test_bgr_at_detector_and_rgb_at_species_boundary():
    from ml.detector.detector import WildlifeDetector
    from ml.species.classifier import SpeciesClassifier
    frame = np.zeros((32,32,3),dtype=np.uint8)
    frame[:] = [10, 40, 200]
    detector = object.__new__(WildlifeDetector)
    detector.default_conf_threshold = .2
    detector._model = MagicMock()
    detector._model.single_image_detection.return_value = {'detections':None}
    assert detector.detect(frame) == []
    assert detector._model.single_image_detection.call_args.args[0] is frame
    classifier = object.__new__(SpeciesClassifier)
    classifier.min_crop_size = 1
    rgb = np.array(classifier.validate_and_preprocess_crop(frame))
    np.testing.assert_array_equal(rgb[0,0], [200,40,10])
    np.testing.assert_array_equal(frame[0,0], [10,40,200])


def test_api_contract_and_recent_activity_survive_degraded_sample(tmp_path):
    class FakeVision:
        items = [detection()]
        def analyze(self, frame): return self.items
        def status(self): return {'detector_ready':True, 'species_model_ready':False}
    vision = FakeVision()
    buffer = BytesIO()
    Image.new('RGB', (32,32)).save(buffer, format='PNG')
    def upload(client, url):
        response = client.post(url, files={'file':('frame.png',buffer.getvalue(),'image/png')})
        assert response.status_code == 200, response.text
        return response.json()
    with TestClient(create_app(tmp_path/'test.db', vision_service=vision)) as client:
        static = upload(client, '/api/analyze-image')
        assert static['frame_analysis']['status'] == 'CONFIRMED_DETECTION'
        first = upload(client, '/api/cameras/C-18/frame')
        assert first['event_state'] == 'NEW'
        vision.items = []
        missed = upload(client, '/api/cameras/C-18/frame')
        assert missed['event_state'] == 'NO_DETECTION'
        assert missed['frame_analysis']['status'] == 'DEGRADED_FRAME'
        assert missed['recent_activity']['active'] is True
        vision.items = [detection()]
        resumed = upload(client, '/api/cameras/C-18/frame')
        assert resumed['event_state'] == 'CONTINUATION'
        assert resumed['event_id'] == first['event_id']
