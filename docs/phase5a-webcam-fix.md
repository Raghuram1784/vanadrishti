# C-18 webcam startup fix — physical verification pending

15 October 2026. Repository: `C:\Users\Raghu Ram\Desktop\vanadrishti`.

## Diagnosis

The reported “Camera access failed: Not Found” did not identify the failing operation. The previous frontend wrapped getUserMedia, video playback, and backend session registration in one catch block and labeled every failure as camera access. An HTTP 404 containing “Not Found” could therefore look like a browser camera failure. The original physical error's DOMException name was not captured, so its root cause cannot yet be established.

At inspection, neither local server was reachable. Both were started from the current repository; the running backend now advertises the C-18 session and frame routes. This does not prove a stale backend caused the earlier failure.

The previous startup already opened the stream before registering a session. It requested ideal 1280×720 plus `facingMode: "user"`, had no enumeration or device selector, did not explicitly wait for a usable frame, and had no cancellation guard against late startup results. Its 15-second frame request timeout could expire during lazy model loading while backend inference continued.

The existing backend remains intact: C-18 is simulated CORE metadata; sessions are in memory, heartbeats update connectivity with 20/45-second thresholds, clear samples return NO_DETECTION without persistence, repeated primary category/species activity uses the existing 20-second deduplication logic, and meaningful new events retain evidence and existing WebSocket publication. No database, ML, risk, registry, or backend API changes were made for this fix.

## Changed files

- Modified `frontend/src/components/live/LiveCameraPanel.tsx`: preserves the current layout and analysis panels; adds selector, refresh, cancellation, and collapsible diagnostics.
- Added `frontend/src/components/live/useLaptopCamera.ts`: lifecycle and sampling logic extracted from the component, with guarded startup/stop and async cleanup.
- Added `frontend/src/components/live/cameraAccess.ts`: typed enumeration, constraint fallback, error messages, playback readiness, and optional permission query.
- Modified `frontend/src/services/api.ts`: HTTP errors carry status and an ApiError name; live frame timeout now matches image inference at ten minutes.
- Added `frontend/tests/cameraAccess.test.mjs`: lightweight Node tests using the existing TypeScript dependency.
- Added `docs/phase5a-webcam-fix.md`: this report and physical test procedure.

The earlier unfinished Phase 5 staging was not copied into the repository. This change adds no C-21, phone, LAN HTTPS, or correlation functionality.

## Acquisition and lifecycle behavior

Before: `{video:{width:{ideal:1280},height:{ideal:720},facingMode:"user"},audio:false}`.

After, default: `{video:true,audio:false}`.

After, explicitly selected device: `{video:{deviceId:{exact:selectedDeviceId}},audio:false}`. A selected-device NotFoundError or OverconstrainedError retries once using default video. Permission denial, device-in-use, security, and interrupted startup errors are not hidden by repeated fallback attempts. There are no mandatory resolution/FPS constraints and no laptop facingMode constraint.

Enumeration runs when entering Live Field Camera, on refresh/device changes, and before startup. Blank labels use neutral numbered labels. Selection exists only in React memory and is checked against the latest list; missing IDs reset to Default Camera. Zero visible video inputs prevent acquisition and backend session/frame calls. Enumeration has an eight-second timeout rather than an indefinite spinner.

Startup now follows: explicit Start → support/secure-context check → enumerate → acquire stream → attach video → wait for metadata/data, nonzero dimensions, and playback → backend registration → ONLINE → heartbeat/sampling. Video uses autoPlay, muted, and playsInline. Stop/cancel/unmount releases every track, clears the video, invalidates pending startup/results, and closes the backend session. A late camera grant is released; a late session registration is closed. Pending heartbeat completion precedes session closure so it cannot revive the closed lease.

Sampling remains 3 seconds by default with 2/3/5-second options, longest edge 1280 pixels, JPEG quality 0.82. The guard covers canvas encoding and inference. Busy samples are skipped; stopping does not prematurely release an outstanding inference guard. Pause stops new submissions and retains preview. Hidden tabs skip sampling. Submission count increments when a request is sent, not only when it succeeds. Errors appear visibly rather than only in console logs. An already submitted frame may finish after pause/stop; its stale response cannot reactivate the UI.

## Diagnostics and errors

The panel shows API availability, secure context, device count, selected/opened label, active stream, resolution, permission state, startup/failure stage, attempted constraints, and error name. No raw device IDs or JavaScript stacks are displayed. Unsupported Permissions API queries return unknown and never block startup.

Separate safe guidance exists for NotAllowedError, NotFoundError, NotReadableError, OverconstrainedError, AbortError, SecurityError, and playback/enumeration timeouts. Backend failures explicitly identify session registration and HTTP status. Windows troubleshooting appears only when enumeration actually returns zero video inputs.

## Verification

- Full Python suite: **85 tests passed**, including existing Phase 5A session, heartbeat/status, NO_DETECTION, meaningful-event evidence, species/category deduplication, and existing upload regression tests. No existing test was removed or weakened.
- Camera helper tests: **10 passed**, covering named errors, stale IDs, enumeration, default constraints, both fallback errors, non-retriable errors, cancellation cleanup, and preview readiness.
- **`npm run build` passed**, including TypeScript. The existing large JavaScript chunk warning remains nonfatal.
- Browser UI inspection: camera API available, secure context Yes, no capture started, OFFLINE, counters zero. The background in-app browser did not return device enumeration during inspection (count Unknown), so it is not evidence of zero hardware devices. Physical Chrome/Edge enumeration and capture are unverified.
- Real webcam preview, sampled-frame inference, physical pause/resume, and hardware release still require the test below. **Phase 5A is not declared complete. Phase 5B remains blocked.**

## Exact run commands

Both servers were started for this handoff. If restarting, stop their existing processes with Ctrl+C before launching replacements.

Backend PowerShell:

```powershell
Set-Location 'C:\Users\Raghu Ram\Desktop\vanadrishti'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend, separate PowerShell:

```powershell
Set-Location 'C:\Users\Raghu Ram\Desktop\vanadrishti\frontend'
npm run dev
```

Checks from repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test frontend/tests/cameraAccess.test.mjs
npm --prefix frontend run build
```

## Required physical test — stop before Phase 5B

1. Open Windows Camera and confirm the physical webcam works.
2. Close Windows Camera so it releases the device.
3. Open Chrome or Edge at `http://127.0.0.1:5173/monitor` and reload the page.
4. Select LIVE FIELD CAMERA and expand Camera Diagnostics.
5. Keep the tab active. Click Refresh Cameras; confirm at least one video input. Choose Default Camera or an explicit available camera.
6. Click Start Camera; allow camera permission if prompted.
7. Confirm preview appears and diagnostics show a nonzero resolution and Stream active Yes.
8. Confirm C-18 becomes ONLINE only after backend registration.
9. Wait through initial model loading. Confirm Frames Captured and Inference Submissions increase. Busy samples should increase Skipped instead of queuing.
10. Confirm an actual MegaDetector result appears automatically; an animal detection should invoke BioCLIP ranking.
11. Aim at a plain wall and check for NO DETECTION. The detector can produce false positives; record actual output rather than assuming an empty wall guarantees no detections.
12. Show staged person/animal activity. Verify its first meaningful observation is NEW EVENT and has stored evidence.
13. Keep the activity stable within the dedupe window. Confirm CONTINUATION uses the same event ID and Events/Alerts do not gain duplicate records for those samples.
14. Open the persisted event's evidence and confirm context/risk.
15. Pause analysis: preview must remain active, and no new inference submissions should start. An existing request may finish.
16. Resume analysis: submissions should restart.
17. Stop Camera: preview clears, diagnostics show Stream active No, C-18 returns OFFLINE, and the webcam hardware indicator turns off. Confirm Windows Camera can reopen it if needed.

If it fails, report **Video devices found, device label, startup/failure stage, constraint attempted, error name, and the safe error text**. If the count is genuinely zero, the implementation is ready but that OS/browser is not exposing a camera device; follow the conditional Windows guidance. If the stage is Backend session registration with HTTP 404, restart the current Phase 5A backend rather than changing webcam permissions.
