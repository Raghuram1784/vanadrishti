import { UncertaintyNotice, detectionLabel } from "@/components/analysis/UncertaintyNotice";
import { useEffect, useRef, useState } from "react";
import {
  ImagePlus,
  LoaderCircle,
  ScanLine,
  Upload,
  CheckCircle2,
  Camera,
  Image as ImageIcon,
} from "lucide-react";
import { toast } from "sonner";
import { useCameras } from "@/hooks/useCameras";
import { refreshData } from "@/hooks/usePolling";
import { analyzeImage, getEvent, getHealth, evidenceUrl } from "@/services/api";
import type { AnalyzeImageResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Empty, ErrorBanner, PageTitle } from "@/components/ui/shared";
import { DetectionImage } from "@/components/analysis/DetectionImage";
import { ResultPanels } from "@/components/analysis/ResultPanels";
import { DemoPanel } from "@/components/demo/DemoPanel";
import { LiveCameraPanel } from "@/components/live/LiveCameraPanel";
import { MobileCameraPanel } from "@/components/live/MobileCameraPanel";
import { CameraGridView } from "@/components/live/CameraGridView";
import { Layers, Smartphone } from "lucide-react";
import { message } from "@/lib/utils";
export default function Monitor() {
  const [mode, setMode] = useState<"grid" | "c18" | "c21" | "static">("grid");
  const cameras = useCameras();
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState("");
  const [camera, setCamera] = useState("");
  const [timestamp, setTimestamp] = useState("");
  const [patrol, setPatrol] = useState("registry");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnalyzeImageResponse>();
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [warming, setWarming] = useState(false);
  const selectionVersion = useRef(0);
  const input = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const version = selectionVersion.current;
    const previous = sessionStorage.getItem('vanadrishti:last-analysis');
    if (previous) getEvent(previous).then(event => {
      if (mounted.current && version === selectionVersion.current) setResult(event);
    }).catch(() => { /* Events remains available if the last ID no longer exists. */ });
    getHealth().then(health => {
      if (mounted.current) setWarming(!health.detector_ready || !health.species_model_ready);
    }).catch(() => { /* The shared health indicator handles connectivity errors. */ });
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  function choose(selected?: File) {
    if (!selected || busy) return;
    if (!["image/jpeg", "image/png"].includes(selected.type)) {
      toast.error("Choose a JPG or PNG image.");
      return;
    }
    if (selected.size > 20 * 1024 * 1024) {
      toast.error("Choose an image smaller than 20 MiB.");
      return;
    }
    setFile(selected);
    selectionVersion.current++;
    setResult(undefined);
    setError("");
  }
  async function analyze() {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (camera) form.append("camera_id", camera);
    if (timestamp) form.append("timestamp", `${timestamp}:00+05:30`);
    if (patrol !== "registry") form.append("authorized_patrol", patrol);
    setBusy(true);
    setElapsed(0);
    setError("");
    setResult(undefined);
    try {
      const health = await getHealth();
      setWarming(!health.detector_ready || !health.species_model_ready);
      const response = await analyzeImage(form);
      sessionStorage.setItem('vanadrishti:last-analysis', response.event_id);
      refreshData();
      toast.success("Analysis complete. Event saved.");
      if (mounted.current) { setResult(response); setWarming(false); }
    } catch (e) {
      const text = message(e);
      toast.error(text);
      if (mounted.current) setError(text);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="FOREST INTELLIGENCE / MONITOR"
        title={
          mode === "grid"
            ? "Command-center multi-camera surveillance."
            : mode === "c18"
            ? "Live Sector C-18 laptop camera node."
            : mode === "c21"
            ? "Sector C-21 Android mobile patrol ingestion."
            : "From a frame to understanding."
        }
      >
        {mode === "grid"
          ? "Six-camera surveillance overview: C-18 and C-21 real physical feeds; peripheral slots clearly marked simulated/inactive. Live inference, risk scoring, and alert routing."
          : mode === "c18"
          ? "Sector C-18 prototype node. Live sampled frames analyzed with MegaDetector V6 and BioCLIP."
          : mode === "c21"
          ? "Sector C-21 Android field patrol camera ingested via phone hotspot / Wi-Fi into the shared pipeline."
          : "Analyze a wildlife image with the existing detection, species, and risk pipeline."}
      </PageTitle>

      <div className="monitor-mode-tabs">
        <button
          type="button"
          className={`mode-tab ${mode === "grid" ? "active" : ""}`}
          onClick={() => setMode("grid")}
        >
          <Layers size={16} />
          <span>6-CAMERA OVERVIEW</span>
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "c18" ? "active" : ""}`}
          onClick={() => setMode("c18")}
        >
          <Camera size={16} />
          <span>C-18 LAPTOP CAM</span>
          <span className="live-indicator-dot" />
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "c21" ? "active" : ""}`}
          onClick={() => setMode("c21")}
        >
          <Smartphone size={16} />
          <span>C-21 MOBILE PATROL</span>
          <span className="live-indicator-dot" />
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "static" ? "active" : ""}`}
          onClick={() => setMode("static")}
        >
          <ImageIcon size={16} />
          <span>STATIC IMAGE</span>
        </button>
      </div>

      {mode === "grid" ? (
        <CameraGridView
          onSelectCamera={(id) => {
            if (id === "C-18") setMode("c18");
            else if (id === "C-21") setMode("c21");
            else {
              setCamera(id);
              setMode("static");
            }
          }}
        />
      ) : mode === "c18" ? (
        <LiveCameraPanel />
      ) : mode === "c21" ? (
        <MobileCameraPanel />
      ) : (
        <>
          <div className="demo-flow">1. Select camera <span>→</span> 2. Upload image <span>→</span> 3. Analyze <span>→</span> 4. Detections & species <span>→</span> 5. Context & risk <span>→</span> 6. Stored evidence & alert</div>
          <div className="monitor-grid">
        <section className="panel capture-panel">
          <div className="panel-heading">
            <h2>
              <ScanLine size={18} /> Image analysis workspace
            </h2>
            <span className="source-tag">REAL MODEL INFERENCE</span>
          </div>
          <div
            className="upload-zone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              choose(e.dataTransfer.files[0]);
            }}
          >
            {result?.evidence_image_url || (file && preview) ? (
              <DetectionImage
                url={result?.evidence_image_url ? evidenceUrl(result.evidence_image_url) : preview}
                detections={result?.detections || []}
              />
            ) : (
              <button
                className="upload-empty"
                onClick={() => input.current?.click()}
              >
                <span className="upload-icon">
                  <ImagePlus size={34} />
                </span>
                <h3>Bring the forest into focus</h3>
                <p>Drop a camera-trap image here, or browse files.</p>
                <span className="upload-hint">JPG OR PNG · UP TO 20 MiB</span>
                <span className="browse-label">
                  <Upload size={14} /> Choose image
                </span>
              </button>
            )}
            <input
              ref={input}
              type="file"
              accept="image/jpeg,image/png"
              aria-label="Upload wildlife image"
              className="sr-only"
              disabled={busy}
              onChange={(e) => choose(e.target.files?.[0])}
            />
          </div>
          {(file || result?.evidence_image_url) && (
            <div className="image-caption">
              <span>
                {result?.evidence_image_url ? 'Stored original evidence' : file?.name}
                <small>
                  {result?.evidence_image_url ? 'Available after refresh in Monitor, Events, and Alerts' : `${((file?.size || 0) / 1024).toFixed(0)} KB · Original image`}
                </small>
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => input.current?.click()}
              >
                Change image
              </Button>
            </div>
          )}
          {busy && (
            <div className="analysis-progress" role="status">
              <LoaderCircle className="animate-spin" />
              <div>
                <strong>{warming ? 'Initializing AI models and analyzing frame...' : 'Analyzing forest frame...'}</strong>
                <p>Detection → species ranking → context → risk assessment</p>
                <small>
                  {elapsed}s elapsed · Models may be warming up. First analysis
                  can take longer.
                  <br />
                  The API returns a complete result; individual stage progress
                  is unavailable.
                </small>
              </div>
            </div>
          )}
          {result && (
            <div className="analysis-summary">
              <CheckCircle2 size={16} />
              <div>Analysis complete · {result.detections.length} retained detections
                <small className="block mt-2">Event {result.event_id}</small>
                <small className="block mt-2">{result.evidence_image_url ? 'Evidence stored' : 'No stored image evidence for this event.'} · {result.risk.alert ? 'Alert created for ranger review' : 'No alert required'}</small>
              </div>
            </div>
          )}
        </section>
        <section className="panel settings-panel">
          <div className="panel-heading">
            <h2>Analysis context</h2>
          </div>
          <ErrorBanner text={cameras.error} retry={cameras.refresh} />
          <div className="form-fields">
            <label>
              Simulated camera
              <select
                value={camera}
                onChange={(e) => setCamera(e.target.value)}
                disabled={busy}
              >
                <option value="">CAM-01 · Default demo camera</option>
                {cameras.data?.cameras.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} · {c.name}
                  </option>
                ))}
              </select>
            </label>
            <p className="field-help">
              Simulated camera locations for prototype demonstration.
            </p>
            <label>
              Timestamp <span className="optional">optional · IST</span>
              <input
                type="datetime-local"
                value={timestamp}
                onChange={(e) => setTimestamp(e.target.value)}
                disabled={busy}
              />
            </label>
            <label>
              Authorized patrol
              <select
                value={patrol}
                onChange={(e) => setPatrol(e.target.value)}
                disabled={busy}
              >
                <option value="registry">Use camera registry</option>
                <option value="true">Yes · Authorized</option>
                <option value="false">No · Not authorized</option>
              </select>
            </label>
            <div className="context-note">
              Context helps assess the situation. It does not identify people or
              establish intent.
            </div>
            <Button
              className="w-full"
              disabled={!file || busy || !!cameras.error}
              onClick={analyze}
            >
              {busy ? <LoaderCircle className="animate-spin" /> : <ScanLine />}
              {busy ? "Analyzing…" : "Analyze with VanaDrishti"}
            </Button>
            {warming && <p className="field-help">AI models will initialize on the first analysis. The first request may take longer.</p>}
            {!file && (
              <p className="field-help text-center">
                Select an image to begin.
              </p>
            )}
            {error && (
              <p className="inline-error" role="alert">
                {error}
              </p>
            )}
          </div>
        </section>
      </div>
      {result && (
        <div className="analysis-results">
          <div className="section-label">
            <span>ANALYSIS RESULTS</span>
            <small>Event {result.event_id}</small>
          </div>
          {result.detections.length ? (
            <section className="panel">
              <div className="panel-heading">
                <h2>Detected objects & species</h2>
                <span className="subtle-badge">
                  {result.detections.length} DETECTIONS
                </span>
              </div>
              <div className="detection-cards">
                {result.detections.map((d, i) => (
                  <article className="detection-card" key={i}>
                    <div className="detection-title">
                      <span className={`object-dot object-${d.type}`} />
                      <strong>
                        {i + 1}. <span className="capitalize">{detectionLabel(d)}</span>
                      </strong>
                      <span>Detector score: {d.score.toFixed(4)}</span>
                    </div>
                    {d.uncertain ? <UncertaintyNotice detection={d} /> : d.type === "animal" ? (
                      d.species ? (
                        <>
                          <h3>{d.species.top1}</h3>
                          <p>
                            Ranking score{" "}
                            <strong>
                              {d.species.ranking_score.toFixed(4)}
                            </strong>
                          </p>
                          <ol className="species-ranks">
                            {d.species.top3.map((s, j) => (
                              <li key={s.label}>
                                <span>{j + 1}</span>
                                <span>{s.label}</span>
                                <strong>{s.ranking_score.toFixed(4)}</strong>
                              </li>
                            ))}
                          </ol>
                        </>
                      ) : (
                        <p>Species: Not classified. Species ranking unavailable for this crop.</p>
                      )
                    ) : (
                      <p>Context assessed without identity classification.</p>
                    )}
                  </article>
                ))}
              </div>
              {result.detections.some((d) => d.type === "animal") && (
                <p className="ranking-note">
                  Species values are model ranking scores, not calibrated
                  probabilities.
                </p>
              )}
            </section>
          ) : (
            <section className="panel">
              <Empty title="No detections found">
                No objects met the existing detector thresholds in this image.
              </Empty>
            </section>
          )}
          <ResultPanels event={result} />
        </div>
      )}
      <DemoPanel />
        </>
      )}
    </>
  );
}
