import { useState, useEffect } from "react";
import { useLiveCamera } from "./useLaptopCamera";
import { Button } from "@/components/ui/button";
import { UncertaintyNotice, detectionLabel } from "@/components/analysis/UncertaintyNotice";
import { DetectionImage } from "@/components/analysis/DetectionImage";
import {
  Camera,
  Play,
  Square,
  Pause,
  RefreshCw,
  Smartphone,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Wifi,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { BASE, getCameraPolicy, setCameraPolicy } from "@/services/api";
import type { CameraPolicy } from "@/types/api";
import { toast } from "sonner";

const DEMO_TOKEN = "RANGER-DEMO-2026";

export function MobileCameraPanel() {
  const cam = useLiveCamera("C-21", "Android Mobile Patrol", "mobile_android", "environment");
  const [token, setToken] = useState(DEMO_TOKEN);
  const [showGuide, setShowGuide] = useState(false);
  const [showDiag, setShowDiag] = useState(false);
  const [localIp, setLocalIp] = useState("");
  const [policy, setPolicy] = useState<CameraPolicy>("RESTRICTED");

  useEffect(() => {
    if (typeof window !== "undefined" && window.location) {
      setLocalIp(window.location.hostname);
    }
  }, []);

  useEffect(() => {
    getCameraPolicy("C-21")
      .then((res) => {
        if (res?.policy) setPolicy(res.policy);
      })
      .catch(() => {});
  }, []);

  const handlePolicyChange = async (newPolicy: CameraPolicy) => {
    try {
      await setCameraPolicy("C-21", newPolicy);
      setPolicy(newPolicy);
      toast.success(`C-21 operational policy updated to ${newPolicy}`);
    } catch {
      toast.error("Failed to update C-21 policy");
    }
  };

  const authenticated = token.trim() === DEMO_TOKEN;

  return (
    <div className="mobile-camera-workspace space-y-6">
      {/* Header Banner */}
      <div className="panel bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-950 border-emerald-800/40 p-5 rounded-xl border">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
              <Smartphone size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  REAL PHYSICAL SOURCE · NODE C-21
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-mono ${
                    cam.sessionStatus === "ONLINE"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                  }`}
                >
                  {cam.sessionStatus}
                </span>
              </div>
              <h2 className="text-lg font-semibold text-slate-100 mt-1">
                Android Mobile Patrol Camera Ingestion
              </h2>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <span className="text-xs text-slate-400">
                  Geographic Zone: <strong className="text-slate-200">BUFFER ZONE WEST</strong> · Demonstration Node
                </span>
                <span className="text-slate-600">|</span>
                <label className="flex items-center gap-1.5 text-xs text-slate-300">
                  <ShieldAlert
                    size={13}
                    className={
                      policy === "CRITICAL"
                        ? "text-red-400"
                        : policy === "RESTRICTED"
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }
                  />
                  <span className="font-medium text-slate-300">Alert Policy:</span>
                  <select
                    aria-label="C-21 operational policy"
                    value={policy}
                    onChange={(e) => handlePolicyChange(e.target.value as CameraPolicy)}
                    className="bg-slate-900 border border-slate-700 hover:border-slate-600 text-xs font-mono text-slate-200 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    <option value="SAFE">SAFE / PUBLIC</option>
                    <option value="RESTRICTED">RESTRICTED</option>
                    <option value="CRITICAL">CRITICAL / SENSITIVE</option>
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowGuide(!showGuide)}
              className="text-xs flex items-center gap-1.5"
            >
              <Wifi size={14} />
              <span>Hotspot Connect Guide</span>
              {showGuide ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </Button>
          </div>
        </div>

        {/* Demo Token Authentication */}
        <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 text-slate-300">
            <ShieldCheck size={14} className="text-emerald-400" />
            <span>Patrol Auth Token:</span>
          </div>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 px-2.5 py-1 rounded font-mono text-xs w-48 focus:border-emerald-500 focus:outline-none"
            placeholder="Enter patrol auth token"
          />
          {authenticated ? (
            <span className="text-emerald-400 flex items-center gap-1 font-mono">
              ✓ Verified (Demo Mode)
            </span>
          ) : (
            <span className="text-red-400 flex items-center gap-1 font-mono">
              ✗ Invalid Token (Use: {DEMO_TOKEN})
            </span>
          )}
        </div>

        {/* Hotspot & ADB Connect Instructions */}
        {showGuide && (
          <div className="mt-4 p-4 bg-slate-900/90 rounded-lg border border-slate-700/60 text-xs space-y-3 text-slate-300">
            <div className="font-semibold text-slate-100 flex items-center gap-1.5">
              <Info size={14} className="text-blue-400" />
              <span>How to connect your Android Phone to Node C-21:</span>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-slate-950 p-3 rounded border border-slate-800 space-y-1.5">
                <strong className="text-emerald-400">Option 1: Phone Hotspot / Wi-Fi (Wireless)</strong>
                <ol className="list-decimal list-inside space-y-1 text-slate-400">
                  <li>Connect laptop to phone hotspot (or same Wi-Fi).</li>
                  <li>
                    Open Chrome on phone and navigate to:
                    <div className="bg-slate-900 text-emerald-300 p-1.5 mt-1 rounded font-mono select-all">
                      http://{localIp || "192.168.x.x"}:5173/c21
                    </div>
                  </li>
                  <li className="text-amber-300">
                    If Chrome blocks camera on HTTP: open <code className="bg-slate-800 px-1">chrome://flags/#unsafely-treat-insecure-origin-as-secure</code>, add <code className="bg-slate-800 px-1">http://{localIp || "192.168.x.x"}:5173</code>, enable and relaunch.
                  </li>
                </ol>
              </div>

              <div className="bg-slate-950 p-3 rounded border border-slate-800 space-y-1.5">
                <strong className="text-cyan-400">Option 2: USB Cable via ADB Reverse (Instant HTTPS/Secure Context)</strong>
                <ol className="list-decimal list-inside space-y-1 text-slate-400">
                  <li>Connect phone to laptop with USB cable (USB Debugging ON).</li>
                  <li>Run in PowerShell on laptop:
                    <div className="bg-slate-900 text-cyan-300 p-1.5 mt-1 rounded font-mono select-all">
                      adb reverse tcp:5173 tcp:5173 ; adb reverse tcp:8000 tcp:8000
                    </div>
                  </li>
                  <li>
                    Open Chrome on phone to <code className="bg-slate-800 px-1 text-emerald-300">http://localhost:5173/c21</code> (Chrome automatically treats localhost as a Secure Context with zero SSL warnings!).
                  </li>
                </ol>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Streaming & Preview Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Left Column: Camera Preview & Controls */}
        <section className="panel space-y-4">
          <div className="panel-heading flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Camera size={18} className="text-emerald-400" />
              <span>C-21 Camera Viewfinder</span>
            </h2>
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Cadence:</label>
              <select
                value={cam.intervalSec}
                onChange={(e) => cam.setIntervalSec(Number(e.target.value))}
                className="bg-slate-900 border border-slate-700 text-xs rounded px-2 py-1 text-slate-200"
              >
                <option value={2}>2s (Fast)</option>
                <option value={3}>3s (Standard)</option>
                <option value={5}>5s (Conserve)</option>
              </select>
            </div>
          </div>

          <div className="relative aspect-video bg-black rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center">
            <video
              ref={cam.videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${cam.running ? "block" : "hidden"}`}
            />

            {!cam.running && (
              <div className="text-center p-6 space-y-3">
                <Smartphone size={40} className="mx-auto text-slate-600" />
                <p className="text-sm text-slate-400">
                  Mobile patrol camera stream is stopped.
                </p>
                <Button
                  onClick={cam.startCamera}
                  disabled={cam.starting || !authenticated}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white"
                >
                  <Play size={16} className="mr-1.5" />
                  {cam.starting ? "Opening Camera…" : "Start C-21 Stream"}
                </Button>
              </div>
            )}

            {cam.running && (
              <div className="absolute top-3 left-3 bg-slate-950/80 backdrop-blur px-2.5 py-1 rounded text-xs font-mono text-emerald-400 flex items-center gap-1.5 border border-slate-700">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>C-21 STREAMING · {cam.diagnostics.resolution}</span>
              </div>
            )}

            {cam.inFlight && (
              <div className="absolute bottom-3 left-3 bg-slate-950/90 backdrop-blur px-2 py-0.5 rounded text-[11px] font-mono text-cyan-300 border border-cyan-800/60 flex items-center gap-1.5">
                <RefreshCw size={11} className="animate-spin" />
                <span>{cam.diagnostics.sampleStage || "Sampling"}</span>
              </div>
            )}
          </div>

          {/* Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-2">
              {cam.running ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={cam.togglePause}
                    className="text-xs"
                  >
                    <Pause size={14} className="mr-1" />
                    {cam.paused ? "Resume Sampling" : "Pause Sampling"}
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={cam.stopCamera}
                    className="text-xs"
                  >
                    <Square size={14} className="mr-1" />
                    Stop Stream
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  onClick={cam.startCamera}
                  disabled={cam.starting || !authenticated}
                  className="bg-emerald-600 hover:bg-emerald-500 text-xs"
                >
                  <Play size={14} className="mr-1" />
                  {cam.starting ? "Connecting…" : "Start Camera"}
                </Button>
              )}
            </div>

            {cam.devices.length > 1 && (
              <select
                value={cam.selectedDevice}
                onChange={(e) => cam.setSelectedDevice(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-xs rounded px-2 py-1 text-slate-300 max-w-[200px] truncate"
              >
                {cam.devices.map((d, i) => (
                  <option key={d.deviceId || i} value={d.deviceId}>
                    {d.label || `Camera ${i + 1}`}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Error Banner */}
          {cam.error && (
            <div className="p-3 bg-red-950/40 border border-red-800/60 rounded text-xs text-red-300 flex items-start gap-2">
              <AlertTriangle size={15} className="shrink-0 mt-0.5 text-red-400" />
              <span>{cam.error}</span>
            </div>
          )}

          {/* Telemetry Stats */}
          <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800 text-center text-xs">
            <div className="p-2 bg-slate-900/60 rounded border border-slate-800/80">
              <span className="text-slate-500 block text-[10px] uppercase">Captured</span>
              <strong className="text-slate-200 text-sm font-mono">{cam.capturedCount}</strong>
            </div>
            <div className="p-2 bg-slate-900/60 rounded border border-slate-800/80">
              <span className="text-slate-500 block text-[10px] uppercase">Submitted</span>
              <strong className="text-slate-200 text-sm font-mono">{cam.submittedCount}</strong>
            </div>
            <div className="p-2 bg-slate-900/60 rounded border border-slate-800/80">
              <span className="text-slate-500 block text-[10px] uppercase">Latency</span>
              <strong className="text-slate-200 text-sm font-mono">
                {cam.lastLatencyMs ? `${cam.lastLatencyMs}ms` : "—"}
              </strong>
            </div>
            <div className="p-2 bg-slate-900/60 rounded border border-slate-800/80">
              <span className="text-slate-500 block text-[10px] uppercase">Status</span>
              <strong className={`text-sm font-mono ${cam.sessionStatus === 'ONLINE' ? 'text-emerald-400' : 'text-slate-400'}`}>
                {cam.sessionStatus}
              </strong>
            </div>
          </div>
        </section>

        {/* Right Column: Latest Analysis & Inference Results */}
        <section className="panel space-y-4">
          <div className="panel-heading flex items-center justify-between">
            <h2 className="text-base font-semibold flex items-center gap-2">
              <ShieldCheck size={18} className="text-cyan-400" />
              <span>Latest Sampled Analysis</span>
            </h2>
            {cam.latestResult && (
              <span className="text-xs px-2 py-0.5 rounded font-mono bg-cyan-950 text-cyan-300 border border-cyan-800">
                {cam.latestResult.event_state}
              </span>
            )}
          </div>

          {cam.analyzedFrameUrl ? (
            <div className="space-y-4">
              <div className="analyzed-frame-wrap mobile-analyzed-wrap">
                <DetectionImage
                  url={cam.analyzedFrameUrl}
                  detections={cam.latestResult?.detections || []}
                />
              </div>

              {cam.latestResult?.detections && cam.latestResult.detections.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Detected Objects ({cam.latestResult.detections.length})
                  </div>
                  <div className="space-y-2">
                    {cam.latestResult.detections.map((det, i) => (
                      <div
                        key={i}
                        className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-2 h-2 rounded-full ${
                                det.type === "person"
                                  ? "bg-amber-400"
                                  : det.type === "animal"
                                  ? "bg-emerald-400"
                                  : "bg-blue-400"
                              }`}
                            />
                            <strong className="capitalize text-slate-200">
                              {detectionLabel(det)}
                            </strong>
                          </div>
                          <span className="text-xs font-mono text-slate-400">
                            Confidence: {(det.score * 100).toFixed(1)}%
                          </span>
                        </div>

                        {det.uncertain && <UncertaintyNotice detection={det} />}

                        {det.species && (
                          <div className="text-xs bg-emerald-950/40 p-2 rounded border border-emerald-800/40 text-emerald-200 flex items-center justify-between">
                            <span>Species: <strong>{det.species.top1}</strong></span>
                            <span className="text-emerald-400 font-mono">
                              Ranking: {(det.species.ranking_score * 100).toFixed(1)}%
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Incident / Risk Banner */}
                  {cam.latestResult.risk && (
                    <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between text-xs">
                      <div>
                        <span className="text-slate-400">Risk Assessment: </span>
                        <strong className={
                          cam.latestResult.risk.level === 'CRITICAL' ? 'text-red-400' :
                          cam.latestResult.risk.level === 'HIGH' ? 'text-amber-400' :
                          cam.latestResult.risk.level === 'MEDIUM' ? 'text-yellow-400' : 'text-emerald-400'
                        }>
                          {cam.latestResult.risk.level} ({cam.latestResult.risk.score}/100)
                        </strong>
                      </div>
                      {cam.latestResult.event_id && (
                        <span className="font-mono text-slate-500 text-[11px]">
                          Event #{cam.latestResult.event_id.slice(0, 8)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 bg-slate-900/40 rounded border border-slate-800 text-center text-xs text-slate-400">
                  No objects detected in the latest frame sample.
                </div>
              )}
            </div>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs p-6 text-center space-y-2">
              <RefreshCw size={24} className="text-slate-600" />
              <p>Waiting for first sampled frame from Node C-21…</p>
              <p className="text-[11px] text-slate-600">
                Start camera streaming to send frames to the shared ML detection pipeline.
              </p>
            </div>
          )}

          {/* Diagnostics Toggle */}
          <div className="pt-2 border-t border-slate-800">
            <button
              onClick={() => setShowDiag(!showDiag)}
              className="text-xs text-slate-500 hover:text-slate-400 flex items-center gap-1 font-mono"
            >
              <span>[Diagnostics: {cam.diagnostics.sampleStage || "Idle"}]</span>
              {showDiag ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showDiag && (
              <pre className="mt-2 p-2 bg-slate-950 rounded text-[10px] text-slate-400 overflow-x-auto font-mono">
                {JSON.stringify(cam.diagnostics, null, 2)}
              </pre>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
