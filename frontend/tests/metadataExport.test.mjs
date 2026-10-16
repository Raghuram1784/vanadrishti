import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const root = fileURLToPath(new URL('..', import.meta.url));

const bundle = await build({
  absWorkingDir: root,
  entryPoints: ['src/lib/metadataExport.ts'],
  bundle: true,
  write: false,
  format: 'cjs',
  platform: 'node',
  packages: 'external',
});

const loaded = { exports: {} };
new Function('require', 'module', 'exports', bundle.outputFiles[0].text)(
  createRequire(import.meta.url),
  loaded,
  loaded.exports,
);

const {
  formatEventMetadata,
  eventToJson,
  eventsToCsv,
} = loaded.exports;

// Fixtures for testing
const baseCameraC18 = {
  id: 'C-18',
  camera_id: 'C-18',
  name: 'Sector C-18 Trail Camera (Laptop Prototype)',
  latitude: 20.25,
  longitude: 79.363,
  zone: 'CORE ZONE A',
  zone_name: 'Core Conservation Area A',
  zone_type: 'CORE',
  active: true,
  allowed_hours: null,
  patrol_authorized: false,
  policy: 'CRITICAL',
  simulated: true,
  disclaimer: 'Simulated location metadata',
  notes: null,
};

const baseCameraC21 = {
  id: 'C-21',
  camera_id: 'C-21',
  name: 'Sector C-21 Mobile Patrol (Android Hotspot)',
  latitude: 20.275,
  longitude: 79.315,
  zone: 'BUFFER ZONE WEST',
  zone_name: 'Buffer Zone West',
  zone_type: 'BUFFER',
  active: true,
  allowed_hours: null,
  patrol_authorized: true,
  policy: 'RESTRICTED',
  simulated: true,
  disclaimer: 'Simulated location metadata',
  notes: null,
};

test('1. Exporting an event with one person preserves confidence, bbox, and excludes species', () => {
  const event = {
    event_id: 'evt-person-001',
    timestamp: '2026-10-16T18:15:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    policy: 'CRITICAL',
    detections: [
      {
        type: 'person',
        score: 0.94215,
        bbox: [0.12, 0.25, 0.65, 0.8],
        uncertain: false,
        uncertainty_reason: null,
        candidate_signals: [{ type: 'person', score: 0.94 }],
        species: null,
      },
    ],
    context: {
      zone: 'CORE',
      hour: 18,
      timezone: 'Asia/Kolkata',
      simulated: true,
      authorized_patrol: false,
      recent_wildlife_events: [],
    },
    risk: {
      score: 90,
      level: 'CRITICAL',
      alert: true,
      reasons: ['Person detected in critical conservation sector'],
      recommended_action: 'Immediate ranger response required',
    },
  };

  const meta = formatEventMetadata(event);
  assert.equal(meta.event_id, 'evt-person-001');
  assert.equal(meta.camera.id, 'C-18');
  assert.equal(meta.camera.operational_policy, 'CRITICAL');
  assert.equal(meta.detections.length, 1);
  assert.equal(meta.detections[0].type, 'person');
  assert.equal(meta.detections[0].detector_score, 0.94215);
  assert.deepEqual(meta.detections[0].bbox_normalized, [0.12, 0.25, 0.65, 0.8]);
  assert.equal(meta.detections[0].uncertain, false);
  // Species MUST be null for person detections
  assert.equal(meta.detections[0].species, null);
  assert.equal(meta.risk.level, 'CRITICAL');
  assert.equal(meta.risk.score, 90);
});

test('2. Exporting multiple detections preserves individual indices, scores, and classes', () => {
  const event = {
    event_id: 'evt-multi-002',
    timestamp: '2026-10-16T18:20:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC21,
    policy: 'RESTRICTED',
    detections: [
      {
        type: 'person',
        score: 0.885,
        bbox: [0.05, 0.1, 0.4, 0.6],
        uncertain: false,
        species: null,
      },
      {
        type: 'vehicle',
        score: 0.762,
        bbox: [0.45, 0.3, 0.9, 0.85],
        uncertain: false,
        species: null,
      },
    ],
    context: {
      zone: 'BUFFER',
      hour: 18,
      timezone: 'Asia/Kolkata',
      simulated: true,
      authorized_patrol: true,
      recent_wildlife_events: [],
    },
    risk: {
      score: 70,
      level: 'HIGH',
      alert: true,
      reasons: ['Vehicle and human presence detected'],
      recommended_action: 'Verify patrol authorization',
    },
  };

  const meta = formatEventMetadata(event);
  assert.equal(meta.detections.length, 2);
  assert.equal(meta.detections[0].index, 0);
  assert.equal(meta.detections[0].type, 'person');
  assert.equal(meta.detections[0].detector_score, 0.885);
  assert.equal(meta.detections[1].index, 1);
  assert.equal(meta.detections[1].type, 'vehicle');
  assert.equal(meta.detections[1].detector_score, 0.762);
});

test('3. Exporting an animal preserves BioCLIP top species, ranking score, and candidates', () => {
  const event = {
    event_id: 'evt-animal-003',
    timestamp: '2026-10-16T18:25:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    policy: 'SAFE',
    detections: [
      {
        type: 'animal',
        score: 0.965,
        bbox: [0.2, 0.3, 0.7, 0.8],
        uncertain: false,
        species: {
          top1: 'Panthera tigris',
          ranking_score: 0.8924,
          top3: [
            { label: 'Panthera tigris', ranking_score: 0.8924 },
            { label: 'Panthera pardus', ranking_score: 0.0812 },
            { label: 'Cuon alpinus', ranking_score: 0.0153 },
          ],
        },
      },
    ],
    context: {
      zone: 'CORE',
      hour: 18,
      timezone: 'Asia/Kolkata',
      simulated: true,
      authorized_patrol: false,
      recent_wildlife_events: [],
    },
    risk: {
      score: 15,
      level: 'LOW',
      alert: false,
      reasons: ['Tiger activity recorded in core habitat'],
      recommended_action: 'Routine monitoring',
    },
  };

  const meta = formatEventMetadata(event);
  assert.equal(meta.detections[0].type, 'animal');
  assert.ok(meta.detections[0].species);
  assert.equal(meta.detections[0].species.top1, 'Panthera tigris');
  assert.equal(meta.detections[0].species.ranking_score, 0.8924);
  assert.equal(meta.detections[0].species.top3.length, 3);
  assert.equal(meta.detections[0].species.top3[0].label, 'Panthera tigris');
});

test('4. Handling uncertain detections sets uncertain flag and preserves reason', () => {
  const event = {
    event_id: 'evt-uncertain-004',
    timestamp: '2026-10-16T18:27:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    detections: [
      {
        type: 'person',
        score: 0.38,
        bbox: [0.1, 0.1, 0.5, 0.5],
        uncertain: true,
        uncertainty_reason: 'Subject backlit with ambiguous posture',
        candidate_signals: [
          { type: 'person', score: 0.38 },
          { type: 'animal', score: 0.29 },
        ],
        species: null,
      },
    ],
    context: {
      zone: 'CORE',
      hour: 18,
      timezone: 'Asia/Kolkata',
      simulated: true,
      authorized_patrol: false,
      recent_wildlife_events: [],
    },
    risk: {
      score: 10,
      level: 'LOW',
      alert: false,
      reasons: ['Uncertain observation logged without alert escalation'],
      recommended_action: 'Monitor future frames',
    },
  };

  const meta = formatEventMetadata(event);
  assert.equal(meta.detections[0].uncertain, true);
  assert.equal(meta.detections[0].uncertainty_reason, 'Subject backlit with ambiguous posture');
  assert.equal(meta.detections[0].candidate_signals.length, 2);
  assert.equal(meta.risk.alert_required, false);
});

test('5. Handling missing and null fields defaults safely without throwing', () => {
  const minimalEvent = {
    event_id: 'evt-minimal-005',
    timestamp: '2026-10-16T18:30:00+05:30',
    simulated: true,
    source: 'image',
    camera: {
      id: 'CAM-01',
      name: 'Corridor 1',
      latitude: 20.24,
      longitude: 79.36,
      zone: 'CORE',
      zone_type: 'CORE',
    },
    detections: [],
    context: { zone: 'CORE' },
    risk: { score: 0, level: 'LOW', alert: false, reasons: [] },
  };

  const meta = formatEventMetadata(minimalEvent);
  assert.equal(meta.event_id, 'evt-minimal-005');
  assert.equal(meta.detections.length, 0);
  assert.equal(meta.camera.operational_policy, null);
  assert.equal(meta.incident.alert_id, null);
  assert.equal(meta.incident.status, 'NONE');
});

test('6. Maintaining correct normalized bounding box values [x1, y1, x2, y2]', () => {
  const event = {
    event_id: 'evt-bbox-006',
    timestamp: '2026-10-16T18:32:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    detections: [
      {
        type: 'animal',
        score: 0.89,
        bbox: [0.123456, 0.654321, 0.789012, 0.987654],
        uncertain: false,
      },
    ],
    context: { zone: 'CORE' },
    risk: { score: 10, level: 'LOW', alert: false, reasons: [] },
  };

  const meta = formatEventMetadata(event);
  assert.deepEqual(meta.detections[0].bbox_normalized, [0.123456, 0.654321, 0.789012, 0.987654]);
});

test('7. JSON export serializes valid JSON parseable back to structure', () => {
  const event = {
    event_id: 'evt-json-007',
    timestamp: '2026-10-16T18:35:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC21,
    policy: 'RESTRICTED',
    detections: [
      {
        type: 'person',
        score: 0.92,
        bbox: [0.1, 0.2, 0.5, 0.8],
      },
    ],
    context: { zone: 'BUFFER' },
    risk: { score: 65, level: 'HIGH', alert: true, reasons: ['Test human entry'] },
  };

  const jsonStr = eventToJson(event);
  assert.ok(typeof jsonStr === 'string');
  const parsed = JSON.parse(jsonStr);
  assert.equal(parsed.schema_version, '1.0');
  assert.equal(parsed.event_id, 'evt-json-007');
  assert.equal(parsed.camera.id, 'C-21');
  assert.equal(parsed.camera.operational_policy, 'RESTRICTED');
});

test('8. Correct CSV formatting with RFC 4180 escaping and zero-detection preservation', () => {
  const eventWithDetection = {
    event_id: 'evt-csv-008a',
    timestamp: '2026-10-16T18:40:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    policy: 'CRITICAL',
    detections: [
      {
        type: 'person',
        score: 0.95,
        bbox: [0.1, 0.2, 0.6, 0.7],
      },
    ],
    risk: {
      score: 95,
      level: 'CRITICAL',
      alert: true,
      reasons: ['Person detected in critical sector, urgent response needed'],
      recommended_action: 'Dispatch rangers to sector',
    },
  };

  const eventZeroDetections = {
    event_id: 'evt-csv-008b',
    timestamp: '2026-10-16T18:41:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC21,
    policy: 'RESTRICTED',
    detections: [],
    risk: {
      score: 0,
      level: 'LOW',
      alert: false,
      reasons: ['No detections in frame'],
      recommended_action: 'Routine monitoring',
    },
  };

  const csv = eventsToCsv([eventWithDetection, eventZeroDetections]);
  const lines = csv.trim().split('\n');

  // 1 header line + 1 row for eventWithDetection + 1 row for eventZeroDetections = 3 lines
  assert.equal(lines.length, 3);

  // Header verification
  assert.match(lines[0], /event_id,timestamp_iso,camera_id/);
  assert.match(lines[0], /detection_type,detector_score,bbox_x1/);

  // Line 1: Person detection
  assert.match(lines[1], /evt-csv-008a/);
  assert.match(lines[1], /C-18/);
  assert.match(lines[1], /person/);
  assert.match(lines[1], /0\.95/);

  // Line 2: Zero detections retained with 'none'
  assert.match(lines[2], /evt-csv-008b/);
  assert.match(lines[2], /C-21/);
  assert.match(lines[2], /none/);
});

test('9. Separating C-18 and C-21 records retains distinct hardware attribution and policies', () => {
  const eventC18 = {
    event_id: 'evt-c18-test',
    timestamp: '2026-10-16T18:45:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC18,
    policy: 'CRITICAL',
    detections: [{ type: 'animal', score: 0.91, species: { top1: 'Axis axis', ranking_score: 0.85 } }],
    risk: { score: 10, level: 'LOW', alert: false, reasons: ['Deer activity'] },
  };

  const eventC21 = {
    event_id: 'evt-c21-test',
    timestamp: '2026-10-16T18:46:00+05:30',
    simulated: true,
    source: 'live_camera',
    camera: baseCameraC21,
    policy: 'RESTRICTED',
    detections: [{ type: 'person', score: 0.89 }],
    risk: { score: 75, level: 'HIGH', alert: true, reasons: ['Human presence in restricted area'] },
  };

  const metaC18 = formatEventMetadata(eventC18);
  const metaC21 = formatEventMetadata(eventC21);

  assert.equal(metaC18.camera.id, 'C-18');
  assert.match(metaC18.camera.hardware_node, /Laptop Webcam/);
  assert.equal(metaC18.camera.operational_policy, 'CRITICAL');

  assert.equal(metaC21.camera.id, 'C-21');
  assert.match(metaC21.camera.hardware_node, /Android Mobile Patrol/);
  assert.equal(metaC21.camera.operational_policy, 'RESTRICTED');
});
