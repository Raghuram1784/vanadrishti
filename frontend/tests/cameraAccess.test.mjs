// Uses the existing TypeScript compiler and Node test runner; no test framework dependency.
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = readFileSync(new URL('../src/components/live/cameraAccess.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
const {cameraErrorMessage, validDeviceId, listVideoInputs, openLaptopCamera, waitForPreview} = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
const device = (id, label = '') => ({kind:'videoinput', deviceId:id, label});
test('distinct camera errors map to safe guidance', () => {
  for (const [name, text] of Object.entries({ NotAllowedError:'permission was denied', NotFoundError:'No camera device', NotReadableError:'in use', OverconstrainedError:'settings', AbortError:'interrupted', SecurityError:'security settings' })) {
    assert.ok(cameraErrorMessage(new DOMException('private stack', name)).includes(text));
    assert.ok(!cameraErrorMessage(new DOMException('private stack', name)).includes('private stack'));
  }
});
test('stale selection resets; explicit available selection is retained', () => {
  assert.equal(validDeviceId([device('current')], 'stale'), '');
  assert.equal(validDeviceId([device('current')], 'current'), 'current');
  assert.equal(validDeviceId([], 'current'), '');
});
test('enumeration filters audio while retaining blank labels and empty result', async () => {
  assert.deepEqual(await listVideoInputs({enumerateDevices:async()=>[device('a'), {kind:'audioinput'}]}), [device('a')]);
  assert.deepEqual(await listVideoInputs({enumerateDevices:async()=>[]}), []);
});
test('default acquisition has no facingMode, resolution or FPS constraints', async () => {
  let constraints; const stream = {getTracks:()=>[]};
  assert.equal(await openLaptopCamera({getUserMedia:async c=>{constraints=c;return stream;}}, '', ()=>{}, new AbortController().signal), stream);
  assert.deepEqual(constraints, {video:true,audio:false});
});
for (const name of ['NotFoundError', 'OverconstrainedError']) test(`${name} retries selected camera once with default video`, async () => {
  const calls=[], attempts=[];
  await openLaptopCamera({getUserMedia:async c=>{calls.push(c);if(calls.length===1)throw new DOMException('',name);return {}; }}, 'chosen', a=>attempts.push(a), new AbortController().signal);
  assert.deepEqual(calls,[{video:{deviceId:{exact:'chosen'}},audio:false},{video:true,audio:false}]);
  assert.ok(attempts[1].includes(name));
});
test('denial and unreadable devices do not trigger misleading fallback', async () => {
  for (const name of ['NotAllowedError','NotReadableError','SecurityError','AbortError']) {
    let calls=0;
    await assert.rejects(openLaptopCamera({getUserMedia:async()=>{calls++;throw new DOMException('',name);}}, 'chosen', ()=>{}, new AbortController().signal), {name});
    assert.equal(calls,1);
  }
});
test('late getUserMedia resolution after cancellation releases every track', async () => {
  const controller = new AbortController(); let resolve, stopped=0;
  const pending=openLaptopCamera({getUserMedia:()=>new Promise(r=>resolve=r)}, '', ()=>{},controller.signal);
  controller.abort(); resolve({getTracks:()=>[{stop:()=>stopped++},{stop:()=>stopped++}]});
  await assert.rejects(pending,{name:'AbortError'}); assert.equal(stopped,2);
});
test('preview waits for actual dimensions and loaded data', async () => {
  const video = new EventTarget(); Object.assign(video,{videoWidth:0,videoHeight:0,readyState:0,play:async()=>{}});
  let done=false; const ready=waitForPreview(video,{},new AbortController().signal).then(()=>done=true);
  await Promise.resolve(); assert.equal(done,false);
  Object.assign(video,{videoWidth:640,videoHeight:480,readyState:2}); video.dispatchEvent(new Event('loadeddata'));
  await ready; assert.equal(done,true);
});
test('cancelled preview rejects without waiting for timeout', async () => {
  const video = new EventTarget(); Object.assign(video,{videoWidth:0,videoHeight:0,readyState:0,play:async()=>{}});
  const controller=new AbortController(); const pending=waitForPreview(video,{},controller.signal);controller.abort();
  await assert.rejects(pending,{name:'AbortError'});
});
