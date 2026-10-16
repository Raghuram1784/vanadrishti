from datetime import datetime, timezone
import json
import sqlite3
import logging
from threading import RLock
from backend.db.models import TRANSITIONS


class Repository:
    def __init__(self, path, publish=None):
        self.publish = publish
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, camera_id TEXT NOT NULL,
                source TEXT NOT NULL, payload TEXT NOT NULL, domain_events TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS camera_policies (
                camera_id TEXT PRIMARY KEY, policy TEXT NOT NULL);
        ''')

    def close(self):
        self.connection.close()

    def restore(self):
        with self.lock:
            rows = self.connection.execute(
                "SELECT domain_events FROM events WHERE source IN ('image', 'live_camera') ORDER BY timestamp, rowid").fetchall()
        return [event for row in rows for event in json.loads(row[0])]

    def save(self, entries):
        messages = []
        with self.lock, self.connection:
            for response, domain_events in entries:
                self.connection.execute('INSERT INTO events VALUES (?,?,?,?,?,?)', (
                    response['event_id'], response['timestamp'], response['camera']['id'],
                    response['source'], json.dumps(response), json.dumps(domain_events)))
                messages.append({'type': 'event.created', 'data': response})
                risk = response['risk']
                if risk['alert']:
                    policy = response.get('policy') or response.get('camera', {}).get('policy')
                    if not policy:
                        policy = self.get_camera_policy(response['camera']['id'])
                    alert = {'id': response['event_id'], 'timestamp': response['timestamp'],
                             'camera_id': response['camera']['id'], 'simulated': True,
                             'risk_score': risk['score'], 'risk_level': risk['level'],
                             'reasons': risk['reasons'], 'status': 'NEW',
                             'source': response['source'],
                             'policy': policy,
                             'evidence_image_url': response.get('evidence_image_url')}
                    self.connection.execute('INSERT INTO alerts VALUES (?,?,?)',
                                            (alert['id'], 'NEW', json.dumps(alert)))
                    messages.append({'type': 'alert.created', 'data': alert})
        self._notify(messages)

    def _notify(self, messages):
        if self.publish:
            try:
                self.publish(messages)
            except Exception:
                # Broadcast failure must never roll back an already committed event.
                logging.getLogger(__name__).exception('Live update failed; REST remains available')

    def event(self, event_id):
        with self.lock:
            row = self.connection.execute('SELECT payload FROM events WHERE id=?', (event_id,)).fetchone()
        if row is None:
            raise KeyError(event_id)
        return json.loads(row[0])

    def events(self, camera_id=None, event_type=None, limit=100):
        query = 'SELECT payload FROM events WHERE 1=1'
        args = []
        if camera_id:
            query += ' AND camera_id=?'
            args.append(camera_id)
        if event_type:
            query += " AND EXISTS (SELECT 1 FROM json_each(events.payload, '$.detections') WHERE json_extract(value, '$.type')=?)"
            args.append(event_type)
        query += ' ORDER BY timestamp DESC, rowid DESC LIMIT ?'
        args.append(limit)
        with self.lock:
            return [json.loads(row[0]) for row in self.connection.execute(query, args)]

    def alerts(self, include_resolved=False):
        query = 'SELECT payload FROM alerts'
        if not include_resolved:
            query += " WHERE status NOT IN ('RESOLVED','FALSE_ALARM')"
        query += " ORDER BY json_extract(payload, '$.timestamp') DESC, rowid DESC"
        with self.lock:
            return [json.loads(row[0]) for row in self.connection.execute(query)]

    def action(self, alert_id, action):
        with self.lock, self.connection:
            row = self.connection.execute('SELECT payload FROM alerts WHERE id=?', (alert_id,)).fetchone()
            if row is None:
                raise KeyError(alert_id)
            alert = json.loads(row[0])
            previous_status = alert['status']
            if action != alert['status'] and action not in TRANSITIONS[alert['status']]:
                raise ValueError('Invalid alert status transition')
            alert['status'] = action
            alert['updated_at'] = datetime.now(timezone.utc).isoformat()
            self.connection.execute('UPDATE alerts SET status=?, payload=? WHERE id=?',
                                    (action, json.dumps(alert), alert_id))
        if previous_status != action:
            self._notify([{'type': 'alert.updated', 'data': alert}])
        return alert

    def get_camera_policy(self, camera_id: str) -> str | None:
        with self.lock:
            row = self.connection.execute(
                'SELECT policy FROM camera_policies WHERE camera_id=?', (camera_id,)
            ).fetchone()
        if row and row[0]:
            return row[0]
        # Real cameras have default operational alert policies
        if camera_id == 'C-18':
            return 'CRITICAL'
        elif camera_id == 'C-21':
            return 'RESTRICTED'
        return None

    def set_camera_policy(self, camera_id: str, policy: str) -> str:
        policy_upper = (policy or '').strip().upper()
        if policy_upper not in ('SAFE', 'RESTRICTED', 'CRITICAL'):
            raise ValueError(f"Invalid policy '{policy}'. Must be one of SAFE, RESTRICTED, CRITICAL")
        with self.lock, self.connection:
            self.connection.execute(
                'INSERT OR REPLACE INTO camera_policies (camera_id, policy) VALUES (?, ?)',
                (camera_id, policy_upper),
            )
        return policy_upper

    def get_all_camera_policies(self) -> dict[str, str]:
        with self.lock:
            rows = self.connection.execute('SELECT camera_id, policy FROM camera_policies').fetchall()
        result = {'C-18': 'CRITICAL', 'C-21': 'RESTRICTED'}
        for cid, pol in rows:
            result[cid] = pol
        return result
