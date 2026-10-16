import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const root = fileURLToPath(new URL('..', import.meta.url));

// Bundle CameraGridView with mocked API calls
const gridBundle = await build({
  absWorkingDir: root,
  entryPoints: ['src/components/live/CameraGridView.tsx'],
  bundle: true,
  write: false,
  format: 'cjs',
  platform: 'node',
  packages: 'external',
  plugins: [
    {
      name: 'mock-services',
      setup(builder) {
        builder.onResolve({ filter: /@\/services\/api/ }, () => ({
          path: 'mock-api',
          namespace: 'mock',
        }));
        builder.onLoad({ filter: /.*/, namespace: 'mock' }, () => ({
          contents: `
            export const getCameras = async () => ({ cameras: [], simulated: true, disclaimer: '' });
            export const getCameraSessions = async () => globalThis.__mockSessions || [];
            export const getEvents = async () => globalThis.__mockEvents || [];
            export const getCameraPolicy = async (id) => ({ camera_id: id, policy: id === 'C-18' ? 'CRITICAL' : 'RESTRICTED' });
            export const setCameraPolicy = async (id, policy) => ({ camera_id: id, policy, updated_at: '2026-10-16T18:00:00Z' });
          `,
          loader: 'js',
        }));
      },
    },
  ],
});

const loadedGrid = { exports: {} };
new Function('require', 'module', 'exports', gridBundle.outputFiles[0].text)(
  createRequire(import.meta.url),
  loadedGrid,
  loadedGrid.exports,
);
const { CameraGridView } = loadedGrid.exports;

test('CameraGridView renders operational policy dropdowns for real cameras C-18 and C-21', () => {
  globalThis.__mockSessions = [];
  globalThis.__mockEvents = [];

  const html = renderToStaticMarkup(
    React.createElement(CameraGridView, { onSelectCamera: () => {} })
  );

  // Check C-18 and C-21 policy dropdowns are present
  assert.match(html, /aria-label="C-18 operational policy"/);
  assert.match(html, /aria-label="C-21 operational policy"/);
  assert.match(html, /SAFE \/ PUBLIC/);
  assert.match(html, /RESTRICTED/);
  assert.match(html, /CRITICAL \/ SENSITIVE/);

  // Check geographic zones are preserved (CORE ZONE A, BUFFER ZONE WEST)
  assert.match(html, /CORE ZONE A/);
  assert.match(html, /BUFFER ZONE WEST/);
});

test('CameraGridView distinguishes live online hardware from offline historical events', () => {
  // C-18 is ONLINE with recent event; C-21 is OFFLINE with historical event
  globalThis.__mockSessions = [
    { camera_id: 'C-18', status: 'ONLINE', frames_received: 10, frames_analyzed: 10 },
    { camera_id: 'C-21', status: 'OFFLINE', frames_received: 5, frames_analyzed: 5 },
  ];
  globalThis.__mockEvents = [
    {
      event_id: 'evt-c18-live',
      timestamp: '2026-10-16T18:30:00+05:30',
      camera: { id: 'C-18' },
      risk: { level: 'HIGH', score: 72 },
    },
    {
      event_id: 'evt-c21-hist',
      timestamp: '2026-10-16T17:15:00+05:30',
      camera: { id: 'C-21' },
      risk: { level: 'CRITICAL', score: 88 },
    },
  ];

  const html = renderToStaticMarkup(
    React.createElement(CameraGridView, {
      onSelectCamera: () => {},
      initialSessions: globalThis.__mockSessions,
      initialEvents: globalThis.__mockEvents,
    })
  );

  // C-18 shows live stream active
  assert.match(html, /LIVE STREAM ACTIVE/);
  assert.match(html, /HARDWARE ONLINE/);
  assert.match(html, /Live Stream Status:/);

  // C-21 shows offline / standby and historical record
  assert.match(html, /OFFLINE \/ STANDBY/);
  assert.match(html, /HARDWARE OFFLINE/);
  assert.match(html, /Last Recorded Event:/);
  assert.match(html, /Camera offline/);
});

test('CameraGridView clearly labels simulated inactive slots without live footage', () => {
  globalThis.__mockSessions = [];
  globalThis.__mockEvents = [];

  const html = renderToStaticMarkup(
    React.createElement(CameraGridView, { onSelectCamera: () => {} })
  );

  // Simulated cameras CAM-01 to CAM-04 must be clearly marked
  assert.match(html, /CAM-01/);
  assert.match(html, /CAM-02/);
  assert.match(html, /CAM-03/);
  assert.match(html, /CAM-04/);
  assert.match(html, /SIMULATED NODE · INACTIVE/);
  assert.match(html, /SYNTHETIC SECTOR NODE/);
  assert.match(html, /No physical camera hardware connected to this slot/);
});
