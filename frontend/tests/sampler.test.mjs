import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import ts from 'typescript';
import { build } from 'esbuild';

async function load(relative) {
  const source = readFileSync(new URL(relative, import.meta.url),'utf8');
  const js = ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
  return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
}
const {encodeJpeg} = await load('../src/components/live/frameCapture.ts');
const {uploadCameraFrame} = await load('../src/services/frameRequest.ts');
const blob = () => new Blob(['jpeg'],{type:'image/jpeg'});
const flush = async () => { for(let n=0;n<15;n++) await Promise.resolve(); };

class FakeXHR {
  static instances=[];
  constructor(){ this.upload={}; FakeXHR.instances.push(this); }
  open(){}
  send(form){this.form=form;}
  abort(){this.aborted=true;this.onabort?.();}
  complete(result={event_state:'NO_DETECTION'}){this.status=200;this.responseText=JSON.stringify(result);this.onload?.();}
}

 test('JPEG missing callback times out; late callback ignored; next encode succeeds',async t=>{
  t.mock.timers.enable({apis:['setTimeout']}); let callback;
  const pending=encodeJpeg({toBlob:fn=>callback=fn},new AbortController().signal);
  const rejected=assert.rejects(pending,{name:'TimeoutError'});
  t.mock.timers.tick(5000);await rejected;
  callback(blob());
  assert.equal((await encodeJpeg({toBlob:fn=>fn(blob())},new AbortController().signal)).size,4);
 });
 test('JPEG abort, null and draw/encoder exceptions settle instead of locking',async()=>{
  const abort=new AbortController();let callback;
  const pending=encodeJpeg({toBlob:fn=>callback=fn},abort.signal);
  abort.abort();await assert.rejects(pending,{name:'AbortError'});callback(blob());
  await assert.rejects(encodeJpeg({toBlob:fn=>fn(null)},new AbortController().signal),/empty image/);
  await assert.rejects(encodeJpeg({toBlob:()=>{throw new Error('encoder failed');}},new AbortController().signal),/encoder failed/);
 });
 test('transport times out and aborts even when browser callbacks never arrive',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});globalThis.XMLHttpRequest=FakeXHR;
  const pending=uploadCameraFrame('/frame',new FormData());
  const rejected=assert.rejects(pending,{name:'TimeoutError'});
  const xhr=FakeXHR.instances.at(-1), late=xhr.onload;
  t.mock.timers.tick(120000);await rejected;assert.equal(xhr.aborted,true);
  xhr.status=200;xhr.responseText='{}';late();
 });
 test('transport stages reflect upload completion and response; cancellation detaches late callbacks',async t=>{
  globalThis.XMLHttpRequest=FakeXHR;const stages=[];
  const controller=new AbortController();
  const pending=uploadCameraFrame('/frame',new FormData(),{signal:controller.signal,onUploaded:()=>stages.push('uploaded'),onReceiving:()=>stages.push('receiving')});
  const xhr=FakeXHR.instances.at(-1);xhr.upload.onload();xhr.complete();
  assert.equal((await pending).event_state,'NO_DETECTION');assert.deepEqual(stages,['uploaded','receiving']);
  const second=uploadCameraFrame('/frame',new FormData(),{signal:controller.signal});
  const stale=FakeXHR.instances.at(-1);controller.abort();await assert.rejects(second,{name:'AbortError'});
  assert.equal(stale.aborted,true);assert.equal(stale.onload,null);
 });

// Exercise the actual hook with deterministic state/effect slots and browser fakes.
// Cleanup/setup replay models Strict Mode lifecycle; this is not a physical webcam test.
const root=fileURLToPath(new URL('..',import.meta.url));
const bundle=await build({absWorkingDir:root,entryPoints:['src/components/live/useLaptopCamera.ts'],bundle:true,write:false,platform:'node',format:'cjs',plugins:[{name:'hook-fakes',setup(b){
 b.onResolve({filter:/^(react|sonner|@\/services\/api|@\/lib\/utils)$/},a=>({path:a.path,namespace:'fake'}));
 b.onLoad({filter:/.*/,namespace:'fake'},a=>({loader:'js',contents:a.path==='react'
 ? 'export const useRef=(...a)=>globalThis.__hooks.useRef(...a); export const useState=(...a)=>globalThis.__hooks.useState(...a); export const useEffect=(...a)=>globalThis.__hooks.useEffect(...a); export const useCallback=(...a)=>globalThis.__hooks.useCallback(...a);'
 : a.path==='sonner' ? 'export const toast={success(){},error(){},info(){}};'
 : a.path==='@/lib/utils' ? 'export const message=e=>e.message;'
 : 'export const createCameraSession=(...a)=>globalThis.__api.create(...a); export const closeCameraSession=(...a)=>globalThis.__api.close(...a); export const sendHeartbeat=(...a)=>globalThis.__api.heartbeat(...a); export const postCameraFrame=(...a)=>globalThis.__api.post(...a);'}));
}}]});
const mod={exports:{}};new Function('require','module','exports',bundle.outputFiles[0].text)(createRequire(import.meta.url),mod,mod.exports);
function harness(t){
 t.mock.timers.enable({apis:['setTimeout','setInterval']});
 const previous={window:globalThis.window,document:globalThis.document,xhr:globalThis.XMLHttpRequest};
 globalThis.window={isSecureContext:true}; globalThis.XMLHttpRequest=FakeXHR;
 let callback,drawError=false;
 const canvas={getContext:()=>({drawImage(){if(drawError)throw new Error('draw failed');}}),toBlob:fn=>callback=fn};
 globalThis.document={hidden:false,createElement:()=>canvas};
 const media=new EventTarget();const track={label:'Fake camera',stop(){}};
 media.enumerateDevices=async()=>[{kind:'videoinput',deviceId:'fake',label:'Fake camera'}];
 media.getUserMedia=async()=>({active:true,getTracks:()=>[track],getVideoTracks:()=>[track]});
 const descriptor=Object.getOwnPropertyDescriptor(navigator,'mediaDevices');Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:media});
 let sid=0;const closed=[];
 globalThis.__api={create:async()=>({session_id:`s${++sid}`,status:'ONLINE'}),close:async(_,id)=>closed.push(id),heartbeat:async()=>({status:'ONLINE'}),post:(_,form,options)=>uploadCameraFrame('/frame',form,options)};
 const slots=[];let index=0,pending=[];
 const equal=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
 globalThis.__hooks={
  useState(initial){const i=index++;if(!slots[i])slots[i]={value:initial};return [slots[i].value,v=>slots[i].value=typeof v==='function'?v(slots[i].value):v];},
  useRef(initial){const i=index++;if(!slots[i])slots[i]={current:initial};return slots[i];},
  useCallback(fn,deps){const i=index++;if(!slots[i]||!equal(slots[i].deps,deps))slots[i]={fn,deps};return slots[i].fn;},
  useEffect(fn,deps){const i=index++;if(!slots[i]||!equal(slots[i].deps,deps)){const old=slots[i];slots[i]={deps,fn,cleanup:old?.cleanup};pending.push(()=>{slots[i].cleanup?.();slots[i].cleanup=fn();});}},
 };
 const video=new EventTarget();Object.assign(video,{readyState:2,videoWidth:640,videoHeight:480,play:async()=>{}});
 function render(){index=0;const result=mod.exports.useLaptopCamera();result.videoRef.current=video;const effects=pending;pending=[];effects.forEach(fn=>fn());return result;}
 function cleanup(){slots.forEach(s=>s.cleanup?.());}
 t.after(()=>{cleanup();Object.assign(globalThis,{window:previous.window,document:previous.document,XMLHttpRequest:previous.xhr});if(descriptor)Object.defineProperty(navigator,'mediaDevices',descriptor);else delete navigator.mediaDevices;delete globalThis.__hooks;delete globalThis.__api;});
 return {render,video,track,closed,canvas,callback:()=>callback,drawFail:()=>drawError=true,
   replay(){cleanup();slots.forEach(s=>{if(s.fn&&s.cleanup){s.cleanup=s.fn();}});},
   async start(){await render().startCamera();await flush();return render();},
   async tick(ms){t.mock.timers.tick(ms);await flush();return render();}};
}
// Node has no native XHR; establish a replaceable stub for transport tests above.
globalThis.XMLHttpRequest=FakeXHR;

test('actual sampler releases stalled encoding guard, pauses, and resumes one sample',async t=>{
 const h=harness(t);await h.start();let state=await h.tick(3000);
 assert.equal(state.diagnostics.sampleStage,'Encoding JPEG');assert.equal(state.capturedCount,0);assert.equal(state.submittedCount,0);
 const late=h.callback();state=await h.tick(3000);assert.equal(state.skippedCount,1);
 state=await h.tick(2000);assert.equal(state.inFlight,false);assert.equal(state.paused,true);assert.equal(state.diagnostics.sampleStage,'Timeout');
 late(blob());await flush();assert.equal(h.render().submittedCount,0);
 state.togglePause();await h.tick(1000);h.callback()(blob());await flush();state=h.render();
 assert.equal(state.capturedCount,1);assert.equal(state.submittedCount,1);assert.equal(state.inFlight,true);
 const xhr=FakeXHR.instances.at(-1);xhr.upload.onload();assert.equal(h.render().diagnostics.sampleStage,'Waiting for backend inference');
 xhr.complete();await flush();assert.equal(h.render().inFlight,false);assert.equal(h.render().diagnostics.sampleStage,'Result received');
});
test('request timeout pauses without automatic retry or queue; explicit resume recovers',async t=>{
 const h=harness(t);await h.start();await h.tick(3000);h.callback()(blob());await flush();
 const xhr=FakeXHR.instances.at(-1);let state=await h.tick(120000);
 assert.equal(xhr.aborted,true);assert.equal(state.inFlight,false);assert.equal(state.paused,true);assert.equal(state.submittedCount,1);
 await h.tick(30000);assert.equal(h.render().submittedCount,1);
 state.togglePause();await h.tick(3000);h.callback()(blob());await flush();assert.equal(h.render().submittedCount,2);
 FakeXHR.instances.at(-1).complete();await flush();assert.equal(h.render().inFlight,false);
});
test('stop/restart ignores old encoding callback, old track event, and old finally',async t=>{
 const h=harness(t);await h.start();await h.tick(3000);const old=h.callback(),ended=h.track.onended;
 h.render().stopCamera();await h.start();await h.tick(3000);old(blob());ended();await flush();
 assert.equal(h.render().running,true);assert.equal(h.render().inFlight,true);assert.equal(h.render().submittedCount,0);
 h.callback()(blob());await flush();assert.equal(h.render().submittedCount,1);
 assert.equal(FakeXHR.instances.at(-1).form.get('session_id'),'s2');
});
test('cadence changes keep a single in-flight request; stop ignores late response',async t=>{
 const h=harness(t);await h.start();await h.tick(3000);h.callback()(blob());await flush();const xhr=FakeXHR.instances.at(-1),late=xhr.onload;
 h.render().setIntervalSec(2);h.render();await h.tick(6000);assert.equal(h.render().submittedCount,1);
 h.render().stopCamera();h.render();xhr.status=200;xhr.responseText='{}';late();await flush();
 assert.equal(xhr.aborted,true);assert.equal(h.render().latestResult,null);assert.equal(h.render().inFlight,false);
});
test('readiness waits without locking; draw error releases guard and pauses',async t=>{
 const h=harness(t);await h.start();h.video.readyState=1;let state=await h.tick(3000);
 assert.equal(state.diagnostics.sampleStage,'Waiting for video readiness');assert.equal(state.inFlight,false);
 h.video.readyState=2;h.drawFail();state=await h.tick(3000);assert.equal(state.paused,true);assert.equal(state.inFlight,false);assert.match(state.error,/Drawing frame/);
});
test('effect cleanup/setup replay does not leave a busy guard or duplicate interval',async t=>{
 const h=harness(t);h.render();h.replay();await h.start();await h.tick(3000);h.callback()(blob());await flush();
 assert.equal(h.render().submittedCount,1);FakeXHR.instances.at(-1).complete();await flush();await h.tick(3000);h.callback()(blob());await flush();assert.equal(h.render().submittedCount,2);
});
