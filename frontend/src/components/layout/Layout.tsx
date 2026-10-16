import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Leaf,
  LayoutDashboard,
  ScanLine,
  Trees,
} from "lucide-react";
import { getAlerts, getHealth } from "@/services/api";
import { usePolling } from "@/hooks/usePolling";
import { useLiveUpdates } from '@/hooks/useLiveUpdates';
import type { LiveMessage } from "@/types/api";

export function Layout() {
  const live = useLiveUpdates();
  const health = usePolling(getHealth, 10000);
  const online = !!health.data && !health.error;
  const [unreadAlerts, setUnreadAlerts] = useState<number>(0);

  useEffect(() => {
    getAlerts().then((alerts) => {
      setUnreadAlerts(alerts.filter((a) => a.status === "NEW" || a.status === "REVIEWING").length);
    }).catch(() => {});

    const handler = (event: globalThis.Event) => {
      const message = (event as CustomEvent<LiveMessage>).detail;
      if (message.type === "alert.created") {
        setUnreadAlerts((n) => n + 1);
      } else if (message.type === "alert.updated") {
        getAlerts().then((alerts) => {
          setUnreadAlerts(alerts.filter((a) => a.status === "NEW" || a.status === "REVIEWING").length);
        }).catch(() => {});
      }
    };
    window.addEventListener("vanadrishti:live", handler);
    return () => window.removeEventListener("vanadrishti:live", handler);
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-icon">
            <Trees size={25} />
          </span>
          <span>
            VanaDrishti<small>FOREST INTELLIGENCE</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {[
            [LayoutDashboard, "Overview", "/"],
            [ScanLine, "Monitor", "/monitor"],
            [Bell, "Alerts", "/alerts"],
            [Activity, "Events", "/events"],
          ].map(([Icon, label, path]) => {
            const I = Icon as typeof Leaf;
            return (
              <NavLink
                key={String(path)}
                to={String(path)}
                aria-label={String(label)}
                end={path === "/"}
              >
                <I size={18} />
                <span>{String(label)}</span>
                {path === "/alerts" && unreadAlerts > 0 && (
                  <span
                    title={`${unreadAlerts} alerts requiring ranger review`}
                    style={{
                      marginLeft: "auto",
                      marginRight: "6px",
                      padding: "1px 6px",
                      borderRadius: "9999px",
                      fontSize: "10px",
                      fontWeight: 700,
                      backgroundColor: "#ef4444",
                      color: "#ffffff",
                    }}
                  >
                    {unreadAlerts}
                  </span>
                )}
                <ArrowUpRight size={14} className="nav-arrow" />
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="conservation-mark">
            <Leaf size={24} />
            <p>
              Intelligent Eyes
              <br />
              for Safer Forests
            </p>
          </div>
          <span className="prototype-dot" /> Prototype System
          <small>Simulated Camera Locations</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <strong>VanaDrishti Ranger Intelligence</strong>
            <span>Prototype Dashboard</span>
          </div>
          <div className={`system-state ${online ? "online" : "offline"}`}>
            <i />
            {health.loading
              ? "CONNECTING"
              : online
                ? "SYSTEM ONLINE"
                : "BACKEND OFFLINE"}
          </div>
        </header>
        <main>
          <div className="model-strip">
            <span>Live Updates: {live ? 'Connected' : 'Reconnecting'}</span>
            <span>
              <i
                className={online && health.data?.detector_ready ? "ready" : ""}
              />
              Detector:{" "}
              {!online
                ? "Unavailable"
                : health.data?.detector_ready
                  ? "Ready"
                  : "Standby"}
            </span>
            <span>
              <i
                className={
                  online && health.data?.species_model_ready ? "ready" : ""
                }
              />
              Species AI:{" "}
              {!online
                ? "Unavailable"
                : health.data?.species_model_ready
                  ? "Ready"
                  : "Standby"}
            </span>
            <span className="strip-note">
              LOCAL PROTOTYPE <b>·</b> INDIA STANDARD TIME
            </span>
          </div>
          <div className="prototype-banner">Prototype Demonstration · Simulated Camera Locations</div>
          <Outlet />
        </main>
        <footer>
          VanaDrishti assesses situations, not identities. Rangers make the
          final decision.<span>PHASE 4C · REST + LIVE UPDATES</span>
        </footer>
      </div>
    </div>
  );
}
