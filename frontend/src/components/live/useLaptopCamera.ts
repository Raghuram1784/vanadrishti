import { encodeJpeg } from './frameCapture';
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { createCameraSession, closeCameraSession, sendHeartbeat, postCameraFrame } from '@/services/api';
import type { LiveFrameResponse, SessionStatus } from '@/types/api';
import { message } from '@/lib/utils';
import { cameraErrorMessage, cameraPermission, errorName, listVideoInputs, openLaptopCamera, validDeviceId, waitForPreview } from './cameraAccess';

const CAMERA_ID = 'C-18';
export function useLaptopCamera() {
  const [running, setRunning] = useState(false), [starting, setStarting] = useState(false), [paused, setPaused] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('OFFLINE');
  const [intervalSec, setIntervalSec] = useState(3), [inFlight, setInFlight] = useState(false);
  const [capturedCount, setCapturedCount] = useState(0), [submittedCount, setSubmittedCount] = useState(0), [skippedCount, setSkippedCount] = useState(0);
  const [lastBlobSize, setLastBlobSize] = useState<number | null>(null), [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [latestResult, setLatestResult] = useState<LiveFrameResponse | null>(null), [analyzedFrameUrl, setAnalyzedFrameUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null), [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [diagnostics, setDiagnostics] = useState({ enumerated: false, permission: 'unknown', stage: 'Not started', attempt: 'None', errorName: 'None', deviceLabel: 'Default Camera', resolution: '—', streamActive: false, notice: '', sampleStage: 'Idle', sampleError: '' });
  const videoRef = useRef<HTMLVideoElement>(null), stream = useRef<MediaStream | null>(null);
  const session = useRef<string | null>(null), controller = useRef<AbortController | null>(null), generation = useRef(0);
  const active = useRef(false), pending = useRef(false), pause = useRef(false), mounted = useRef(true), url = useRef<string | null>(null);
  const sampleOperation = useRef<AbortController | null>(null);
  const heartbeatPending = useRef<Promise<unknown> | null>(null);
  const stopCameraInternal = useCallback(() => {
    generation.current++; controller.current?.abort();
    sampleOperation.current?.abort(); sampleOperation.current = null; active.current = false; pending.current = false; pause.current = false;
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    const old = session.current; session.current = null;
    // Close after a pending heartbeat so that a late heartbeat cannot revive this lease.
    if (old) void Promise.resolve(heartbeatPending.current).catch(() => {}).then(() => closeCameraSession(CAMERA_ID, old)).catch(() => {});
    if (mounted.current) {
      setRunning(false); setStarting(false); setPaused(false); setSessionStatus('OFFLINE'); setInFlight(false);
      setDiagnostics(d => ({ ...d, streamActive: false, resolution: '-', sampleStage: 'Stopped', sampleError: '' }));
    }
    // Cancellation settles encoding/transport; old continuations cannot mutate a new generation.
  }, []);
  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const list = await listVideoInputs(navigator.mediaDevices);
      if (!mounted.current) return;
      setDevices(list); setSelectedDevice(old => validDeviceId(list, old));
      setDiagnostics(d => ({ ...d, enumerated: true }));
      const permission = await cameraPermission();
      if (mounted.current) setDiagnostics(d => ({ ...d, permission }));
    } catch (e) { if (mounted.current) setDiagnostics(d => ({ ...d, notice: 'Device enumeration unavailable: ' + errorName(e) })); }
  }, []);
  useEffect(() => {
    mounted.current = true; void refreshDevices();
    navigator.mediaDevices?.addEventListener('devicechange', refreshDevices);
    return () => {
      mounted.current = false; stopCameraInternal();
      navigator.mediaDevices?.removeEventListener('devicechange', refreshDevices);
      if (url.current) URL.revokeObjectURL(url.current);
    };
  }, [refreshDevices, stopCameraInternal]);
  async function startCamera() {
    if (pending.current || active.current) return;
    pending.current = true; const version = ++generation.current;
    const abort = new AbortController(); controller.current = abort;
    setStarting(true); setError(null);
    setDiagnostics(d => ({ ...d, errorName: 'None', notice: '', stage: 'Checking browser support' }));
    let stage = 'Browser support', opened: MediaStream | null = null, sid: string | null = null;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new DOMException('Camera API unavailable', 'SecurityError');
      stage = 'Device enumeration'; setDiagnostics(d => ({ ...d, stage }));
      const list = await listVideoInputs(navigator.mediaDevices); abort.signal.throwIfAborted();
      setDevices(list); setDiagnostics(d => ({ ...d, enumerated: true }));
      if (!list.length) throw new DOMException('No video input', 'NotFoundError');
      const chosen = validDeviceId(list, selectedDevice); setSelectedDevice(chosen);
      setDiagnostics(d => ({ ...d, deviceLabel: list.find(d => d.deviceId === chosen)?.label || 'Default Camera', notice: selectedDevice && !chosen ? 'Previously selected camera is unavailable. Using Default Camera.' : '' }));
      stage = 'Opening camera'; setDiagnostics(d => ({ ...d, stage }));
      opened = await openLaptopCamera(navigator.mediaDevices, chosen, attempt => {
        if (version === generation.current) {
          setDiagnostics(d => ({ ...d, attempt }));
          if (attempt.includes('fallback')) setSelectedDevice('');
        }
      }, abort.signal);
      stream.current = opened;
      stage = 'Video playback'; setDiagnostics(d => ({ ...d, stage }));
      if (!videoRef.current) throw new DOMException('Video element unavailable', 'AbortError');
      await waitForPreview(videoRef.current, opened, abort.signal); abort.signal.throwIfAborted();
      const track = opened.getVideoTracks()[0];
      setDiagnostics(d => ({ ...d, streamActive: opened!.active, deviceLabel: track.label || 'Camera (label unavailable)', resolution: `${videoRef.current!.videoWidth} × ${videoRef.current!.videoHeight}` }));
      stage = 'Backend session registration'; setDiagnostics(d => ({ ...d, stage }));
      const created = await createCameraSession(CAMERA_ID, { device_name: 'Laptop Webcam', device_type: 'laptop_webcam' });
      sid = created.session_id;
      if (abort.signal.aborted) { void closeCameraSession(CAMERA_ID, sid).catch(() => {}); sid = null; abort.signal.throwIfAborted(); }
      session.current = sid; active.current = true; pause.current = false;
      track.onended = () => { if (version !== generation.current) return; stopCameraInternal(); if (mounted.current) setError('Camera disconnected. Reconnect it and press Start Camera.'); };
      setSessionStatus(created.status); setRunning(true); setPaused(false);
      setCapturedCount(0); setSubmittedCount(0); setSkippedCount(0); setLastBlobSize(null); setLastLatencyMs(null); setLatestResult(null);
      if (url.current) URL.revokeObjectURL(url.current); url.current = null; setAnalyzedFrameUrl(null);
      setDiagnostics(d => ({ ...d, stage: 'Ready', sampleStage: 'Waiting for video readiness', sampleError: '' })); void refreshDevices();
      toast.success('Laptop camera C-18 active and session registered.');
    } catch (e) {
      opened?.getTracks().forEach(track => track.stop());
      if (sid && sid !== session.current) void closeCameraSession(CAMERA_ID, sid).catch(() => {});
      if (version !== generation.current || !mounted.current) return;
      const text = stage === 'Backend session registration'
        ? `Camera preview opened, but backend session registration failed: ${message(e)}. Confirm the Phase 5A backend is running on port 8000 and restart it after code updates.`
        : stage === 'Device enumeration' && errorName(e) === 'TimeoutError'
          ? 'Camera device enumeration did not finish. Keep this tab active and retry in Chrome or Edge.'
          : cameraErrorMessage(e);
      stopCameraInternal(); setError(text);
      setDiagnostics(d => ({ ...d, stage, errorName: errorName(e) })); void refreshDevices(); toast.error(text);
    } finally { if (version === generation.current) { pending.current = false; setStarting(false); } }
  }
  useEffect(() => {
    if (!running) return;
    const version = generation.current;
    const heartbeat = async () => {
      const sid = session.current;
      if (!sid || heartbeatPending.current || !active.current) return;
      const promise = sendHeartbeat(CAMERA_ID, sid); heartbeatPending.current = promise;
      try { const updated = await promise; if (generation.current === version) setSessionStatus(updated.status); }
      catch { if (generation.current === version) setSessionStatus('DEGRADED'); }
      finally { if (heartbeatPending.current === promise) heartbeatPending.current = null; }
    };
    const timer = setInterval(() => void heartbeat(), 10000);
    return () => clearInterval(timer);
  }, [running]);
  useEffect(() => {
    if (!running) return;
    const version = generation.current;
    const sample = async () => {
      if (version !== generation.current || !mounted.current || !active.current || pause.current || document.hidden) return;
      if (sampleOperation.current) { setSkippedCount(n => n + 1); return; }
      const video = videoRef.current, sid = session.current;
      if (!sid || !video || video.readyState < 2 || video.videoWidth <= 0 || video.videoHeight <= 0) {
        setDiagnostics(d => ({ ...d, sampleStage: 'Waiting for video readiness' }));
        return;
      }
      const operation = new AbortController(); sampleOperation.current = operation; setInFlight(true);
      const current = () => version === generation.current && mounted.current && active.current && sampleOperation.current === operation;
      let stage = 'Drawing frame';
      const updateStage = (next: string) => {
        stage = next;
        if (current()) setDiagnostics(d => ({ ...d, sampleStage: next, sampleError: '' }));
      };
      try {
        updateStage('Drawing frame');
        const canvas = document.createElement('canvas');
        const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.max(1, Math.round(video.videoWidth * scale)); canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
        const ctx = canvas.getContext('2d'); if (!ctx) throw new Error('Canvas capture unavailable');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        updateStage('Encoding JPEG');
        const blob = await encodeJpeg(canvas, operation.signal);
        if (!current() || pause.current) return;
        setCapturedCount(n => n + 1); setLastBlobSize(blob.size);
        const form = new FormData(); form.append('file', blob, 'webcam_sample.jpg'); form.append('session_id', sid);
        const started = performance.now(); setSubmittedCount(n => n + 1);
        updateStage('Uploading frame');
        const result = await postCameraFrame(CAMERA_ID, form, {
          signal: operation.signal,
          onUploaded: () => updateStage('Waiting for backend inference'),
          onReceiving: () => updateStage('Receiving result'),
        });
        if (!current()) return;
        setLastLatencyMs(Math.round(performance.now() - started)); setLatestResult(result); setError(null);
        if (url.current) URL.revokeObjectURL(url.current); url.current = URL.createObjectURL(blob); setAnalyzedFrameUrl(url.current);
        updateStage('Result received');
      } catch (e) {
        if (current()) {
          // No automatic retries after an ambiguous request timeout or failed encoder.
          pause.current = true; setPaused(true);
          const text = `${stage}: ${message(e)}. Sampling paused; review the issue before resuming.`;
          setError(text);
          setDiagnostics(d => ({ ...d, sampleStage: errorName(e) === 'TimeoutError' ? 'Timeout' : 'Error', sampleError: text }));
        }
      } finally {
        if (sampleOperation.current === operation) {
          sampleOperation.current = null;
          if (version === generation.current && mounted.current) setInFlight(false);
        }
      }
    };
    const timer = setInterval(() => void sample(), intervalSec * 1000);
    return () => clearInterval(timer);
  }, [running, intervalSec]);
  return { running, starting, paused, sessionStatus, intervalSec, setIntervalSec, inFlight, capturedCount, submittedCount, skippedCount, lastBlobSize, lastLatencyMs,
    latestResult, analyzedFrameUrl, error, videoRef, devices, selectedDevice, setSelectedDevice, diagnostics, refreshDevices, startCamera,
    stopCamera: () => { stopCameraInternal(); toast.info('Camera stopped. Hardware released; session closure requested.'); },
    togglePause: () => { pause.current = !pause.current; setPaused(pause.current); if (!pause.current) { setError(null); setDiagnostics(d => ({ ...d, sampleStage: 'Waiting for video readiness', sampleError: '' })); } } };
}
