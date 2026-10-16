import { uploadCameraFrame, type FrameRequestOptions } from './frameRequest';
import type {
  Alert,
  AlertStatus,
  AnalyzeImageResponse,
  Camera,
  CameraSession,
  DemoScenario,
  Event,
  EventFilters,
  Health,
} from "@/types/api";
const BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");
export const evidenceUrl = (path: string) => `${BASE}${path}`;
export const liveUrl = () => `${BASE.replace(/^http/, 'ws')}/ws/events`;
export const getEvent = (id: string) => request<Event>(`/api/events/${encodeURIComponent(id)}`);
export class ApiError extends Error {
  constructor(public status: number, detail: string) { super(`HTTP ${status}: ${detail}`); this.name = "ApiError"; }
}
async function request<T>(
  path: string,
  init?: RequestInit,
  timeout = 20000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body: { detail?: unknown } = await response
        .json()
        .catch(() => ({}));
      const detail =
        typeof body.detail === "string"
          ? body.detail
          : response.status === 422
            ? "Check the image, timestamp, and selected values."
            : `Request could not be completed (${response.status}).`;
      throw new ApiError(response.status, detail);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw new Error(
        "Request timed out. Analysis may still finish on the server; check Events before retrying.",
      );
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach the backend. Check that FastAPI is running on port 8000.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
export const getHealth = () => request<Health>("/health");
export const getCameras = () =>
  request<{ simulated: true; disclaimer: string; cameras: Camera[] }>(
    "/api/cameras",
  );
export const getCamera = (id: string) =>
  request<Camera>(`/api/cameras/${encodeURIComponent(id)}`);
export const getEvents = (filters: EventFilters = {}) => {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return request<Event[]>(`/api/events?${query}`);
};
export const getAlerts = (includeResolved = false) =>
  request<Alert[]>(`/api/alerts?include_resolved=${includeResolved}`);
export const analyzeImage = (form: FormData) =>
  request<AnalyzeImageResponse>(
    "/api/analyze-image",
    { method: "POST", body: form },
    600000,
  );
export const updateAlert = (id: string, action: AlertStatus) =>
  request<Alert>(`/api/alerts/${encodeURIComponent(id)}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
export const getDemoScenarios = () =>
  request<{ simulated: true; scenarios: DemoScenario[] }>(
    "/api/demo/scenarios",
  );
export const runDemoScenario = (id: string) =>
  request<{ scenario_id: string; simulated: true; events: Event[] }>(
    `/api/demo/scenarios/${encodeURIComponent(id)}/run`,
    { method: "POST" },
  );

export const createCameraSession = (
  cameraId: string,
  body?: { device_name?: string; device_type?: string },
) =>
  request<CameraSession>(`/api/cameras/${encodeURIComponent(cameraId)}/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });

export const sendHeartbeat = (cameraId: string, sessionId: string) =>
  request<CameraSession>(
    `/api/cameras/${encodeURIComponent(cameraId)}/heartbeat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    },
    5000,
  );

export const closeCameraSession = (cameraId: string, sessionId: string) =>
  request<{ message: string; session_id: string; status: string }>(
    `/api/cameras/${encodeURIComponent(cameraId)}/session/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
    5000,
  );

export const getCameraSessions = () =>
  request<CameraSession[]>("/api/camera-sessions");

export const postCameraFrame = (cameraId: string, form: FormData, options?: FrameRequestOptions) =>
  uploadCameraFrame(`${BASE}/api/cameras/${encodeURIComponent(cameraId)}/frame`, form, options);
