import { UncertaintyNotice, detectionLabel } from "@/components/analysis/UncertaintyNotice";
import { Camera, Play, Square, Pause, Activity, Layers, ShieldAlert, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DetectionImage } from "@/components/analysis/DetectionImage";
import { ResultPanels } from "@/components/analysis/ResultPanels";
import { useLaptopCamera } from "./useLaptopCamera";
import { frameQualityNotice } from "./frameQuality";

const CAMERA_ID = "C-18";
const CAMERA_NAME = "Sector C-18 Trail Camera — Laptop Prototype Node";
const ZONE_TYPE = "CORE";

export function LiveCameraPanel() {
  const {
    running, starting, paused, sessionStatus, intervalSec, setIntervalSec, inFlight,
    capturedCount, submittedCount, skippedCount, lastBlobSize, lastLatencyMs,
    latestResult, analyzedFrameUrl, error, videoRef, devices, selectedDevice,
    setSelectedDevice, diagnostics, refreshDevices, startCamera, stopCamera, togglePause,
  } = useLaptopCamera();
  const qualityNotice = latestResult ? frameQualityNotice(latestResult.frame_analysis) : null;

  return (
    <div className="live-camera-layout">
      {/* Top Status Bar */}
      <div className="live-header panel">
        <div className="live-camera-identity">
          <div className="live-node-badge">
            <Camera size={18} />
            <strong>{CAMERA_ID}</strong>
          </div>
          <div>
            <h3>{CAMERA_NAME}</h3>
            <span className="live-camera-meta">
              Simulated Zone: <strong className="zone-tag">{ZONE_TYPE}</strong> · Demonstration Node
            </span>
          </div>
        </div>

        <div className="live-controls-cluster">
          <div className="sampling-rate-selector">
            <span className="rate-label">Sample cadence:</span>
            {[2, 3, 5].map((s) => (
              <button
                key={s}
                className={`rate-btn ${intervalSec === s ? "active" : ""}`}
                onClick={() => setIntervalSec(s)}
                disabled={inFlight}
              >
                {s}s
              </button>
            ))}
          </div>

          <div className="live-actions">
            {starting && <Button variant="outline" onClick={stopCamera}>Cancel Startup</Button>}
            {!running ? (
              <Button onClick={startCamera} disabled={starting} className="btn-start-camera">
                <Play size={16} /> {starting ? "Starting Camera…" : "Start Camera"}
              </Button>
            ) : (
              <>
                <Button
                  variant={paused ? "default" : "outline"}
                  onClick={togglePause}
                  size="sm"
                >
                  {paused ? <Play size={14} /> : <Pause size={14} />}
                  {paused ? "Resume Analysis" : "Pause Analysis"}
                </Button>
                <Button variant="destructive" onClick={stopCamera} size="sm">
                  <Square size={14} /> Stop Camera
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      <section className="panel" style={{padding: '1rem'}}>
        <label>Available Cameras
          <select aria-label="Available Cameras" value={selectedDevice}
            disabled={running || starting} onChange={e => setSelectedDevice(e.target.value)}>
            <option value="">Default Camera</option>
            {devices.filter(d => d.deviceId).map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${index + 1} (label unavailable)`}</option>
            ))}
          </select>
        </label>{' '}
        <Button variant="outline" size="sm" disabled={starting} onClick={() => void refreshDevices()}>Refresh Cameras</Button>
        <p className="field-help">Stop the camera before changing devices. Camera labels may appear after permission is granted.</p>
        {diagnostics.enumerated && devices.length === 0 && <div role="status">
          <p>No camera device detected by this browser. Windows or the browser is not exposing a video input.</p>
          <ul>
            <li>Confirm the webcam works in the Windows Camera app, then close that app.</li>
            <li>Close Teams, Zoom, Meet or OBS if they are using the camera.</li>
            <li>Check Windows Settings → Privacy &amp; security → Camera; enable camera access and desktop app access.</li>
            <li>Check Chrome/Edge site camera permissions. Reload after changing permissions.</li>
          </ul>
        </div>}
        <details style={{marginTop: '1rem'}}>
          <summary>Camera Diagnostics</summary>
          <dl className="context-grid" style={{marginTop: '.75rem'}}>
            <div><dt>Browser camera API</dt><dd>{typeof navigator.mediaDevices?.getUserMedia === 'function' ? 'Available' : 'Unavailable'}</dd></div>
            <div><dt>Secure context</dt><dd>{window.isSecureContext ? 'Yes' : 'No'}</dd></div>
            <div><dt>Video devices found</dt><dd>{diagnostics.enumerated ? devices.length : 'Unknown'}</dd></div>
            <div><dt>Selected / opened device</dt><dd>{devices.find(d => d.deviceId === selectedDevice)?.label || diagnostics.deviceLabel}</dd></div>
            <div><dt>Stream active</dt><dd>{diagnostics.streamActive ? 'Yes' : 'No'}</dd></div>
            <div><dt>Video resolution</dt><dd>{diagnostics.resolution}</dd></div>
            <div><dt>Camera permission</dt><dd>{diagnostics.permission}</dd></div>
            <div><dt>Startup / failure stage</dt><dd>{diagnostics.stage}</dd></div>
            <div><dt>Sampling stage</dt><dd>{diagnostics.sampleStage || "Idle"}</dd></div>
            <div><dt>Sampling error</dt><dd>{diagnostics.sampleError || "None"}</dd></div>
            <div><dt>Constraint attempted</dt><dd>{diagnostics.attempt}</dd></div>
            <div><dt>Error name</dt><dd>{diagnostics.errorName}</dd></div>
          </dl>
          {diagnostics.notice && <p>{diagnostics.notice}</p>}
          <p className="field-help">Diagnostics describe this browser. No camera starts until you press Start Camera.</p>
        </details>
      </section>

      {/* Metrics Bar */}
      <div className="live-metrics-bar">
        <div className="metric-item">
          <span className="metric-label">Connection Status</span>
          <span className={`status-pill status-${sessionStatus.toLowerCase()}`}>
            <span className="status-dot" />
            {sessionStatus}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Frames Captured</span>
          <span className="metric-val">{capturedCount}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Inference Submissions</span>
          <span className="metric-val">{submittedCount}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Skipped (In-Flight)</span>
          <span className={`metric-val ${skippedCount > 0 ? "metric-warn" : ""}`}>
            {skippedCount}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Sample Size</span>
          <span className="metric-val">
            {lastBlobSize ? `${Math.round(lastBlobSize / 1024)} KB` : "—"}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Inference Latency</span>
          <span className="metric-val">
            {lastLatencyMs ? `${lastLatencyMs} ms` : "—"}
          </span>
        </div>
      </div>

      {error && (
        <div className="inline-error" role="alert">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Dual Monitor Grid */}
      <div className="monitor-grid">
        {/* Left: Live Viewfinder */}
        <section className="panel viewfinder-panel">
          <div className="panel-heading">
            <h2>
              <Camera size={18} /> Live Webcam Feed
            </h2>
            {running && (
              <span className={`live-pulse-badge ${paused ? "paused" : ""}`}>
                {paused ? "SAMPLING PAUSED" : inFlight ? "ANALYZING SAMPLE..." : "SAMPLING ACTIVE"}
              </span>
            )}
          </div>

          <div className="viewfinder-wrap">
            <video
              ref={videoRef}
              className={`viewfinder-video ${running || diagnostics.streamActive ? "active" : "standby"}`}
              autoPlay
              muted
              playsInline
            />

            {!running && !diagnostics.streamActive && (
              <div className="viewfinder-placeholder">
                <Camera size={48} className="placeholder-icon" />
                <h3>Laptop Camera Standby</h3>
                <p>Click "Start Camera" above to begin field prototype capture.</p>
                <small>Uses your laptop webcam to feed sampled frames to MegaDetector V6.</small>
              </div>
            )}

            {running && (
              <div className="viewfinder-crosshair">
                <div className="ch-corner ch-tl" />
                <div className="ch-corner ch-tr" />
                <div className="ch-corner ch-bl" />
                <div className="ch-corner ch-br" />
                <div className="ch-center" />
                <div className="ch-hud">
                  <span>NODE: {CAMERA_ID}</span>
                  <span>INTERVAL: {intervalSec}s</span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right: Analyzed Frame & Detections Overlay */}
        <section className="panel analyzed-panel">
          <div className="panel-heading">
            <h2>
              <Activity size={18} /> Latest Sampled Analysis
            </h2>
            {latestResult && (
              <span className={`event-state-pill state-${latestResult.event_state.toLowerCase()}`}>
                {latestResult.event_state === "UNCERTAIN_DETECTION" && "UNCERTAIN DETECTION"}
                {latestResult.event_state === "NEW" && "NEW EVENT"}
                {latestResult.event_state === "CONTINUATION" && "CONTINUATION (DEDUPED)"}
                {latestResult.event_state === "NO_DETECTION" && "NO DETECTION"}
              </span>
            )}
          </div>

          {qualityNotice && (
            <div className="active-event-alert-banner" role="status">
              <AlertTriangle size={18} className="text-warning shrink-0" />
              <p>{qualityNotice}</p>
            </div>
          )}
          <div className="analyzed-frame-wrap">
            {analyzedFrameUrl ? (
              <DetectionImage
                url={analyzedFrameUrl}
                detections={latestResult?.detections || []}
              />
            ) : (
              <div className="analyzed-empty">
                <Layers size={36} />
                <p>Waiting for first analyzed frame...</p>
                <small>Frames are automatically sampled every {intervalSec} seconds.</small>
              </div>
            )}
          </div>

          {latestResult && (
            <>
              <div className="analyzed-summary-banner">
                <div className="summary-left">
                  <strong>
                    {latestResult.detections.length === 0
                      ? "No detection in latest sample"
                      : latestResult.detections.length === 1
                      ? "1 object detected"
                      : `${latestResult.detections.length} objects detected`}
                  </strong>
                  <span className="summary-sub">
                    {latestResult.event_state === "UNCERTAIN_DETECTION" &&
                      "Additional observation recommended. No event or alert created."}
                    {latestResult.event_state === "NEW" && "Persisted as new event."}
                    {latestResult.event_state === "CONTINUATION" &&
                      "Existing activity within deduplication window. No duplicate alert created."}
                    {latestResult.event_state === "NO_DETECTION" &&
                      "No objects exceeded confidence threshold in this sample."}
                  </span>
                </div>
                {(latestResult.risk.alert || latestResult.recent_activity?.last_risk_alert) && (
                  <span className="alert-callout">
                    <ShieldAlert size={16} /> Ranger Review Required
                  </span>
                )}
              </div>

              {/* Dual Temporal Continuity Overview: Latest Sample vs Recent Ongoing Activity */}
              <div className="temporal-activity-tracker">
                <div className="tracker-card tracker-latest">
                  <span className="tracker-tag">LATEST SAMPLE</span>
                  <div className="tracker-main">
                    <strong>
                      {latestResult.detections.length === 0
                        ? "No detection in latest sample"
                        : latestResult.detections.length === 1
                        ? `${
                            latestResult.detections[0].type
                              ? latestResult.detections[0].type.charAt(0).toUpperCase() +
                                latestResult.detections[0].type.slice(1)
                              : "1 object"
                          } detected`
                        : `${latestResult.detections.length} objects detected`}
                    </strong>
                    <span className="tracker-status">
                      {latestResult.detections.length > 0 ? (
                        latestResult.detections[0].uncertain ? (
                          "Uncertain candidate"
                        ) : (
                          `Detector score: ${latestResult.detections[0].score.toFixed(4)}`
                        )
                      ) : (
                        qualityNotice ? "Visibility limited; absence not established" : "No retained detections; absence not established"
                      )}
                    </span>
                  </div>
                </div>

                <div
                  className={`tracker-card tracker-recent ${
                    latestResult.recent_activity?.active ? "status-active" : "status-idle"
                  }`}
                >
                  <div className="tracker-head-row">
                    <span className="tracker-tag">RECENT ACTIVITY</span>
                    {latestResult.recent_activity?.active && (
                      <span className="tracker-live-indicator">
                        <span className="live-ping" /> Active
                      </span>
                    )}
                  </div>
                  <div className="tracker-main">
                    {latestResult.recent_activity?.active ? (
                      <>
                        <strong>
                          {latestResult.recent_activity.type
                            ? `${
                                latestResult.recent_activity.type.charAt(0).toUpperCase() +
                                latestResult.recent_activity.type.slice(1)
                              } activity observed recently`
                            : "Activity observed recently"}
                        </strong>
                        <div className="tracker-meta-list">
                          <span>
                            Last confirmed:{" "}
                            <strong>
                              {latestResult.recent_activity.seconds_since_last_confirmed === 0
                                ? "Just now"
                                : `${latestResult.recent_activity.seconds_since_last_confirmed}s ago`}
                            </strong>
                          </span>
                          {latestResult.recent_activity.last_event_id && (
                            <span>
                              Event:{" "}
                              <code>
                                {latestResult.recent_activity.last_event_id.slice(0, 8)}…
                              </code>
                            </span>
                          )}
                          {latestResult.recent_activity.last_risk_level && (
                            <span
                              className={`risk-badge-micro risk-${latestResult.recent_activity.last_risk_level.toLowerCase()}`}
                            >
                              {latestResult.recent_activity.last_risk_level} RISK
                            </span>
                          )}
                        </div>
                        <span className="tracker-footer-note">Monitoring continues</span>
                      </>
                    ) : (
                      <>
                        <strong className="text-muted">No active activity</strong>
                        <span className="tracker-footer-note">Monitoring continues</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      {/* Detections & Intelligence Cards */}
      {latestResult && (() => {
        const hasActiveRecentEvent = Boolean(
          latestResult.recent_activity?.active && latestResult.recent_activity.last_risk_level
        );

        const displayRisk =
          latestResult.detections.length === 0 && hasActiveRecentEvent
            ? {
                score: latestResult.recent_activity!.last_risk_score ?? 0,
                level: (latestResult.recent_activity!.last_risk_level as "CRITICAL" | "HIGH" | "MEDIUM" | "LOW") || "LOW",
                alert: Boolean(latestResult.recent_activity!.last_risk_alert),
                reasons: [
                  `Recent activity context: ${latestResult.recent_activity!.type || "object"} observed ${
                    latestResult.recent_activity!.seconds_since_last_confirmed === 0
                      ? "just now"
                      : `${latestResult.recent_activity!.seconds_since_last_confirmed}s ago`
                  } (Event ${latestResult.recent_activity!.last_event_id?.slice(0, 8)}…).`,
                  ...(latestResult.recent_activity!.last_risk_reasons || []),
                  "Latest sample had no detection; scene is not assumed clear while activity remains within temporal persistence window.",
                ],
                recommended_action:
                  latestResult.recent_activity!.last_recommended_action ||
                  "Maintain active monitoring of ongoing event.",
              }
            : latestResult.risk;

        return (
          <div className="analysis-results">
            {/* Active event context when the latest sample has no detections */}
            {latestResult.detections.length === 0 && hasActiveRecentEvent && (
              <div className="active-event-alert-banner">
                <AlertTriangle size={18} className="text-warning shrink-0" />
                <div>
                  <strong>
                    Active Event Context: {latestResult.recent_activity?.last_risk_level} RISK Event Under Observation
                  </strong>
                  <p>
                    No detection in latest sample, but confirmed{" "}
                    {latestResult.recent_activity?.type} activity was observed{" "}
                    {latestResult.recent_activity?.seconds_since_last_confirmed === 0
                      ? "just now"
                      : `${latestResult.recent_activity?.seconds_since_last_confirmed}s ago`}
                    . Active Event <code>{latestResult.recent_activity?.last_event_id}</code> remains under observation until inactivity window expires.
                  </p>
                </div>
              </div>
            )}

            {latestResult.detections.length > 0 ? (
              <section className="panel">
                <div className="panel-heading">
                  <h2>Detected Objects & BioCLIP Species</h2>
                  <span className="subtle-badge">
                    {latestResult.detections.length === 1
                      ? "1 DETECTION"
                      : `${latestResult.detections.length} DETECTIONS`}
                  </span>
                </div>
                <div className="detection-cards">
                  {latestResult.detections.map((d, i) => (
                    <article className="detection-card" key={i}>
                      <div className="detection-title">
                        <span className={`object-dot object-${d.type}`} />
                        <strong>
                          {i + 1}. <span className="capitalize">{detectionLabel(d)}</span>
                        </strong>
                        <span>Detector score: {d.score.toFixed(4)}</span>
                      </div>
                      {d.uncertain ? (
                        <UncertaintyNotice detection={d} />
                      ) : d.type === "animal" ? (
                        d.species ? (
                          <>
                            <h3>{d.species.top1}</h3>
                            <p>
                              Ranking score{" "}
                              <strong>{d.species.ranking_score.toFixed(4)}</strong>
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
                        <p>Neutral context assessed without individual identity classification.</p>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {/* Context & Risk Panels */}
            <ResultPanels
              event={{
                event_id:
                  latestResult.event_id ||
                  (hasActiveRecentEvent
                    ? latestResult.recent_activity!.last_event_id!
                    : "unrecorded-sample"),
                timestamp: latestResult.timestamp,
                simulated: true,
                source: "live_camera",
                camera: latestResult.camera,
                detections: latestResult.detections,
                context: latestResult.context,
                risk: qualityNotice ? { ...displayRisk, reasons: [qualityNotice, ...displayRisk.reasons] } : displayRisk,
                evidence_image_url: latestResult.evidence_image_url,
              }}
            />
          </div>
        );
      })()}
    </div>
  );
}
