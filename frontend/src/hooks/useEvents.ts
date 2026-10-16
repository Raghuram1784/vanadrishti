import { useCallback } from "react";
import { getEvents } from "@/services/api";
import type { Event, EventFilters, LiveMessage } from "@/types/api";
import { usePolling } from "./usePolling";
export function useEvents({
  camera_id,
  event_type,
  limit = 100,
}: EventFilters = {}) {
  return usePolling(
    useCallback(
      () => getEvents({ camera_id, event_type, limit }),
      [camera_id, event_type, limit],
    ),
    15000,
    useCallback((data: Event[], message: LiveMessage) => {
      if (message.type !== 'event.created') return data;
      const event = message.data;
      if (camera_id && event.camera.id !== camera_id) return data;
      if (event_type && !event.detections.some(d => d.type === event_type)) return data;
      return [event, ...data.filter(e => e.event_id !== event.event_id)]
        .sort((a,b) => Date.parse(b.timestamp) - Date.parse(a.timestamp)).slice(0, limit);
    }, [camera_id, event_type, limit]),
  );
}
