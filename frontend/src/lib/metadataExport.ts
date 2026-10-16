import type { Alert, Detection, Event } from "@/types/api";

export interface NormalizedDetectionMetadata {
  index: number;
  type: string;
  detector_score: number;
  bbox_normalized: [number, number, number, number] | null;
  uncertain: boolean;
  uncertainty_reason: string | null;
  candidate_signals: { type: string; score: number }[] | null;
  species: {
    top1: string;
    ranking_score: number;
    top3: { label: string; ranking_score: number }[];
  } | null;
}

export interface StandardizedEventMetadata {
  schema_version: "1.0";
  event_id: string;
  timestamp: string;
  camera: {
    id: string;
    name: string;
    source: "live_camera" | "image" | "demo";
    hardware_node: string;
    geographic_zone: string;
    zone_type: string;
    operational_policy: string | null;
    coordinates: {
      latitude: number;
      longitude: number;
      coordinate_type: "configured_geographic_metadata";
    };
  };
  detections: NormalizedDetectionMetadata[];
  risk: {
    score: number;
    level: string;
    alert_required: boolean;
    reasons: string[];
    recommended_action: string;
  };
  incident: {
    alert_id: string | null;
    status: string;
    policy: string | null;
    review_timestamp: string | null;
  };
  frame_evidence: {
    evidence_image_url: string | null;
    media_type: string | null;
    disclaimer: string;
  };
}

/**
 * Format an existing event record into a clean, standardized metadata object.
 * Strictly preserves original detector confidence, species ranking, and bbox coordinates.
 */
export function formatEventMetadata(
  event: Event,
  alert?: Alert | null,
): StandardizedEventMetadata {
  const hardwareNode =
    event.camera.id === "C-18"
      ? "Sector C-18 Laptop Webcam (Prototype Node)"
      : event.camera.id === "C-21"
      ? "Sector C-21 Android Mobile Patrol (Hotspot Node)"
      : `Synthetic Corridor Slot (${event.camera.id})`;

  const detections: NormalizedDetectionMetadata[] = (event.detections || []).map(
    (d: Detection, index: number) => ({
      index,
      type: d.type,
      detector_score: Number(d.score),
      bbox_normalized: d.bbox ? [d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3]] : null,
      uncertain: Boolean(d.uncertain),
      uncertainty_reason: d.uncertainty_reason || null,
      candidate_signals: d.candidate_signals || null,
      species:
        d.type === "animal" && d.species
          ? {
              top1: d.species.top1,
              ranking_score: Number(d.species.ranking_score),
              top3: d.species.top3 || [],
            }
          : null,
    }),
  );

  return {
    schema_version: "1.0",
    event_id: event.event_id,
    timestamp: event.timestamp,
    camera: {
      id: event.camera.id,
      name: event.camera.name,
      source: event.source,
      hardware_node: hardwareNode,
      geographic_zone: event.camera.zone,
      zone_type: event.camera.zone_type,
      operational_policy: event.policy || event.camera.policy || null,
      coordinates: {
        latitude: event.camera.latitude,
        longitude: event.camera.longitude,
        coordinate_type: "configured_geographic_metadata",
      },
    },
    detections,
    risk: {
      score: event.risk.score,
      level: event.risk.level,
      alert_required: Boolean(event.risk.alert),
      reasons: event.risk.reasons || [],
      recommended_action: event.risk.recommended_action || "Routine monitoring",
    },
    incident: {
      alert_id: alert?.id || (event.risk.alert ? event.event_id : null),
      status: alert?.status || (event.risk.alert ? "NEW" : "NONE"),
      policy: alert?.policy || event.policy || event.camera.policy || null,
      review_timestamp: alert?.timestamp || null,
    },
    frame_evidence: {
      evidence_image_url: event.evidence_image_url || null,
      media_type: event.evidence_media_type || (event.evidence_image_url ? "image/jpeg" : null),
      disclaimer: "Metadata reflects recorded observation rather than complete raw inference history.",
    },
  };
}

/**
 * Returns formatted JSON string for an event.
 */
export function eventToJson(event: Event, alert?: Alert | null): string {
  const metadata = formatEventMetadata(event, alert);
  return JSON.stringify(metadata, null, 2);
}

/**
 * Triggers a browser download of formatted JSON.
 */
export function downloadEventJson(event: Event, alert?: Alert | null): void {
  const jsonStr = eventToJson(event, alert);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `vanadrishti-event-${event.event_id}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/**
 * Copies formatted JSON to clipboard.
 */
export async function copyEventJsonToClipboard(
  event: Event,
  alert?: Alert | null,
): Promise<boolean> {
  const jsonStr = eventToJson(event, alert);
  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(jsonStr);
      return true;
    } catch {
      // Fallback below
    }
  }

  // Fallback for non-secure contexts or permission denials
  try {
    const textarea = document.createElement("textarea");
    textarea.value = jsonStr;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const success = document.execCommand("copy");
    document.body.removeChild(textarea);
    return success;
  } catch {
    return false;
  }
}

/**
 * Escapes a single value for standard CSV compatibility (RFC 4180).
 */
function escapeCsv(val: unknown): string {
  if (val === null || val === undefined) return "";
  const str = String(val);
  if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Converts a list of events into CSV format.
 * Emits one row per detected object.
 * If an event has 0 detections, emits 1 row with detection columns blank so the event record is retained.
 */
export function eventsToCsv(events: Event[], alerts: Alert[] = []): string {
  const headers = [
    "event_id",
    "timestamp_iso",
    "camera_id",
    "camera_name",
    "camera_source",
    "geographic_zone",
    "zone_type",
    "operational_policy",
    "latitude",
    "longitude",
    "detection_index",
    "detection_type",
    "detector_score",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "uncertain",
    "uncertainty_reason",
    "species_top1",
    "species_ranking_score",
    "risk_level",
    "risk_score",
    "alert_required",
    "risk_reasons",
    "recommended_action",
    "incident_status",
    "evidence_image_url",
  ];

  const rows: string[] = [headers.join(",")];

  for (const event of events) {
    const alert = alerts.find((a) => a.id === event.event_id);
    const policy = event.policy || event.camera.policy || "";
    const incidentStatus = alert?.status || (event.risk.alert ? "NEW" : "NONE");
    const reasonsStr = (event.risk.reasons || []).join(" | ");

    if (!event.detections || event.detections.length === 0) {
      // Event with zero detections
      const row = [
        escapeCsv(event.event_id),
        escapeCsv(event.timestamp),
        escapeCsv(event.camera.id),
        escapeCsv(event.camera.name),
        escapeCsv(event.source),
        escapeCsv(event.camera.zone),
        escapeCsv(event.camera.zone_type),
        escapeCsv(policy),
        escapeCsv(event.camera.latitude),
        escapeCsv(event.camera.longitude),
        escapeCsv(""), // detection_index
        escapeCsv("none"), // detection_type
        escapeCsv(""), // detector_score
        escapeCsv(""), // bbox_x1
        escapeCsv(""), // bbox_y1
        escapeCsv(""), // bbox_x2
        escapeCsv(""), // bbox_y2
        escapeCsv(false), // uncertain
        escapeCsv(""), // uncertainty_reason
        escapeCsv(""), // species_top1
        escapeCsv(""), // species_ranking_score
        escapeCsv(event.risk.level),
        escapeCsv(event.risk.score),
        escapeCsv(event.risk.alert),
        escapeCsv(reasonsStr),
        escapeCsv(event.risk.recommended_action),
        escapeCsv(incidentStatus),
        escapeCsv(event.evidence_image_url || ""),
      ];
      rows.push(row.join(","));
    } else {
      // One row per detection
      event.detections.forEach((d: Detection, index: number) => {
        const row = [
          escapeCsv(event.event_id),
          escapeCsv(event.timestamp),
          escapeCsv(event.camera.id),
          escapeCsv(event.camera.name),
          escapeCsv(event.source),
          escapeCsv(event.camera.zone),
          escapeCsv(event.camera.zone_type),
          escapeCsv(policy),
          escapeCsv(event.camera.latitude),
          escapeCsv(event.camera.longitude),
          escapeCsv(index),
          escapeCsv(d.type),
          escapeCsv(d.score !== undefined ? d.score : ""),
          escapeCsv(d.bbox ? d.bbox[0] : ""),
          escapeCsv(d.bbox ? d.bbox[1] : ""),
          escapeCsv(d.bbox ? d.bbox[2] : ""),
          escapeCsv(d.bbox ? d.bbox[3] : ""),
          escapeCsv(Boolean(d.uncertain)),
          escapeCsv(d.uncertainty_reason || ""),
          escapeCsv(d.species?.top1 || ""),
          escapeCsv(d.species?.ranking_score !== undefined ? d.species.ranking_score : ""),
          escapeCsv(event.risk.level),
          escapeCsv(event.risk.score),
          escapeCsv(event.risk.alert),
          escapeCsv(reasonsStr),
          escapeCsv(event.risk.recommended_action),
          escapeCsv(incidentStatus),
          escapeCsv(event.evidence_image_url || ""),
        ];
        rows.push(row.join(","));
      });
    }
  }

  return rows.join("\n");
}

/**
 * Triggers a browser download of CSV data.
 */
export function downloadEventsCsv(
  events: Event[],
  alerts: Alert[] = [],
  filename = "vanadrishti-detections-export.csv",
): void {
  const csvStr = eventsToCsv(events, alerts);
  const blob = new Blob([csvStr], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
