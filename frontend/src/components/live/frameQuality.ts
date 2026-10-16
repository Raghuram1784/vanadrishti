import type { FrameAnalysis } from "@/types/api";

// Presentation only: never changes detection, incident, or contextual risk policy.
export function frameQualityNotice(analysis?: FrameAnalysis | null): string | null {
  const quality = analysis?.image_quality;
  if (!quality) {
    return "Frame quality unavailable. No detection does not establish that the area is clear.";
  }
  if (quality.status === "GOOD") return null;
  return [
    `Image quality ${quality.status.toLowerCase()}.`,
    "No detection does not establish that the area is clear; obtain a usable image.",
    "Any retained detections and recent activity still apply.",
    ...quality.reasons,
    ...(analysis?.warnings || []),
  ].join(" ");
}
