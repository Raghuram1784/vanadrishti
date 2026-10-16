import { useState } from "react";
import type { Alert, Event } from "@/types/api";
import {
  formatEventMetadata,
  eventToJson,
  downloadEventJson,
  downloadEventsCsv,
  copyEventJsonToClipboard,
} from "@/lib/metadataExport";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Copy,
  Check,
  FileCode,
  FileSpreadsheet,
  Download,
  Code,
  Table as TableIcon,
  ShieldAlert,
  Camera,
  Layers,
  MapPin,
  Clock,
  Sparkles,
  Info,
} from "lucide-react";

interface DetectionMetadataViewerProps {
  event: Event;
  alert?: Alert | null;
}

export function DetectionMetadataViewer({ event, alert }: DetectionMetadataViewerProps) {
  const [viewMode, setViewMode] = useState<"structured" | "raw">("structured");
  const [copied, setCopied] = useState(false);

  const metadata = formatEventMetadata(event, alert);
  const jsonString = eventToJson(event, alert);

  const handleCopy = async () => {
    const success = await copyEventJsonToClipboard(event, alert);
    if (success) {
      setCopied(true);
      toast.success("Detection metadata copied to clipboard as JSON");
      setTimeout(() => setCopied(false), 2000);
    } else {
      toast.error("Failed to copy metadata to clipboard");
    }
  };

  const handleDownloadJson = () => {
    downloadEventJson(event, alert);
    toast.success(`Downloaded ${event.event_id}-metadata.json`);
  };

  const handleDownloadCsv = () => {
    downloadEventsCsv([event], alert ? [alert] : [], `event-${event.event_id}-detections.csv`);
    toast.success(`Downloaded event-${event.event_id}-detections.csv`);
  };

  return (
    <div className="panel mt-4 border border-slate-800 bg-slate-950/70 rounded-xl overflow-hidden">
      {/* Header Toolbar */}
      <div className="p-3.5 bg-slate-900/80 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20">
            <FileCode size={16} />
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Detection Metadata & Export
            </h4>
            <span className="text-[10px] text-slate-400">
              Standardized inspection & integration schema (v1.0)
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="flex items-center bg-slate-950 p-0.5 rounded border border-slate-800 mr-1">
            <button
              type="button"
              onClick={() => setViewMode("structured")}
              className={`px-2 py-1 text-[11px] rounded font-medium flex items-center gap-1 transition-colors ${
                viewMode === "structured"
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <TableIcon size={12} />
              <span>Inspector</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("raw")}
              className={`px-2 py-1 text-[11px] rounded font-medium flex items-center gap-1 transition-colors ${
                viewMode === "raw"
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Code size={12} />
              <span>Raw JSON</span>
            </button>
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={handleCopy}
            className="text-xs h-7 px-2.5 border-slate-700 bg-slate-900 hover:bg-slate-800"
          >
            {copied ? <Check size={12} className="text-emerald-400 mr-1" /> : <Copy size={12} className="mr-1" />}
            <span>{copied ? "Copied" : "Copy JSON"}</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleDownloadJson}
            className="text-xs h-7 px-2.5 border-slate-700 bg-slate-900 hover:bg-slate-800 text-emerald-400 hover:text-emerald-300"
          >
            <Download size={12} className="mr-1" />
            <span>JSON</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleDownloadCsv}
            className="text-xs h-7 px-2.5 border-slate-700 bg-slate-900 hover:bg-slate-800 text-cyan-400 hover:text-cyan-300"
          >
            <FileSpreadsheet size={12} className="mr-1" />
            <span>CSV</span>
          </Button>
        </div>
      </div>

      {/* Main Content: Inspector or Raw JSON */}
      <div className="p-4">
        {viewMode === "structured" ? (
          <div className="space-y-4 text-xs">
            {/* Section A: Camera & Identity */}
            <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800/80 space-y-2">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 flex items-center gap-1">
                <Camera size={12} className="text-emerald-400" />
                <span>Node & Operational Policy</span>
              </span>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500 block text-[10px]">Camera ID:</span>
                  <strong className="text-slate-200 font-mono">{metadata.camera.id}</strong>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Geographic Zone:</span>
                  <span className="text-slate-300">{metadata.camera.geographic_zone}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Alert Policy:</span>
                  <span
                    className={`font-semibold font-mono ${
                      metadata.camera.operational_policy === "CRITICAL"
                        ? "text-red-400"
                        : metadata.camera.operational_policy === "RESTRICTED"
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }`}
                  >
                    {metadata.camera.operational_policy ? `${metadata.camera.operational_policy} ZONE` : "UNSET"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Source Medium:</span>
                  <span className="font-mono text-slate-300 uppercase">{metadata.camera.source}</span>
                </div>
              </div>
              <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>Hardware Node: {metadata.camera.hardware_node}</span>
                <span>
                  Coordinates: [{metadata.camera.coordinates.latitude.toFixed(3)}° N,{" "}
                  {metadata.camera.coordinates.longitude.toFixed(3)}° E] (Configured)
                </span>
              </div>
            </div>

            {/* Section B: Detections & Bounding Boxes */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 flex items-center gap-1">
                  <Layers size={12} className="text-cyan-400" />
                  <span>Detections ({metadata.detections.length})</span>
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  MegaDetector V6 · Normalized [x1, y1, x2, y2]
                </span>
              </div>

              {metadata.detections.length === 0 ? (
                <div className="p-3 bg-slate-900/40 rounded border border-slate-800 text-slate-500 text-center">
                  No objects detected in this event frame.
                </div>
              ) : (
                <div className="space-y-2">
                  {metadata.detections.map((det) => (
                    <div
                      key={det.index}
                      className="p-3 bg-slate-900/50 rounded-lg border border-slate-800 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                              det.type === "person"
                                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                : det.type === "animal"
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                            }`}
                          >
                            #{det.index + 1} {det.type}
                          </span>
                          <span className="text-slate-300 font-mono text-xs">
                            Score: {(det.detector_score * 100).toFixed(1)}% ({det.detector_score.toFixed(4)})
                          </span>
                        </div>

                        {det.uncertain && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Uncertain Detection: {det.uncertainty_reason || "Low Confidence / Backlit"}
                          </span>
                        )}
                      </div>

                      {/* Bounding Box Info */}
                      <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 bg-slate-950/80 px-2.5 py-1.5 rounded border border-slate-800/80">
                        <span className="text-slate-500">Bounding Box:</span>
                        {det.bbox_normalized ? (
                          <span>
                            [{det.bbox_normalized.map((n) => n.toFixed(3)).join(", ")}]
                          </span>
                        ) : (
                          <span className="text-slate-600">None</span>
                        )}
                      </div>

                      {/* Species identification if animal */}
                      {det.species && (
                        <div className="p-2 bg-slate-950/60 rounded border border-slate-800/60 text-[11px] space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-emerald-400 font-medium flex items-center gap-1">
                              <Sparkles size={11} />
                              <span>BioCLIP Species: <strong>{det.species.top1}</strong></span>
                            </span>
                            <span className="font-mono text-slate-400 text-[10px]">
                              Ranking Score: {det.species.ranking_score.toFixed(4)}
                            </span>
                          </div>
                          {det.species.top3 && det.species.top3.length > 1 && (
                            <p className="text-[10px] text-slate-500 font-mono">
                              Candidates: {det.species.top3.map((c) => `${c.label} (${c.ranking_score.toFixed(2)})`).join(" · ")}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Section C: Risk & Incident Reference */}
            <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-800/80 space-y-2">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 flex items-center gap-1">
                <ShieldAlert size={12} className="text-amber-400" />
                <span>Risk Intelligence & Incident State</span>
              </span>
              <div className="flex items-center justify-between text-xs">
                <div>
                  <span className="text-slate-500 text-[10px]">Assessed Level: </span>
                  <strong
                    className={
                      metadata.risk.level === "CRITICAL"
                        ? "text-red-400"
                        : metadata.risk.level === "HIGH"
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }
                  >
                    {metadata.risk.level} ({metadata.risk.score}/100)
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px]">Incident Status: </span>
                  <span className="font-mono text-slate-300 font-medium">
                    {metadata.incident.status}
                  </span>
                </div>
              </div>
              <ul className="text-[11px] text-slate-300 list-disc list-inside space-y-0.5">
                {metadata.risk.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              <div className="text-[10px] text-slate-400 border-t border-slate-800/60 pt-1.5 flex items-center justify-between font-mono">
                <span>Action: {metadata.risk.recommended_action}</span>
                <span>Event ID: {metadata.event_id}</span>
              </div>
            </div>
          </div>
        ) : (
          /* Raw JSON View */
          <div className="relative">
            <pre className="p-3 bg-slate-950 text-slate-200 font-mono text-[11px] rounded-lg border border-slate-800 max-h-96 overflow-y-auto leading-relaxed">
              {jsonString}
            </pre>
            <Button
              size="sm"
              variant="outline"
              onClick={handleCopy}
              className="absolute top-2 right-2 text-xs h-6 px-2 bg-slate-900/90 border-slate-700 text-slate-300 hover:text-white"
            >
              {copied ? <Check size={11} className="text-emerald-400 mr-1" /> : <Copy size={11} className="mr-1" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
