import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Camera,
  Activity,
  Bell,
  ShieldAlert,
  ScanLine,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useCameras } from "@/hooks/useCameras";
import { useEvents } from "@/hooks/useEvents";
import { useAlerts } from "@/hooks/useAlerts";
import { Button } from "@/components/ui/button";
import { Empty, ErrorBanner, PageTitle } from "@/components/ui/shared";
import { CameraMap } from "@/components/map/CameraMap";
import { EventTable } from "@/components/events/EventTable";
export default function Dashboard() {
  const cameras = useCameras(),
    events = useEvents({ limit: 100 }),
    alerts = useAlerts(true);
  const activeAlerts = alerts.data?.filter(
    (a) => !["RESOLVED", "FALSE_ALARM"].includes(a.status),
  );
  const distribution = ["LOW", "MEDIUM", "HIGH", "CRITICAL"].map(
    (level, i) => ({
      level,
      count: events.data?.filter((e) => e.risk.level === level).length || 0,
      color: ["#73ad90", "#c5a55d", "#d78652", "#c65d61"][i],
    }),
  );
  return (
    <>
      <PageTitle
        eyebrow="FOREST INTELLIGENCE / OVERVIEW"
        title="A clearer view of the forest."
        action={
          <Button asChild>
            <Link to="/monitor">
              <ScanLine />
              Analyze an image
              <ArrowUpRight />
            </Link>
          </Button>
        }
      >
        Camera context, wildlife activity, and situations that need a closer
        look.
      </PageTitle>
      <ErrorBanner
        text={cameras.error || events.error || alerts.error}
        retry={() => {
          void cameras.refresh();
          void events.refresh();
          void alerts.refresh();
        }}
      />
      <div className="stats-grid">
        {[
          {
            title: "Active Cameras",
            value: cameras.data?.cameras.filter((c) => c.active).length,
            note: "Simulated camera registry",
            icon: Camera,
            color: "green",
          },
          {
            title: "Recent Events",
            value: events.data?.length,
            note: "Latest 100 events · all sources",
            icon: Activity,
            color: "gold",
          },
          {
            title: "High / Critical Alerts",
            value: activeAlerts?.length,
            note: "Open alerts requiring review",
            icon: Bell,
            color: "orange",
          },
          {
            title: "Critical Alerts",
            value: activeAlerts?.filter((a) => a.risk_level === "CRITICAL")
              .length,
            note: "Open critical situations",
            icon: ShieldAlert,
            color: "red",
          },
        ].map((stat) => (
          <section className={`stat-card stat-${stat.color}`} key={stat.title}>
            <div>
              <span>{stat.title}</span>
              <stat.icon size={18} />
            </div>
            <strong>{stat.value ?? "—"}</strong>
            <small>{stat.note}</small>
          </section>
        ))}
      </div>
      <div className="overview-grid">
        <CameraMap cameras={cameras.data?.cameras || []} />
        <section className="panel distribution">
          <div className="panel-heading">
            <div>
              <h2>Risk distribution</h2>
              <p>Latest {events.data?.length ?? "—"} events</p>
            </div>
            <Activity size={17} />
          </div>
          {events.data?.length ? (
            <>
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={distribution}
                    margin={{ top: 15, right: 10, left: -25, bottom: 0 }}
                  >
                    <XAxis
                      dataKey="level"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: "#a2afa6", fontSize: 10 }}
                    />
                    <YAxis
                      allowDecimals={false}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: "#75857d", fontSize: 11 }}
                    />
                    <Tooltip
                      cursor={{ fill: "#24352c" }}
                      contentStyle={{
                        background: "#17251d",
                        border: "1px solid #36463b",
                        borderRadius: 8,
                        color: "#ecefe8",
                      }}
                    />
                    <Bar
                      isAnimationActive={false}
                      dataKey="count"
                      name="Events"
                      radius={[5, 5, 0, 0]}
                      maxBarSize={42}
                    >
                      {distribution.map((d) => (
                        <Cell key={d.level} fill={d.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="distribution-total">
                <span>EVENTS IN VIEW</span>
                <strong>{events.data.length}</strong>
                <small>Includes labeled demo scenarios</small>
              </div>
            </>
          ) : (
            <Empty
              title={events.loading ? "Loading events…" : "No events to chart"}
            >
              Your first analysis will appear here.
            </Empty>
          )}
        </section>
      </div>
      <section className="panel activity-panel">
        <div className="panel-heading">
          <div>
            <h2>Recent activity</h2>
            <p>Latest observations from the API · refreshed every 15 seconds</p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/events">
              View all events
              <ArrowUpRight />
            </Link>
          </Button>
        </div>
        {events.loading ? (
          <Empty title="Loading activity…" />
        ) : (
          <EventTable
            events={events.data?.slice(0, 5) || []}
            alerts={alerts.data}
          />
        )}
      </section>
    </>
  );
}
