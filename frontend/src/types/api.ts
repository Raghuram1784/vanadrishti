export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ObjectType = "animal" | "person" | "vehicle";
export type AlertStatus =
  | "NEW"
  | "REVIEWING"
  | "PATROL_ASSIGNED"
  | "FALSE_ALARM"
  | "ESCALATED"
  | "RESOLVED";
export interface Health {
  status: string;
  service: string;
  detector_ready: boolean;
  species_model_ready: boolean;
}
export interface Camera {
  id: string;
  camera_id: string;
  name: string;
  latitude: number;
  longitude: number;
  zone: string;
  zone_name: string;
  zone_type: string;
  active: boolean;
  allowed_hours: { start: string; end: string } | null;
  patrol_authorized: boolean;
  simulated: true;
  disclaimer: string;
  notes: string | null;
}
export interface SpeciesResult {
  top1: string;
  ranking_score: number;
  top3: { label: string; ranking_score: number }[];
}
export interface Detection {
  uncertain?: boolean;
  uncertainty_reason?: string | null;
  candidate_signals?: { type: ObjectType; score: number }[];
  type: ObjectType;
  score: number;
  bbox: [number, number, number, number] | null;
  species: SpeciesResult | null;
}
export interface RiskAssessment {
  score: number;
  level: RiskLevel;
  alert: boolean;
  reasons: string[];
  recommended_action: string;
}
export interface Context {
  zone: string;
  hour: number;
  timezone: string;
  simulated: true;
  authorized_patrol: boolean;
  recent_wildlife_events: {
    event_id: string;
    camera_id: string;
    timestamp: string;
    species: string | null;
    ranking_score: number | null;
    distance_meters: number;
    simulated: true;
  }[];
}
export interface Event {
  evidence_image_path?: string | null;
  evidence_image_url?: string | null;
  evidence_media_type?: string | null;
  event_id: string;
  timestamp: string;
  simulated: true;
  source: "image" | "demo" | "live_camera";
  camera: Camera;
  detections: Detection[];
  context: Context;
  risk: RiskAssessment;
}
export type AnalyzeImageResponse = Event;
export interface Alert {
  evidence_image_url?: string | null;
  source?: 'image' | 'demo' | 'live_camera';
  id: string;
  timestamp: string;
  camera_id: string;
  simulated: true;
  risk_score: number;
  risk_level: RiskLevel;
  reasons: string[];
  status: AlertStatus;
}
export interface DemoScenario {
  scenario_id: string;
  title: string;
  description: string;
  expected_risk_level: RiskLevel;
  simulated: true;
}
export interface EventFilters {
  camera_id?: string;
  event_type?: string;
  limit?: number;
}
export type LiveMessage =
  | { type: 'event.created'; data: Event }
  | { type: 'alert.created' | 'alert.updated'; data: Alert };

export type EventState = "NEW" | "CONTINUATION" | "NO_DETECTION" | "UNCERTAIN_DETECTION";
export type SessionStatus = "ONLINE" | "DEGRADED" | "OFFLINE";

export interface CameraSession {
  camera_id: string;
  session_id: string;
  device_name: string;
  device_type: string;
  connected_at: string;
  last_seen: string;
  last_frame_at: string | null;
  frames_received: number;
  frames_analyzed: number;
  status: SessionStatus;
}

export interface RecentActivity {
  active: boolean;
  type?: string | null;
  last_confirmed_at?: string | null;
  last_event_id?: string | null;
  last_risk_level?: string | null;
  last_risk_score?: number | null;
  last_risk_alert?: boolean | null;
  last_risk_reasons?: string[] | null;
  last_recommended_action?: string | null;
  seconds_since_last_confirmed?: number | null;
  monitoring_status?: string | null;
}

export interface FrameAnalysis {
  status: "CONFIRMED_DETECTION" | "UNCERTAIN_DETECTION" | "NO_DETECTION" | "DEGRADED_FRAME" | "INVALID_FRAME" | "INFERENCE_ERROR";
  image_quality: {
    status: "GOOD" | "DEGRADED" | "UNUSABLE";
    reasons: string[];
  } | null;
  warnings: string[];
}

export interface LiveFrameResponse {
  frame_analysis?: FrameAnalysis | null;
  event_state: EventState;
  event_id: string | null;
  timestamp: string;
  simulated: true;
  camera_id: string;
  camera: Camera;
  detections: Detection[];
  context: Context;
  risk: RiskAssessment;
  evidence_image_url: string | null;
  session_id: string | null;
  recent_activity?: RecentActivity | null;
}

