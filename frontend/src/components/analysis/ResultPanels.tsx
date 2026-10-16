import { ShieldCheck, Leaf } from "lucide-react";
import type { Event } from "@/types/api";
import { dateTime } from "@/lib/utils";
import { RiskBadge } from "@/components/ui/shared";
export function ResultPanels({ event }: { event: Event }) {
  return (
    <div className="result-panels">
      <section
        className={`panel risk-panel level-${event.risk.level.toLowerCase()}`}
      >
        <div className="panel-heading">
          <h2>
            <ShieldCheck size={17} /> Risk assessment
          </h2>
          <RiskBadge level={event.risk.level} />
        </div>
        <div className="risk-score">
          <strong>{event.risk.score}</strong>
          <span>
            / 100<small>Alert: {String(event.risk.alert)}</small>
          </span>
        </div>
        <ul className="reason-list">
          {event.risk.reasons.map((reason, i) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
        <div className="recommendation">
          <span>RECOMMENDED RANGER ACTION</span>
          <p>{event.risk.recommended_action}</p>
        </div>
      </section>
      <section className="panel context-panel">
        <div className="panel-heading">
          <h2>Environmental context</h2>
          <span className="source-tag">SIMULATED LOCATION</span>
        </div>
        <dl>
          <div>
            <dt>Camera</dt>
            <dd>
              {event.camera.id} · {event.camera.name}
            </dd>
          </div>
          <div>
            <dt>Zone</dt>
            <dd>{event.context.zone}</dd>
          </div>
          <div>
            <dt>Time · IST</dt>
            <dd>{dateTime(event.timestamp)}</dd>
          </div>
          <div>
            <dt>Authorized patrol</dt>
            <dd>{event.context.authorized_patrol ? "Yes" : "No"}</dd>
          </div>
        </dl>
        <div className="context-wildlife">
          <h3>
            <Leaf size={14} />
            Recent wildlife context
          </h3>
          {event.context.recent_wildlife_events.length ? (
            event.context.recent_wildlife_events.map((w) => (
              <p key={w.event_id}>
                {w.species || "Wildlife"} · {w.camera_id} ·{" "}
                {Math.round(w.distance_meters)} m
                <small>{dateTime(w.timestamp)}</small>
              </p>
            ))
          ) : (
            <p>No recent nearby wildlife events recorded.</p>
          )}
        </div>
      </section>
    </div>
  );
}
