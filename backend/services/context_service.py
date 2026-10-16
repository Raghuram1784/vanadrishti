"""Integration with existing context, event store, and scenario definitions."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
import json

from ml.context import ContextEngine, WildlifeEvent
from backend.services.risk_service import RiskService

ROOT = Path(__file__).resolve().parents[2]
LOCAL_TZ = timezone(timedelta(hours=5, minutes=30), 'Asia/Kolkata')
DEMO_CAMERA_ID = 'CAM-01'
DISCLAIMER = 'Demonstration camera locations; not real Tadoba camera coordinates.'


def local_timestamp(value=None):
    value = value or datetime.now(LOCAL_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ)


def camera_payload(camera, policy=None):
    payload = {**camera.to_dict(), 'id': camera.camera_id, 'zone': camera.zone_type,
               'simulated': True, 'disclaimer': DISCLAIMER}
    if policy:
        payload['policy'] = policy
    return payload


class ContextService:
    def __init__(self, repository, evidence_store=None):
        self.repository = repository
        self.evidence_store = evidence_store
        self.context = ContextEngine.create_default(ROOT / 'config')
        self.lock = RLock()
        for data in repository.restore():
            event = WildlifeEvent.from_dict(data)
            event.timestamp = local_timestamp(event.timestamp)
            self.context.events.add_event(event)

    def camera(self, camera_id):
        camera = self.context.cameras.get(camera_id)
        if camera is None:
            raise KeyError(camera_id)
        return camera

    def _assess(self, context, detections, camera_id, timestamp, authorized_patrol, source, policy=None):
        camera = context.cameras.get(camera_id)
        if camera is None:
            raise KeyError(camera_id)
        if policy is None and hasattr(self, 'repository') and self.repository:
            policy = self.repository.get_camera_policy(camera_id)
        # Explicit false must override registry authorization as well as true.
        if authorized_patrol is not None:
            camera = replace(camera, patrol_authorized=authorized_patrol)
        timestamp = local_timestamp(timestamp)
        event_id = str(uuid4())
        recent = context.events.get_recent_wildlife_events(
            camera_id, context.cameras, before_time=timestamp)
        wildlife = [{'event_id': e.event_id, 'camera_id': e.camera_id,
                     'timestamp': e.timestamp.isoformat(), 'species': e.species,
                     'ranking_score': e.species_score, 'distance_meters': round(distance, 1),
                     'simulated': True} for e, distance in recent]
        # Assess every detection against the same prior history: multiple boxes in
        # one image must not become repeated activity or preceding wildlife events.
        risks, domain = [], []
        for index, detection in enumerate(detections):
            # Uncertain observations never enter risk or recent wildlife history.
            if detection.get('uncertain'):
                continue
            species = detection.get('species') or {}
            event = WildlifeEvent(
                event_id=f'{event_id}:{index}', camera_id=camera_id, timestamp=timestamp,
                object_type=detection['type'], confidence=detection['score'],
                bbox=tuple(detection['bbox']) if detection.get('bbox') else None,
                species=species.get('top1'), species_score=species.get('ranking_score'),
                top_species_candidates=species.get('top3'), zone_type=camera.zone_type,
                patrol_authorized=camera.patrol_authorized)
            isolated = ContextEngine(camera_registry=context.cameras, event_store=deepcopy(context.events))
            risks.append(RiskService(isolated).evaluate(event, camera, zone_policy=policy))
            domain.append(event)
        for event in domain:
            context.events.add_event(event)
        risk = max(risks, key=lambda r: r['score']) if risks else RiskService(context).empty()
        response = {'event_id': event_id, 'timestamp': timestamp.isoformat(),
                    'simulated': True, 'source': source,
                    'camera': camera_payload(camera, policy=policy),
                    'policy': policy,
                    'detections': detections,
                    'context': {'zone': camera.zone_type, 'policy': policy, 'hour': timestamp.hour,
                                'timezone': 'Asia/Kolkata', 'simulated': True,
                                'authorized_patrol': camera.patrol_authorized,
                                'recent_wildlife_events': wildlife}, 'risk': risk}
        return response, [event.to_dict() for event in domain]

    def assess_only(self, detections, camera_id, timestamp=None, authorized_patrol=None, source='live_camera', policy=None):
        """Assess detections against current context without persisting to DB or evidence store."""
        with self.lock:
            context = ContextEngine(camera_registry=self.context.cameras,
                                    event_store=deepcopy(self.context.events))
            entry, _ = self._assess(context, detections, camera_id, timestamp, authorized_patrol, source, policy=policy)
            return entry

    def analyze(self, detections, camera_id, timestamp, authorized_patrol, evidence_bytes=None, source='image', policy=None):
        with self.lock:
            context = ContextEngine(camera_registry=self.context.cameras,
                                    event_store=deepcopy(self.context.events))
            entry = self._assess(context, detections, camera_id, timestamp, authorized_patrol, source, policy=policy)
            metadata = None
            try:
                if evidence_bytes is not None and self.evidence_store is not None:
                    metadata = self.evidence_store.save(entry[0]['event_id'], entry[0]['timestamp'], evidence_bytes)
                    entry[0].update(metadata)
                self.repository.save([entry])
            except Exception:
                if metadata and self.evidence_store is not None:
                    self.evidence_store.remove(metadata['evidence_image_path'])
                raise
            self.context = context
            return entry[0]

    def scenarios(self):
        return {data['scenario_id']: data for path in sorted((ROOT / 'data/demo/scenarios').glob('*.json'))
                for data in [json.loads(path.read_text(encoding='utf-8'))]}

    def run_scenario(self, scenario_id):
        data = self.scenarios()[scenario_id]
        # Demo histories are isolated from live analysis and from other demo runs.
        context = ContextEngine.create_default(ROOT / 'config')
        entries = []
        for raw in data['events']:
            event = WildlifeEvent.from_dict(raw)
            species = None
            if event.species:
                species = {'top1': event.species, 'ranking_score': event.species_score,
                           'top3': [{'label': event.species, 'ranking_score': event.species_score}]}
            detection = {'type': event.object_type, 'score': event.confidence,
                         'bbox': list(event.bbox) if event.bbox else None, 'species': species}
            entries.append(self._assess(context, [detection], event.camera_id,
                                        event.timestamp, event.patrol_authorized, 'demo'))
        self.repository.save(entries)
        return {'scenario_id': scenario_id, 'simulated': True, 'events': [e[0] for e in entries]}
