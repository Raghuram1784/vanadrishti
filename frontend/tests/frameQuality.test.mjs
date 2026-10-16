// Render the actual live panel with a fake capture hook; no camera or DOM needed.
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
  entryPoints: ['src/components/live/LiveCameraPanel.tsx'],
  bundle: true, write: false, format: 'cjs', platform: 'node', packages: 'external',
  plugins: [{name:'fake-camera', setup(builder) {
    builder.onResolve({filter:/^\.\/useLaptopCamera$/}, () => ({path:'fake-camera',namespace:'test'}));
    builder.onLoad({filter:/.*/,namespace:'test'}, () => ({
      contents:'export function useLaptopCamera() { return globalThis.__qualityFixture; }', loader:'js',
    }));
  }}],
});
const loaded = {exports:{}};
new Function('require','module','exports',bundle.outputFiles[0].text)(createRequire(import.meta.url),loaded,loaded.exports);
const {LiveCameraPanel} = loaded.exports;

function render(quality, {detected=false, recent=false} = {}) {
  const result = {
    event_state:detected ? 'NEW' : 'NO_DETECTION', event_id:detected ? 'event-1' : null,
    timestamp:'2026-10-16T22:00:00+05:30', camera:{id:'C-18'},
    detections:detected ? [{type:'person',score:.9,bbox:[.1,.1,.8,.8],species:null}] : [],
    context:{zone:'CORE',timezone:'Asia/Kolkata',recent_wildlife_events:[]},
    risk:{score:0,level:'LOW',alert:false,reasons:['No retained detections.'],recommended_action:'Continue observation.'},
    recent_activity:recent ? {active:true,type:'person',last_event_id:'prior-event',
      last_risk_level:'HIGH',last_risk_score:75,last_risk_alert:true,
      last_confirmed_at:'2026-10-16T21:59:59+05:30',seconds_since_last_confirmed:1,
      last_risk_reasons:['Existing activity.']} : {active:false},
    frame_analysis:quality ? {status:detected ? 'CONFIRMED_DETECTION' : 'DEGRADED_FRAME',
      image_quality:{status:quality,reasons:quality === 'GOOD' ? [] : ['Low visual detail.']},
      warnings:quality === 'GOOD' ? [] : ['Negative detection does not establish absence.']} : undefined,
  };
  globalThis.__qualityFixture = {latestResult:result,devices:[],diagnostics:{},intervalSec:3,sessionStatus:"OFFLINE",
    running:false,starting:false,paused:false,inFlight:false,selectedDevice:"",
    capturedCount:1,submittedCount:1,skippedCount:0,videoRef:{current:null}};
  globalThis.window = {isSecureContext:true};
  try { return renderToStaticMarkup(React.createElement(LiveCameraPanel)); }
  finally { delete globalThis.__qualityFixture; delete globalThis.window; }
}

for (const quality of ['DEGRADED','UNUSABLE']) {
  test(`${quality} empty sample displays quality warning even with recent risk override`, () => {
    for (const recent of [false,true]) {
      const html = render(quality,{recent});
      assert.ok(html.includes(`Image quality ${quality.toLowerCase()}`));
      assert.ok(html.includes('No detection does not establish that the area is clear'));
      assert.ok(html.includes('Low visual detail.'));
      assert.ok(html.includes('Negative detection does not establish absence.'));
      assert.ok(!html.includes('Sample clear'));
      // Warning is visible in both the sample panel and the risk reasons.
      assert.equal(html.split(`Image quality ${quality.toLowerCase()}`).length - 1, 2);
      if (recent) assert.ok(html.includes('HIGH RISK'));
    }
  });
}

test('confident object stays visible beside poor quality warning', () => {
  const html = render('DEGRADED',{detected:true});
  assert.ok(html.includes('1 object detected'));
  assert.ok(html.includes('Detector score: 0.9000'));
  assert.ok(html.includes('Image quality degraded'));
});

test('good and legacy responses never claim sample clearance', () => {
  for (const quality of ['GOOD',null]) {
    const html = render(quality);
    assert.ok(!html.includes('Sample clear'));
    assert.ok(html.includes('absence not established'));
    if (quality === null) assert.ok(html.includes('Frame quality unavailable'));
    else assert.ok(!html.includes('Image quality degraded'));
  }
});
