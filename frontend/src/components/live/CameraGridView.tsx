import { useEffect, useState } from "react";
import { useCameras } from "@/hooks/useCameras";
import { getCameraSessions, getEvents, getCameraPolicy, setCameraPolicy } from "@/services/api";
import type { CameraPolicy, CameraSession, Event } from "@/types/api";
import { toast } from "sonner";
import { dateTime } from "@/lib/utils";
import {
  Camera,
  Smartphone,
  Radio,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Wifi,
  Eye,
  MapPin,
  Clock,
  Layers,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface CameraGridViewProps {
  onSelectCamera: (cameraId: string) => void;
  initialSessions?: CameraSession[];
  initialEvents?: Event[];
}

export function CameraGridView({ onSelectCamera, initialSessions, initialEvents }: CameraGridViewProps) {
  const cameraData = useCameras();
  const [sessions, setSessions] = useState<CameraSession[]>(initialSessions || []);
  const [recentEvents, setRecentEvents] = useState<Event[]>(initialEvents || []);
  const [policies, setPolicies] = useState<Record<string, CameraPolicy>>({
    "C-18": "CRITICAL",
    "C-21": "RESTRICTED",
  });

  useEffect(() => {
    const fetchStatus = () => {
      getCameraSessions().then(setSessions).catch(() => {});
      getEvents().then((evts) => setRecentEvents(evts.slice(0, 10))).catch(() => {});
    };
    fetchStatus();
    // Load persisted policies for physical cameras
    getCameraPolicy("C-18").then((res) => {
      if (res?.policy) setPolicies((p) => ({ ...p, "C-18": res.policy }));
    }).catch(() => {});
    getCameraPolicy("C-21").then((res) => {
      if (res?.policy) setPolicies((p) => ({ ...p, "C-21": res.policy }));
    }).catch(() => {});

    const timer = setInterval(fetchStatus, 4000);
    return () => clearInterval(timer);
  }, []);

  const handlePolicyChange = async (cameraId: string, newPolicy: CameraPolicy) => {
    try {
      await setCameraPolicy(cameraId, newPolicy);
      setPolicies((prev) => ({ ...prev, [cameraId]: newPolicy }));
      toast.success(`${cameraId} operational policy updated to ${newPolicy}`);
    } catch {
      toast.error(`Failed to update ${cameraId} policy`);
    }
  };

  const getSession = (id: string) => sessions.find((s) => s.camera_id === id);
  const getLatestEvent = (id: string) => recentEvents.find((e) => e.camera?.id === id);

  // Six-camera surveillance definitions: C-18 and C-21 are physical sources; CAM-01 to CAM-04 are simulated/inactive.
  const slots = [
    {
      id: "C-18",
      name: "Sector C-18 Trail Camera (Laptop Prototype)",
      zone: "CORE ZONE A",
      type: "real_webcam",
      role: "Fixed Trail Surveillance",
      location: "[20.250° N, 79.363° E]",
    },
    {
      id: "C-21",
      name: "Sector C-21 Mobile Patrol (Android Hotspot)",
      zone: "BUFFER ZONE WEST",
      type: "real_mobile",
      role: "Mobile Ranger Patrol",
      location: "[20.275° N, 79.315° E]",
    },
    {
      id: "CAM-01",
      name: "North Forest Trail Tower",
      zone: "CORE ZONE A",
      type: "simulated",
      role: "Wildlife Corridor Tower",
      location: "[20.248° N, 79.361° E]",
    },
    {
      id: "CAM-02",
      name: "Telia Stream Crossing",
      zone: "CORE ZONE A",
      type: "simulated",
      role: "Natural Waterhole Trap",
      location: "[20.251° N, 79.364° E]",
    },
    {
      id: "CAM-03",
      name: "Kolsa Fireline Post",
      zone: "RESTRICTED FIRELINE",
      type: "simulated",
      role: "Vehicular Perimeter Monitor",
      location: "[20.240° N, 79.375° E]",
    },
    {
      id: "CAM-04",
      name: "Moharli Buffer Track",
      zone: "BUFFER ZONE WEST",
      type: "simulated",
      role: "Eco-Tourism Boundary Node",
      location: "[20.278° N, 79.312° E]",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Overview Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-900/80 rounded-xl border border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
            <Radio size={20} className="animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              Surveillance Grid: 6 Operational Sectors
            </h3>
            <p className="text-xs text-slate-400">
              2 Physical Live Nodes (C-18 Laptop, C-21 Mobile) + 4 Synthetic Demo Corridors
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>2 Real Hardware Feeds</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 text-slate-400 rounded-full border border-slate-700">
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span>4 Simulated Slots</span>
          </div>
        </div>
      </div>

      {/* 6-Camera Grid (2x3) */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        {slots.map((slot) => {
          const session = getSession(slot.id);
          const isOnline = session?.status === "ONLINE";
          const lastEvent = getLatestEvent(slot.id);
          const isReal = slot.type.startsWith("real");

          return (
            <div
              key={slot.id}
              className={`panel flex flex-col justify-between rounded-xl border transition-all duration-200 overflow-hidden ${
                isReal
                  ? isOnline
                    ? "border-emerald-600/60 bg-gradient-to-b from-slate-900 via-slate-900 to-emerald-950/20 shadow-lg shadow-emerald-950/30"
                    : "border-slate-800 hover:border-slate-700"
                  : "border-slate-800/60 bg-slate-950/40 opacity-85"
              }`}
            >
              {/* Card Header */}
              <div className="p-4 border-b border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {slot.type === "real_webcam" ? (
                      <Camera size={16} className="text-emerald-400" />
                    ) : slot.type === "real_mobile" ? (
                      <Smartphone size={16} className="text-cyan-400" />
                    ) : (
                      <Radio size={16} className="text-slate-500" />
                    )}
                    <strong className="font-mono text-sm text-slate-100">{slot.id}</strong>
                  </div>

                  {/* Status Badge */}
                  {isReal ? (
                    <span
                      className={`text-[11px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1.5 ${
                        isOnline
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                          : "bg-slate-800 text-slate-400 border border-slate-700"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isOnline ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
                        }`}
                      />
                      <span>{isOnline ? "LIVE STREAM ACTIVE" : "OFFLINE / STANDBY"}</span>
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-500 border border-slate-800">
                      SIMULATED NODE · INACTIVE
                    </span>
                  )}
                </div>

                <div className="text-xs text-slate-300 font-medium truncate">
                  {slot.name}
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span className="flex items-center gap-1">
                    <Layers size={11} className="text-slate-500" />
                    <span>{slot.zone}</span>
                  </span>
                  <span className="flex items-center gap-1 font-mono text-[10px]">
                    <MapPin size={10} className="text-slate-500" />
                    <span>{slot.location}</span>
                  </span>
                </div>

                {/* Operational Zone Policy Dropdown for Real Cameras */}
                {isReal ? (
                  <div className="flex items-center justify-between pt-1.5 border-t border-slate-800/60 text-xs">
                    <span className="text-[11px] text-slate-300 flex items-center gap-1">
                      <ShieldAlert
                        size={12}
                        className={
                          policies[slot.id] === "CRITICAL"
                            ? "text-red-400"
                            : policies[slot.id] === "RESTRICTED"
                            ? "text-amber-400"
                            : "text-emerald-400"
                        }
                      />
                      <span>Alert Policy:</span>
                    </span>
                    <select
                      aria-label={`${slot.id} operational policy`}
                      value={policies[slot.id] || (slot.id === "C-18" ? "CRITICAL" : "RESTRICTED")}
                      onChange={(e) => handlePolicyChange(slot.id, e.target.value as CameraPolicy)}
                      className="bg-slate-900 border border-slate-700 hover:border-slate-600 text-[11px] font-mono text-slate-200 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                    >
                      <option value="SAFE">SAFE / PUBLIC</option>
                      <option value="RESTRICTED">RESTRICTED</option>
                      <option value="CRITICAL">CRITICAL / SENSITIVE</option>
                    </select>
                  </div>
                ) : (
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800/40 text-[11px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <Radio size={11} className="text-slate-600" />
                      <span>Mode:</span>
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">SYNTHETIC BENCHMARK</span>
                  </div>
                )}
              </div>

              {/* Viewport Frame */}
              <div className="relative aspect-video bg-black flex flex-col items-center justify-center overflow-hidden border-y border-slate-800/80">
                {isReal ? (
                  isOnline && lastEvent?.evidence_image_url ? (
                    <img
                      src={lastEvent.evidence_image_url}
                      alt={slot.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-center p-4 space-y-2">
                      {slot.type === "real_webcam" ? (
                        <Camera size={32} className="mx-auto text-slate-600" />
                      ) : (
                        <Smartphone size={32} className="mx-auto text-slate-600" />
                      )}
                      <p className="text-xs text-slate-400 font-mono">
                        {isOnline ? "Sampling Active · Awaiting Detections" : "Source Standby · Offline"}
                      </p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onSelectCamera(slot.id)}
                        className="text-xs border-slate-700"
                      >
                        Open {slot.id} Feed
                      </Button>
                    </div>
                  )
                ) : (
                  // Strictly synthetic node placeholder: never invent live footage!
                  <div className="text-center p-4 space-y-2 text-slate-600">
                    <Radio size={28} className="mx-auto opacity-40" />
                    <p className="text-[11px] font-mono text-slate-500">
                      SYNTHETIC SECTOR NODE
                    </p>
                    <p className="text-[10px] text-slate-600 max-w-[200px] mx-auto">
                      No physical camera hardware connected to this slot.
                    </p>
                  </div>
                )}

                {/* Overlay Badge for Real Node */}
                {isReal && (
                  <div className="absolute top-2 left-2 bg-slate-950/80 backdrop-blur px-2 py-0.5 rounded text-[10px] font-mono border border-slate-700 flex items-center gap-1">
                    {isOnline ? (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-emerald-400">HARDWARE ONLINE</span>
                      </>
                    ) : (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                        <span className="text-slate-400">HARDWARE OFFLINE</span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Card Footer: Telemetry & Actions distinguishing Live vs Historical */}
              <div className="p-3.5 bg-slate-900/40 space-y-2">
                {isReal ? (
                  isOnline ? (
                    <div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-emerald-400 text-[11px] font-semibold flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                          Live Stream Status:
                        </span>
                        {lastEvent?.risk ? (
                          <span
                            className={`font-semibold text-xs ${
                              lastEvent.risk.level === "CRITICAL"
                                ? "text-red-400"
                                : lastEvent.risk.level === "HIGH"
                                ? "text-amber-400"
                                : "text-emerald-400"
                            }`}
                          >
                            Current Risk: {lastEvent.risk.level} ({lastEvent.risk.score})
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[11px] font-mono">Stream Active · Normal</span>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                        Sampling active · Continuous ingestion
                      </p>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400 text-[11px] flex items-center gap-1">
                          <History size={11} className="text-slate-500" />
                          Last Recorded Event:
                        </span>
                        {lastEvent?.risk ? (
                          <span
                            className={`font-semibold text-xs ${
                              lastEvent.risk.level === "CRITICAL"
                                ? "text-red-400"
                                : lastEvent.risk.level === "HIGH"
                                ? "text-amber-400"
                                : "text-emerald-400"
                            }`}
                          >
                            {lastEvent.risk.level} ({lastEvent.risk.score})
                          </span>
                        ) : (
                          <span className="text-slate-500 text-[11px] font-mono">No historical records</span>
                        )}
                      </div>
                      <p className="text-[10px] text-amber-500/80 font-mono mt-0.5">
                        {lastEvent ? `Event at ${dateTime(lastEvent.timestamp)} · Camera offline` : "Camera offline / standby"}
                      </p>
                    </div>
                  )
                ) : (
                  <div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 text-[11px]">Sector Status:</span>
                      <span className="text-slate-500 text-[11px] font-mono">Synthetic Reference</span>
                    </div>
                    <p className="text-[10px] text-slate-600 font-mono mt-0.5">
                      Inactive corridor · Static baseline
                    </p>
                  </div>
                )}

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60">
                  <span className="text-[10px] text-slate-500 font-mono">
                    {slot.role}
                  </span>
                  {isReal && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onSelectCamera(slot.id)}
                      className="text-xs text-emerald-400 hover:text-emerald-300 p-0 h-auto font-medium"
                    >
                      <span>Controls & Logs</span>
                      <ExternalLink size={12} className="ml-1" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
