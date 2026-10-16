import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/ui/shared";
import { ResultPanels } from "@/components/analysis/ResultPanels";
import { getEvent, updateAlert } from "@/services/api";
import { EventEvidence } from '@/components/analysis/EventEvidence';
import { refreshData } from "@/hooks/usePolling";
import type { Alert, AlertStatus, Event } from "@/types/api";
import { dateTime, message, statusLabel } from "@/lib/utils";
const transitions: Record<AlertStatus, AlertStatus[]> = {
  NEW: ["REVIEWING", "FALSE_ALARM", "ESCALATED", "RESOLVED"],
  REVIEWING: ["PATROL_ASSIGNED", "FALSE_ALARM", "ESCALATED", "RESOLVED"],
  PATROL_ASSIGNED: ["ESCALATED", "FALSE_ALARM", "RESOLVED"],
  ESCALATED: ["REVIEWING", "PATROL_ASSIGNED", "FALSE_ALARM", "RESOLVED"],
  FALSE_ALARM: [],
  RESOLVED: [],
};
export function AlertDrawer({
  alert,
  onClose,
  onUpdate,
}: {
  alert?: Alert;
  onClose: () => void;
  onUpdate: (alert: Alert) => void;
}) {
  const [event, setEvent] = useState<Event>();
  const [loading, setLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [pending, setPending] = useState<AlertStatus>();
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setEvent(undefined);
    setDetailError("");
    setPending(undefined);
    if (!alert) return;
    let active = true;
    setLoading(true);
    getEvent(alert.id)
      .then((result) => {
        if (active) setEvent(result);
      })
      .catch((e) => {
        if (active) setDetailError(message(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [alert?.id, alert?.camera_id]);
  async function act(action: AlertStatus) {
    if (!alert) return;
    setBusy(true);
    try {
      const response = await updateAlert(alert.id, action);
      onUpdate(response);
      refreshData();
      setPending(undefined);
      toast.success(`Alert updated to ${statusLabel(response.status)}.`);
    } catch (e) {
      toast.error(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Dialog
        open={!!alert}
        onOpenChange={(open) => {
          if (!open && !busy) onClose();
        }}
      >
        <DialogContent drawer>
          <DialogTitle className="text-xl font-semibold">
            Situation review
          </DialogTitle>
          <DialogDescription className="mt-2 text-sm text-muted-foreground">
            Review the evidence and context before taking action.
          </DialogDescription>
          {alert && (
            <div className="drawer-content">
              <div className="drawer-risk">
                <RiskBadge level={alert.risk_level} />
                <strong>
                  {alert.risk_score}
                  <small>/100</small>
                </strong>
                <span className="subtle-badge">
                  {statusLabel(alert.status)}
                </span>
              </div>
              <dl>
                <div>
                  <dt>Event ID</dt>
                  <dd className="mono-id">{alert.id}</dd>
                </div>
                <div>
                  <dt>Camera</dt>
                  <dd>
                    {alert.camera_id} · {alert.camera_id.startsWith("C-") ? "Real hardware node" : "Simulated location"}
                  </dd>
                </div>
                {alert.policy && (
                  <div>
                    <dt>Alert Policy</dt>
                    <dd className="font-mono text-amber-300 font-semibold">{alert.policy} ZONE</dd>
                  </div>
                )}
                <div>
                  <dt>Timestamp · IST</dt>
                  <dd>{dateTime(alert.timestamp)}</dd>
                </div>
              </dl>
              {loading ? (
                <p>Loading event context…</p>
              ) : event ? (
                <>
                  <EventEvidence event={event}/>
                  <div className="observation-summary">
                    <h3>Detected objects</h3>
                    {event.detections.map((d, i) => (
                      <p key={i}>
                        <span className="capitalize">{d.type}</span>
                        {d.species &&
                          ` · ${d.species.top1} · ranking ${d.species.ranking_score}`}
                      </p>
                    ))}
                    <span className="source-tag">
                      {event.source === "demo"
                        ? "SIMULATED SCENARIO"
                        : "IMAGE ANALYSIS"}
                    </span>
                  </div>
                  <ResultPanels event={event} />
                </>
              ) : (
                <>
                  <p className="muted">
                    {detailError ||
                      "Full event details are unavailable. Alert details remain available."}
                  </p>
                  <ul className="reason-list">
                    {alert.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                  <p className="muted">
                    Recommended action unavailable without the matching event.
                  </p>
                </>
              )}
              <div className="alert-actions">
                <h3>Ranger Incident Response</h3>
                <p>
                  Update workflow status. Every action is logged with timestamp for accountability.
                </p>
                <div className="flex flex-wrap gap-2">
                  {transitions[alert.status].length ? (
                    transitions[alert.status].map((action) => {
                      const label =
                        action === "REVIEWING"
                          ? "Acknowledge"
                          : action === "PATROL_ASSIGNED"
                          ? "Investigate / Patrol"
                          : action === "RESOLVED"
                          ? "Resolve"
                          : action === "FALSE_ALARM"
                          ? "False Alarm"
                          : action === "ESCALATED"
                          ? "Escalate"
                          : statusLabel(action);

                      return (
                        <Button
                          key={action}
                          variant={action === "REVIEWING" ? "default" : action === "RESOLVED" ? "secondary" : "outline"}
                          disabled={busy}
                          onClick={() =>
                            ["FALSE_ALARM", "RESOLVED"].includes(action)
                              ? setPending(action)
                              : void act(action)
                          }
                        >
                          {label}
                        </Button>
                      );
                    })
                  ) : (
                    <p className="text-sm text-slate-400">This incident is resolved / closed.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!pending}
        onOpenChange={(open) => {
          if (!open && !busy) setPending(undefined);
        }}
      >
        <DialogContent>
          <DialogTitle className="text-lg font-semibold">
            Mark as {pending && statusLabel(pending).toLowerCase()}?
          </DialogTitle>
          <DialogDescription className="my-4 text-sm text-muted-foreground">
            This closes the alert in this prototype. The backend does not
            support reopening it.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setPending(undefined)}
            >
              Cancel
            </Button>
            <Button
              disabled={busy}
              onClick={() => pending && void act(pending)}
            >
              {busy ? "Saving…" : "Confirm status change"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
