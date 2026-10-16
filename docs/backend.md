# Backend · Phase 4C

From the repository root, using Python 3.10+ and the existing virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/docs. Use one worker for this prototype. Models load
lazily on the first relevant request and are reused per process. Health reports
detector/species readiness; a healthy HTTP service does not imply loaded models.
Reloading the process reloads its models. First inference can take several minutes.

## Endpoints

- `GET /health`
- `GET /api/cameras`, `GET /api/cameras/{camera_id}`
- `POST /api/analyze-image`: multipart `file`, optional `camera_id`, `timestamp`,
  and `authorized_patrol`
- `GET /api/events`: optional `camera_id`, `event_type`, `limit` (1–1000)
- `GET /api/alerts`: optional `include_resolved` (also includes false alarms)
- `POST /api/alerts/{alert_id}/action`: JSON `{"action":"REVIEWING"}`
- `GET /api/demo/scenarios`, `POST /api/demo/scenarios/{scenario_id}/run`

All camera locations are simulated demonstration data, not real Tadoba camera
coordinates. API location metadata carries `simulated: true`. CAM-01 is the
designated default demo camera. Timestamps without an offset are India local time;
offset timestamps are converted to Asia/Kolkata before camera schedule evaluation.
Omitted patrol authorization uses the camera registry; explicit false overrides it.

Detection boxes are normalized `[x1,y1,x2,y2]`. The frozen detector retains its
animal 0.20, person 0.25, vehicle 0.50 thresholds. Only animal crops reach BioCLIP;
its values are exposed as `ranking_score`. Invalid/tiny crops retain the animal
detection with `species: null`. No species claim is invented.

All detections are scored by the existing RiskEngine against the same prior
history. The highest scoring detection supplies the image-level risk and reasons.
LOW/MEDIUM generate no API alert; HIGH/CRITICAL require ranger review. The API
adapter changes alert presentation and recommended action only, preserving the
frozen Phase 3 scoring, modules, and tests. Rangers remain the final decision makers.

SQLite stores responses and alert status in `data/vanadrishti.db`; set
`VANADRISHTI_DB` to override. Live domain events restore the existing EventStore on
startup. Demo runs use the existing JSON scenarios and RiskEngine, get fresh IDs,
and persist with `source: demo`, but never contaminate live context or other demos.

Alerts start NEW. Review before assigning a patrol. FALSE_ALARM and RESOLVED are
terminal; repeating the current status is idempotent. No action dispatches anyone.

Uploads support JPEG, PNG, WebP, BMP, TIFF up to 20 MiB and 25 megapixels. Bad
formats return 415, bad images/timestamps/actions 422, unknown IDs 404, oversized
images 413, invalid transitions 409, and model failures 503. Unexpected failures
return a generic 500; details remain in server logs.

## Validation and limitations

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p test_backend.py -v
```

API tests inject vision fixtures; existing detector tests and manual NTLNP requests
exercise real models. This is a local prototype: no authentication, no distributed
context synchronization, no retention policy, and no distributed live delivery. Context is held in
memory, with full live history restored at startup. Use localhost and a single
process. Upload size is checked after multipart parsing; a production proxy would
also need request-body limits. CPU inference is serialized for model safety.

See docs/phase4c.md for stored evidence, event detail, and WebSocket contracts.
