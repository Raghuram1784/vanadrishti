// Focused regression test: C-21 mobile patrol bounding-box rendering using DetectionImage
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const root = fileURLToPath(new URL('..', import.meta.url));
const bundle = await build({
  absWorkingDir: root,
  entryPoints: ['src/components/live/MobileCameraPanel.tsx'],
  bundle: true,
  write: false,
  format: 'cjs',
  platform: 'node',
  packages: 'external',
  plugins: [
    {
      name: 'fake-camera',
      setup(builder) {
        builder.onResolve({ filter: /^\.\/useLaptopCamera$/ }, () => ({
          path: 'fake-camera',
          namespace: 'test',
        }));
        builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({
          contents: `
            export function useLiveCamera() { return globalThis.__mobileCameraFixture; }
            export function useLaptopCamera() { return globalThis.__mobileCameraFixture; }
          `,
          loader: 'js',
        }));
      },
    },
  ],
});

const loaded = { exports: {} };
new Function('require', 'module', 'exports', bundle.outputFiles[0].text)(
  createRequire(import.meta.url),
  loaded,
  loaded.exports,
);
const { MobileCameraPanel } = loaded.exports;

function renderMobilePanel({
  analyzedFrameUrl = null,
  detections = [],
  running = false,
} = {}) {
  const result = analyzedFrameUrl
    ? {
        event_state: detections.length ? 'NEW' : 'NO_DETECTION',
        event_id: 'evt-c21-test-1234',
        timestamp: '2026-10-16T18:00:00+05:30',
        camera: { id: 'C-21' },
        detections,
        context: { zone: 'BUFFER', timezone: 'Asia/Kolkata', recent_wildlife_events: [] },
        risk: {
          score: detections.length ? 75 : 0,
          level: detections.length ? 'HIGH' : 'LOW',
          alert: detections.length > 0,
          reasons: detections.length ? ['Detection confirmed.'] : ['No detections.'],
          recommended_action: 'Monitor corridor.',
        },
      }
    : null;

  globalThis.__mobileCameraFixture = {
    running,
    starting: false,
    paused: false,
    sessionStatus: running ? 'ONLINE' : 'OFFLINE',
    intervalSec: 3,
    inFlight: false,
    capturedCount: 5,
    submittedCount: 5,
    skippedCount: 0,
    lastBlobSize: 45000,
    lastLatencyMs: 140,
    latestResult: result,
    analyzedFrameUrl,
    selectedDevice: '',
    devices: [],
    diagnostics: { resolution: '1280x720', sampleStage: 'Completed' },
    videoRef: { current: null },
    startCamera: () => {},
    stopCamera: () => {},
    togglePause: () => {},
    setSelectedDevice: () => {},
  };
  globalThis.window = {
    isSecureContext: true,
    location: { hostname: '192.168.1.10', protocol: 'http:' },
  };

  try {
    return renderToStaticMarkup(React.createElement(MobileCameraPanel));
  } finally {
    delete globalThis.__mobileCameraFixture;
    delete globalThis.window;
  }
}

test('C-21 renders DetectionImage with normalized bounding boxes when detections exist', () => {
  const html = renderMobilePanel({
    analyzedFrameUrl: 'blob:http://localhost:5173/sample-c21-frame',
    detections: [
      {
        type: 'person',
        score: 0.92,
        bbox: [0.125, 0.25, 0.625, 0.75], // left 12.5%, top 25%, width 50%, height 50%
        species: null,
      },
    ],
  });

  // 1. DetectionImage container & coordinate space rendered
  assert.ok(html.includes('image-coordinate-space'), 'Must render image-coordinate-space');
  assert.ok(html.includes('src="blob:http://localhost:5173/sample-c21-frame"'), 'Must render analyzed frame URL in img');

  // 2. Detection box rendered with accurate calculated percentages
  assert.ok(html.includes('detection-box box-person'), 'Must render detection box with box-person class');
  assert.ok(/left:\s*12\.5%/.test(html), 'Must compute left normalized percentage');
  assert.ok(/top:\s*25%/.test(html), 'Must compute top normalized percentage');
  assert.ok(/width:\s*50%/.test(html), 'Must compute width normalized percentage');
  assert.ok(/height:\s*50%/.test(html), 'Must compute height normalized percentage');

  // 3. Label rendered
  assert.ok(html.includes('box-label'), 'Must render box-label element');
  assert.ok(html.includes('person'), 'Must include detection label');

  // 4. Viewfinder remains distinct from analyzed snapshot
  assert.ok(html.includes('<video'), 'Must maintain separate video viewfinder');
  assert.ok(html.includes('mobile-analyzed-wrap'), 'Must use mobile-analyzed-wrap for responsive frame scaling');
});

test('C-21 renders no detection boxes when sample has no detections', () => {
  const html = renderMobilePanel({
    analyzedFrameUrl: 'blob:http://localhost:5173/empty-sample',
    detections: [],
  });

  // DetectionImage is rendered for the frame
  assert.ok(html.includes('image-coordinate-space'), 'Image coordinate space is present');
  assert.ok(html.includes('src="blob:http://localhost:5173/empty-sample"'), 'Frame URL is loaded');

  // No detection box rendered
  assert.ok(!html.includes('detection-box'), 'No detection boxes rendered on empty frame');
  assert.ok(html.includes('No objects detected in the latest frame sample'), 'Summary note displays');
});

test('C-21 waiting state when no analyzed frame is available yet', () => {
  const html = renderMobilePanel({
    analyzedFrameUrl: null,
    detections: [],
  });

  assert.ok(!html.includes('image-coordinate-space'), 'No image coordinate space before first sample');
  assert.ok(html.includes('Waiting for first sampled frame from Node C-21'), 'Displays waiting notice');
});
