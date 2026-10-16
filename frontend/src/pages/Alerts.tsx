import { useEffect, useState } from "react";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { useAlerts } from "@/hooks/useAlerts";
import type { Alert, LiveMessage } from "@/types/api";
import { AlertDrawer } from "@/components/alerts/AlertDrawer";
import { Button } from "@/components/ui/button";
import {
  Empty,
  ErrorBanner,
  PageTitle,
  RiskBadge,
} from "@/components/ui/shared";
import { dateTime, statusLabel } from "@/lib/utils";
export default function Alerts() {
  const [closed, setClosed] = useState(false);
  const [selected, setSelected] = useState<Alert>();
  const alerts = useAlerts(closed);
  useEffect(() => {
    const handler = (event: globalThis.Event) => {
      const message = (event as CustomEvent<LiveMessage>).detail;
      if (message.type === 'alert.updated') setSelected(current => current?.id === message.data.id ? message.data : current);
    };
    window.addEventListener('vanadrishti:live', handler);
    return () => window.removeEventListener('vanadrishti:live', handler);
  }, []);
  useEffect(() => {
    if (!selected) return;
    const latest = alerts.data?.find(a => a.id === selected.id);
    if (latest && latest.status !== selected.status) setSelected(latest);
  }, [alerts.data, selected]);
  return (
    <>
      <PageTitle
        eyebrow="FOREST INTELLIGENCE / ALERTS"
        title="Attention where it matters."
      >
        High and critical situations for human review. Every action stays with
        the ranger.
      </PageTitle>
      <ErrorBanner text={alerts.error} retry={alerts.refresh} />
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              <ShieldCheck size={17} /> Review queue{" "}
              <span className="count-pill">{alerts.data?.length ?? "—"}</span>
            </h2>
            <p>HIGH / CRITICAL · most recent first</p>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={closed}
              onChange={(e) => setClosed(e.target.checked)}
            />
            Include closed alerts
          </label>
        </div>
        {alerts.loading ? (
          <Empty title="Loading alerts…" />
        ) : !alerts.data?.length ? (
          <Empty title="No alerts requiring review">
            High and critical events will appear here. You can run a simulated
            scenario in Monitor.
          </Empty>
        ) : (
          <div className="alert-list">
            {alerts.data.map((alert) => (
              <article className="alert-row" key={alert.id}>
                <div
                  className={`alert-severity severity-${alert.risk_level.toLowerCase()}`}
                >
                  <strong>{alert.risk_score}</strong>
                  <small>RISK SCORE</small>
                </div>
                <div className="alert-main">
                  <div>
                    <RiskBadge level={alert.risk_level} />
                    <span className="subtle-badge">
                      {statusLabel(alert.status)}
                    </span>
                  </div>
                  <h3>{alert.camera_id} · Ranger review required</h3>
                  <p>{alert.reasons.slice(0, 2).join(" · ")}</p>
                  <small>
                    {dateTime(alert.timestamp)} IST · Simulated camera location
                  </small>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelected(alert)}
                >
                  Review alert
                  <ArrowUpRight />
                </Button>
              </article>
            ))}
          </div>
        )}
      </section>
      <AlertDrawer
        alert={selected}
        onClose={() => setSelected(undefined)}
        onUpdate={(a) => {
          setSelected(a);
          void alerts.refresh();
        }}
      />
    </>
  );
}
