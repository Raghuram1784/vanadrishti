import { useState } from "react";
import { Search, FileSpreadsheet } from "lucide-react";
import { useCameras } from "@/hooks/useCameras";
import { useEvents } from "@/hooks/useEvents";
import { useAlerts } from "@/hooks/useAlerts";
import type { Event } from "@/types/api";
import { EventTable } from "@/components/events/EventTable";
import { ResultPanels } from "@/components/analysis/ResultPanels";
import { EventEvidence } from '@/components/analysis/EventEvidence';
import { DetectionMetadataViewer } from "@/components/events/DetectionMetadataViewer";
import { downloadEventsCsv } from "@/lib/metadataExport";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, ErrorBanner, PageTitle } from "@/components/ui/shared";
export default function Events() {
  const [camera, setCamera] = useState(""),
    [type, setType] = useState(""),
    [risk, setRisk] = useState(""),
    [search, setSearch] = useState(""),
    [limit, setLimit] = useState(25);
  const [selected, setSelected] = useState<Event>();
  const cameras = useCameras(),
    events = useEvents({ camera_id: camera, event_type: type, limit }),
    alerts = useAlerts(true);
  const filtered =
    events.data?.filter(
      (e) =>
        (!risk || e.risk.level === risk) &&
        `${e.event_id} ${e.camera.name} ${e.camera.id} ${e.detections.map((d) => `${d.type} ${d.species?.top1 || ""}`).join(" ")}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    ) || [];
  return (
    <>
      <PageTitle
        eyebrow="FOREST INTELLIGENCE / EVENTS"
        title="Every observation, in context."
      >
        Explore persisted image analyses and clearly labeled simulated
        scenarios.
      </PageTitle>
      <ErrorBanner
        text={events.error || cameras.error || alerts.error}
        retry={() => {
          void events.refresh();
          void cameras.refresh();
          void alerts.refresh();
        }}
      />
      <section className="panel">
        <div className="event-filters">
          <label className="search-field">
            <span>Search events</span>
            <div>
              <Search size={16} />
              <input
                placeholder="Camera, object, species or ID…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </label>
          <label>
            Camera
            <select value={camera} onChange={(e) => setCamera(e.target.value)}>
              <option value="">All cameras</option>
              {cameras.data?.cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Event type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">All objects</option>
              {["animal", "person", "vehicle"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Risk level
            <select value={risk} onChange={(e) => setRisk(e.target.value)}>
              <option value="">All levels</option>
              {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Limit
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              {[25, 50, 100].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="filter-caption flex items-center justify-between flex-wrap gap-2">
          <span>
            Showing {filtered.length} of {events.data?.length ?? 0} fetched events.
            Search and risk filters apply within the latest {limit} matching events.
          </span>
          {filtered.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                downloadEventsCsv(
                  filtered,
                  alerts.data || [],
                  `vanadrishti-filtered-events-${filtered.length}.csv`,
                );
                toast.success(`Exported ${filtered.length} filtered events to CSV`);
              }}
              className="text-xs h-7 px-2.5 border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200"
            >
              <FileSpreadsheet size={13} className="mr-1.5 text-cyan-400" />
              <span>Export Filtered ({filtered.length}) CSV</span>
            </Button>
          )}
        </div>
        {events.loading ? (
          <Empty title="Loading event history…" />
        ) : filtered.length ? (
          <EventTable
            events={filtered}
            alerts={alerts.data}
            onSelect={setSelected}
          />
        ) : (
          <Empty
            title={events.data?.length ? "No matching events" : "No events yet"}
          >
            Adjust the filters, analyze an image, or run a demo scenario.
          </Empty>
        )}
      </section>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(undefined);
        }}
      >
        <DialogContent drawer>
          <DialogTitle className="text-xl font-semibold">
            Event details
          </DialogTitle>
          <DialogDescription className="my-3 text-sm text-muted-foreground">
            {selected?.event_id}
          </DialogDescription>
          {selected && (
            <>
              <span className="source-tag">
                {selected.source === "demo"
                  ? "SIMULATED SCENARIO"
                  : "IMAGE ANALYSIS"}
              </span>
              <div className="drawer-content">
                <EventEvidence event={selected}/>
                <ResultPanels event={selected} />
                <DetectionMetadataViewer
                  event={selected}
                  alert={alerts.data?.find((a) => a.id === selected.event_id)}
                />
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
