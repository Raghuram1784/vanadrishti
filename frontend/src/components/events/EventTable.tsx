import type { Alert, Event } from "@/types/api";
import { dateTime, statusLabel } from "@/lib/utils";
import { Empty, RiskBadge } from "@/components/ui/shared";
export function EventTable({
  events,
  alerts = [],
  onSelect,
}: {
  events: Event[];
  alerts?: Alert[];
  onSelect?: (event: Event) => void;
}) {
  if (!events.length)
    return (
      <Empty title="No events yet">
        Analyze an image or run a demo scenario to begin the activity history.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>TIME · IST</th>
            <th>CAMERA</th>
            <th>OBSERVATION</th>
            <th>RISK</th>
            <th>ALERT STATUS</th>
            <th>SOURCE</th>
            <th>EVIDENCE</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const alert = alerts.find((a) => a.id === event.event_id);
            return (
              <tr key={event.event_id}>
                <td>
                  {onSelect ? (
                    <button
                      className="table-link"
                      onClick={() => onSelect(event)}
                    >
                      {dateTime(event.timestamp)}
                    </button>
                  ) : (
                    dateTime(event.timestamp)
                  )}
                </td>
                <td>
                  <strong>{event.camera.id}</strong>
                  <small>{event.camera.zone}</small>
                </td>
                <td>
                  <span className="capitalize">
                    {[...new Set(event.detections.map((d) => d.type))].join(
                      ", ",
                    ) || "No detections"}
                  </span>
                  <small>
                    {event.detections
                      .flatMap((d) => (d.species ? [d.species.top1] : []))
                      .join(", ") || "—"}
                  </small>
                </td>
                <td>
                  <RiskBadge level={event.risk.level} />
                </td>
                <td>
                  <span className="status-text">
                    {alert
                      ? statusLabel(alert.status)
                      : event.risk.alert
                        ? "Alert recorded"
                        : "No alert"}
                  </span>
                </td>
                <td>
                  <span className="source-tag">
                    {event.source === "demo"
                      ? "SIMULATED SCENARIO"
                      : "IMAGE ANALYSIS"}
                  </span>
                </td>
                <td>{event.evidence_image_url ? 'Stored image' : 'No image'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
