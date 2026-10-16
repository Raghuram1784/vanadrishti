import type { Alert, Event } from "@/types/api";
import { dateTime, statusLabel } from "@/lib/utils";
import { Empty, RiskBadge } from "@/components/ui/shared";
import { Button } from "@/components/ui/button";
import { FileCode, ArrowUpRight } from "lucide-react";

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
            {onSelect && <th>ACTIONS</th>}
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const alert = alerts.find((a) => a.id === event.event_id);
            return (
              <tr
                key={event.event_id}
                onClick={() => onSelect?.(event)}
                className={onSelect ? "cursor-pointer hover:bg-slate-800/50 transition-colors" : ""}
              >
                <td>
                  {onSelect ? (
                    <button
                      type="button"
                      className="table-link font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(event);
                      }}
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
                {onSelect && (
                  <td>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(event);
                      }}
                      className="text-xs h-7 px-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/30 flex items-center gap-1 font-mono"
                    >
                      <FileCode size={12} />
                      <span>Metadata</span>
                      <ArrowUpRight size={11} />
                    </Button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
