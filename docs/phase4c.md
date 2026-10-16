# VanaDrishti Phase 4C completion report

Implemented in the existing repository at `C:\Users\Raghu Ram\Desktop\vanadrishti`. Existing detector, BioCLIP, context scoring, five scenarios, and ethical wording are preserved.

## Persistence and API

Original uploaded bytes are stored at `data/evidence/YYYY/MM/<generated-event-uuid>.<detected-extension>`. The filename is generated independently of the uploaded filename. No labels are burned into images. A temporary file is flushed and atomically renamed; failed database writes remove its evidence file. Failed model calls create no evidence.

SQLite retains its existing tables and JSON payload design. Additive event fields are `evidence_image_path`, `evidence_image_url`, and `evidence_media_type`. Alerts expose an optional `evidence_image_url` and source. No SQL migration or image blobs are needed. Old records remain readable with absent/null evidence. OpenAPI event and alert response schemas document these fields.

`GET /api/evidence/{event_id}` looks up a canonical UUID in the database and resolves its stored relative path inside the evidence root. Missing IDs, missing images, traversal attempts, and paths outside that root return 404. `GET /api/events/{event_id}` retrieves full details directly, including older events outside list windows.

The default database is `data/vanadrishti.db`; `VANADRISHTI_DB` overrides it. Evidence defaults to the database directory's `evidence` subdirectory; `VANADRISHTI_EVIDENCE_DIR` overrides that root. Back up the database and evidence directory together.

## Live updates

Endpoint: `ws://127.0.0.1:8000/ws/events`.

Messages are JSON envelopes:

```json
{"type":"event.created","data":{"event_id":"...","evidence_image_url":"/api/evidence/..."}}
{"type":"alert.created","data":{"id":"...","risk_level":"CRITICAL","status":"NEW","evidence_image_url":null}}
{"type":"alert.updated","data":{"id":"...","risk_level":"CRITICAL","status":"REVIEWING"}}
```

The examples abbreviate data: event messages contain the full event, and alert messages contain the full alert. Domain messages are published only after successful SQLite commits. LOW/MEDIUM create no alert messages. Idempotent or rejected actions produce no status-change message. A failed broadcast does not undo committed evidence.

The server sends `connection.ready` with `data.resync=true`; text `ping` receives `connection.pong`. Browser origins are restricted to the existing localhost/127.0.0.1 frontend ports 3000 and 5173. Client queues are bounded; slow consumers reconnect and resync.

The frontend connects once per app, applies event/alert updates, shows appropriate HIGH/CRITICAL toasts, and updates an open alert drawer. It reconnects with exponential backoff (1–30 seconds plus jitter), uses heartbeat checks, cleans up on unmount, and refreshes REST data on connection. Existing REST polling remains the fallback.

## Frontend changes

Monitor uses stored evidence after analysis and restores its last event ID from session storage after refresh. Events indicate image availability and show original evidence, overlays, detections, species Top-3, context, risk, reasons, timestamp, and camera. Alerts retrieve the associated event directly and use the same evidence component. Missing/legacy/demo evidence displays “No stored image evidence for this event.”

The prototype banner and Monitor sequence are explicit. Health is checked before inference. Cold model requests show the required initialization messages without fake percentages; successful analysis shows the event ID and evidence/alert outcome. Demo events remain source-labeled and isolated from live context.

## Files created

- `backend/api/evidence.py`
- `backend/api/live.py`
- `backend/services/evidence_service.py`
- `backend/services/live_service.py`
- `frontend/src/components/analysis/EventEvidence.tsx`
- `frontend/src/hooks/useLiveUpdates.ts`
- `tests/test_evidence.py`
- `tests/test_live.py`
- `docs/phase4c.md`

## Files modified

- `backend/main.py`
- `backend/api/analyze.py`, `backend/api/events.py`, `backend/api/alerts.py`
- `backend/db/database.py`, `backend/schemas/api.py`
- `backend/services/context_service.py`
- `frontend/src/types/api.ts`, `frontend/src/services/api.ts`
- `frontend/src/hooks/usePolling.ts`, `useEvents.ts`, `useAlerts.ts`
- `frontend/src/components/analysis/DetectionImage.tsx`
- `frontend/src/components/alerts/AlertDrawer.tsx`
- `frontend/src/components/events/EventTable.tsx`
- `frontend/src/components/layout/Layout.tsx`
- `frontend/src/pages/Monitor.tsx`, `Events.tsx`, `Alerts.tsx`
- `frontend/src/index.css`, `frontend/README.md`
- `requirements.txt`, `.gitignore`, `docs/backend.md`

## Verification on 14 October 2026

- **77 Python tests pass**, retaining all 62 previous tests and adding 15 evidence/WebSocket tests. Final run: 11.153 seconds.
- **`npm run build` passes**, including TypeScript checks. Vite build: 7.56 seconds. Existing large-bundle warning remains (~935 kB JavaScript before gzip).
- Clean backend/frontend restart; five simulated cameras confirmed.
- Real NTLNP `AmurLeopard_106.jpg` analyzed through the browser. Event: `20ecdd45-fec4-4d15-b941-7e46b5637c7f`.
- Two actual detector scores: **0.8511** and **0.3188**. First crop Top-3: Indian leopard **0.9997**, Bengal tiger **0.0002**, dhole / Indian wild dog **0.0001**. Second crop Top-3: gaur **0.2183**, dhole / Indian wild dog **0.2152**, sloth bear **0.2053**. These are model rankings, not calibrated probabilities; the second detection/ranking is retained as model output, not asserted ground truth.
- Context CAM-01, CORE, unauthorized patrol false; risk **LOW / 0**, no alert. Original image served from the evidence endpoint at its natural width of 1280 pixels.
- Monitor refresh retained the image. Events detail displayed it with overlays and all analysis fields after backend and frontend restarts.
- Running the CRITICAL human-presence scenario in one tab immediately added an alert and WebSocket-only toast in another. Event: `fa21a095-9211-4e0c-9256-ce5f001e492a`. Changing it to REVIEWING immediately updated the second tab's open drawer. The persisted state remained after restart.
- With the backend temporarily launched using `--ws none`, the frontend showed Reconnecting while REST lists and stored image details continued working. Normal transport was restored; the existing tab returned to Connected.
- Alert image display was manually checked against a separate database and temporary ports 8001/3000 using a synthetic red PNG and controlled test detector output. The image loaded at 320 pixels wide inside the alert drawer. This was UI QA, not a real model result, and did not alter the demonstration database. Temporary fixture servers were stopped. Actual demo alerts correctly showed the missing-evidence fallback.

## Run commands

Backend terminal:

```powershell
Set-Location 'C:\Users\Raghu Ram\Desktop\vanadrishti'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location 'C:\Users\Raghu Ram\Desktop\vanadrishti\frontend'
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Use one backend process/worker. For verification:

```powershell
# Repository root
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# frontend directory
npm run build
```

## Known limitations

This remains a localhost, single-process prototype. There is no message broker, durable socket replay, authentication, external notification, or camera streaming. REST resync recovers missed messages. Evidence has no retention policy; an abrupt process crash between file write and database commit can leave an orphan file. Existing records cannot acquire images that were never saved. Monitor's last-event selection is per browser session; all saved events remain available in Events. CPU first-load inference is slow. Map tiles require internet access. No additional feature phase was started.
