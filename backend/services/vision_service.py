"""Thin, lazy, serialized adapter to the frozen vision modules."""
import os
import math
from functools import lru_cache
from threading import Lock


class VisionService:
    def __init__(self, species_min_detector_score=None):
        self.species_min_detector_score = float(
            species_min_detector_score if species_min_detector_score is not None else
            os.environ.get("SPECIES_CLASSIFICATION_MIN_DETECTOR_SCORE", "0.35"))
        if not math.isfinite(self.species_min_detector_score) or not .20 <= self.species_min_detector_score <= 1:
            raise ValueError("Species detector gate must be between 0.20 and 1.0")
        self._detector = None
        self._species = None
        self._lock = Lock()

    def status(self):
        return {'detector_ready': self._detector is not None,
                'species_model_ready': self._species is not None}

    def analyze(self, frame):
        # The lock also protects the existing non-thread-safe species accessor.
        with self._lock:
            if self._detector is None:
                from ml.detector.detector import get_detector
                self._detector = get_detector()
            candidates = []
            retained = self._detector.detect(frame, conf_threshold=0.20, candidate_sink=candidates)
            result = []
            for item in retained:
                detection = {'type': item['class'], 'score': item['confidence'],
                             'bbox': item['bbox'], 'species': None}
                rivals = [c for c in candidates
                          if {item['class'], c['class']} == {'animal', 'person'}
                          and c['confidence'] >= max(.10, item['confidence'] * .5)
                          and box_iou(item['bbox'], c['bbox']) >= .5]
                if rivals:
                    detection.update(uncertain=True,
                        uncertainty_reason='Competing animal and person signals. Ranger review recommended.',
                        candidate_signals=[{'type': item['class'], 'score': item['confidence']}] +
                            [{'type': c['class'], 'score': round(c['confidence'], 4)} for c in rivals])
                elif item['class'] == 'animal' and item['confidence'] < self.species_min_detector_score:
                    detection.update(uncertain=True,
                        uncertainty_reason='Insufficient detector confidence for reliable species ranking.')
                if item['class'] == 'animal' and not detection.get('uncertain'):
                    if self._species is None:
                        from ml.species.classifier import get_species_classifier
                        self._species = get_species_classifier()
                    prediction = self._species.classify_animal_detection(
                        {'class_name': item['class'], 'bbox': item['bbox']}, frame, top_k=3)
                    if prediction is not None:
                        detection['species'] = {
                            'top1': prediction['species'],
                            'ranking_score': prediction['confidence'],
                            'top3': [{'label': p['species'], 'ranking_score': p['confidence']}
                                     for p in prediction['top_k']]}
                result.append(detection)
            return result


def box_iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union if union > 0 else 0


@lru_cache(maxsize=1)
def get_vision_service():
    return VisionService()
