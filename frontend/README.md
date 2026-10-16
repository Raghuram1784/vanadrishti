# VanaDrishti frontend · Phase 4C

React + Vite + TypeScript + Tailwind CSS, shadcn/ui (Radix primitives), Recharts,
and React Leaflet / OpenStreetMap. Uses REST for durable state and WebSockets for incremental live updates.

## Run locally

Backend, from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The Vite port is fixed to 5173 so the existing backend
CORS settings work. Use Node 22+. For another backend, copy `.env.example` to
`.env.local`, set `VITE_API_BASE_URL`, and restart Vite. The default is
`http://127.0.0.1:8000`.

```powershell
npm run build
```

The build emits `dist/`. Previewing on a different port requires allowing that
origin in backend CORS; the supported demonstration command is `npm run dev`.

## Screens

- `/`: API-backed counts, risk distribution, all five simulated map markers,
  recent activity. Counts explicitly describe their data window.
- `/monitor`: JPEG/PNG upload, simulated camera and optional IST timestamp /
  patrol authorization, actual model inference, normalized XYXY overlays,
  exact species labels and top-three ranking scores, context and risk panels.
  Includes the five existing demo scenarios and their API results.
- `/alerts`: persisted HIGH/CRITICAL queue, detail drawer, allowed review status
  actions. FALSE_ALARM and RESOLVED require confirmation. No dispatch occurs.
- `/events`: camera/type API filters, 25/50/100 limit, search and risk filters
  within the fetched window, event detail drawer.

## Contracts and behavior

- `src/services/api.ts` centralizes every API call. GET calls time out after
  20 seconds; image inference has a 10-minute timeout. A timed-out POST may
  still complete on the server; check Events before retrying.
- Health refreshes every 10 seconds. Events and alerts refresh every 15 seconds,
  cameras every 30 seconds, scenarios every minute. Hidden tabs skip interval
  refreshes. Successful mutations also trigger refreshes.
- Standby means a model has not initialized; it is not an error. Loading shows
  elapsed time without fabricated stages or percentages.
- Bounding boxes use the existing normalized `[x1,y1,x2,y2]` contract. CSS
  percentages are anchored to the displayed image, including its actual aspect
  ratio. Each detection has an indexed label and a matching result card.
- All locations and scenarios are prominently labeled simulated. Real image
  analysis results remain labeled IMAGE ANALYSIS, with simulated camera context.
- Risk scores/reasons/actions come directly from the API. The browser does not
  implement a second scoring engine or replace species labels.
- API errors appear as readable toasts; stale data is identified in error
  banners. No raw server traces are displayed.
- The shadcn Button was installed with its official CLI and adapted to the
  project's existing `cn` helper and scoped Radix Slot package. The drawer and
  confirmation dialog use accessible Radix Dialog primitives with shadcn styling.

## Known prototype limits

- Local prototype only: no authentication, streaming, external notifications, or deployment.
- Original evidence is stored by the backend. Monitor restores its last event ID
  from session storage; Events and Alerts load evidence by event ID.
- Live updates reconnect with backoff and REST resynchronization. Existing polling
  remains available when WebSockets are disconnected.
- Overview uses the latest 100 events. Search and risk filters on Events apply
  to the requested 25/50/100-result window, not the entire database.
- OpenStreetMap tiles require internet access. A tile-failure notice is provided;
  camera metadata and markers continue to come from the local API.
- Build succeeds with a Vite warning about the combined chart/map JavaScript
  bundle size. This local prototype has not been optimized for public deployment.

## Verified judge flow

Open Overview → Monitor → upload local `AmurLeopard_106.jpg` → select CAM-01 →
Analyze → inspect both retained detections, top-three species rankings, and LOW
risk → run `Unauthorized Human Presence in Core Habitat at Night` → observe
CRITICAL / 95 / alert=true → Alerts → Review alert → REVIEWING → reload and
verify persisted status. All 77 Python tests pass, including 15 evidence and live-update tests. See ../docs/phase4c.md.
