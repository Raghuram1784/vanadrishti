import { useCallback } from "react";
import { getAlerts } from "@/services/api";
import { usePolling } from "./usePolling";
import type { Alert, LiveMessage } from '@/types/api';
export const useAlerts = (includeResolved = false) =>
  usePolling(useCallback(() => getAlerts(includeResolved), [includeResolved]), 15000,
    useCallback((data: Alert[], message: LiveMessage) => {
      if (message.type === 'event.created') return data;
      const alert = message.data;
      const rows = data.filter(a => a.id !== alert.id);
      if (includeResolved || !['RESOLVED','FALSE_ALARM'].includes(alert.status)) rows.unshift(alert);
      return rows.sort((a,b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
    }, [includeResolved]));
