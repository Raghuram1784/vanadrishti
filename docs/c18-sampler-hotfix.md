# C-18 sampler hotfix from accepted Phase 1 baseline

Baseline verified: feature/ml-foundation at 8725a9b, clean working tree.
Work branch: hotfix/c18-sampler-recovery, created directly from that commit.

## Confirmed defect and limits of diagnosis

The old hook set busy.current before drawing/encoding and awaited a Promise that
only canvas.toBlob's callback could settle. There was no encoding deadline or
abort listener. If the callback never ran, the finally block never released busy.
Captured/submitted counters advanced only after encoding; every later interval
therefore skipped while both counters stayed zero. Stop deliberately retained the
busy flag, so an unresolved old capture could block a new camera session too.
An old request still pending across restart could also produce zero reset counters
with rising skips. Its independent request timeout was ten minutes and stop did
not cancel that request.

Regression tests reproduce the missing-callback mechanism against the actual hook
with fake video/canvas/transport and deterministic timers. This confirms the code
failure path, not the browser/driver reason for the originally reported stall.
No physical webcam or interactive browser success is claimed.

## Correction

- frameCapture.ts: bounded JPEG encoding (5 seconds), abort handling, empty-result
  errors, synchronous encoder exceptions, timer/listener cleanup, late callback guard.
- useLaptopCamera.ts: per-operation AbortController replaces the unowned boolean;
  only the matching operation/generation can publish a result or clear inFlight.
  Stop/unmount cancels encoding and upload, then invalidates old continuations.
  Track-ended events from old generations cannot stop a replacement stream.
- frameRequest.ts: live-only XHR transport with actual upload-complete and
  response-received milestones, a 120-second total deadline, and explicit abort.
  XHR and watchdog deadlines settle once and detach callbacks/listeners.
- api.ts: preserves postCameraFrame(cameraId, form), adds optional cancellation and
  stage callbacks. Same endpoint, multipart fields, response schema and base URL.
  Other APIs and their timeouts are unchanged. Existing backend CORS permits POST.
- LiveCameraPanel.tsx: two diagnostic rows (sampling stage/error) in the existing
  diagnostics area; no layout redesign or notification subsystem changes.

Stages: Waiting for video readiness, Drawing frame, Encoding JPEG, Uploading frame,
Waiting for backend inference, Receiving result, Result received, Error/Timeout,
and Stopped. Waiting for backend inference begins at upload completion; it includes
server queue/processing/network response time and does not assert server execution
has started. Small stages may pass too quickly to be visibly painted.

Readiness does not acquire the lock. Exactly one capture/request is owned at a time.
Changing cadence replaces only the interval and retains that ownership. Hidden tabs
and paused sampling do not enqueue work. A failed encoder or request clears busy
and pauses sampling; the operator explicitly resumes after resolving the issue.
There are no automatic retries or queued samples.

Aborting the browser request does not promise server cancellation. After an upload
error/timeout, inspect Events and backend status before Resume or restart. A cold
model taking over 120 seconds may trigger this pause. Existing backend inference
serialization and deduplication remain unchanged; this hotfix adds no server jobs.
JavaScript timers cannot preempt a synchronous browser/main-thread hang and may be
throttled in background tabs; test recovery in a foreground responsive tab.

## Regression scope

sampler.test.mjs adds ten tests: missing encoder callback with late completion,
null/throw/abort encoding, stalled request timeout, upload/receive milestones,
actual-hook timeout/recovery and counters, request pause without retries,
stop/restart stale callbacks/track events, cadence single-flight behavior,
video readiness/draw errors, and effect cleanup/setup replay. The hook harness
models lifecycle ordering; it is not a physical browser or full React renderer.
Existing frontend render tests still verify quality and uncertainty presentation.

## Manual browser verification (not yet performed)

1. Start the existing backend and frontend from this hotfix checkout. Reload
   Chrome/Edge on localhost:5173/monitor so old sampler code is removed.
2. Open Camera Diagnostics; Start Camera and allow permission. Confirm preview,
   ONLINE, nonzero video dimensions, and stage progression. Frames Captured and
   Inference Submissions should increase; a result and sample size should appear.
3. In Network, confirm at most one active C-18 /frame request. Change sample cadence
   while a request runs; skips may increase but there must be no queued burst.
4. For a controlled encoder stall in this local demo only, Pause Analysis and wait
   for any request to finish, then run in DevTools:

   ```js
   window.savedC18ToBlob = HTMLCanvasElement.prototype.toBlob;
   HTMLCanvasElement.prototype.toBlob = function () {};
   ```

   Resume. Expect Encoding JPEG, then Timeout after approximately 5 seconds and
   sampling paused. Captured/submitted must not increase; skips must stop rising.
   Restore the encoder before resuming:

   ```js
   HTMLCanvasElement.prototype.toBlob = window.savedC18ToBlob;
   delete window.savedC18ToBlob;
   ```

   Resume and verify a fresh result. Reload also removes the temporary override.
5. Block the /api/cameras/C-18/frame request in DevTools to exercise upload failure.
   Verify an explicit error and paused sampling. Remove the block, verify backend
   status, then Resume. Deterministic tests cover the full no-callback deadline.
6. Stop during capture or upload; confirm request cancellation and camera hardware
   release. Start again; old results must not replace the new session's analysis.
   In development Strict Mode, also navigate away/back and repeat Start/Stop.
7. Cover the lens: quality warnings must remain visible. Restore the scene and use
   staged activity to verify NEW/CONTINUATION and recent-activity continuity.

Only C-18 sampling was corrected. No C-21, Phase 2, maintenance persistence, risk
policy, incident-engine, quality-policy, or notification feature was implemented.
