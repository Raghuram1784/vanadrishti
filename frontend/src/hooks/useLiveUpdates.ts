import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { liveUrl } from '@/services/api';
import { refreshData } from './usePolling';
import type { LiveMessage } from '@/types/api';

export function useLiveUpdates() {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;
    let attempt = 0;
    let lastReceived = Date.now();
    const seenAlerts = new Set<string>();
    function connect() {
      if (stopped) return;
      socket = new WebSocket(liveUrl());
      socket.onmessage = event => {
        if (stopped) return;
        lastReceived = Date.now();
        try {
          const value = JSON.parse(event.data);
          if (value.type === 'connection.ready') {
            attempt = 0; setConnected(true);
            // One REST resync on each connection, including after missed updates.
            refreshData();
            heartbeat = setInterval(() => {
              if (Date.now() - lastReceived > 65000) socket?.close();
              else if (socket?.readyState === WebSocket.OPEN) socket.send('ping');
            }, 20000);
            return;
          }
          if (!['event.created', 'alert.created', 'alert.updated'].includes(value.type) || !value.data) return;
          const message = value as LiveMessage;
          window.dispatchEvent(new CustomEvent<LiveMessage>('vanadrishti:live', { detail: message }));
          if (message.type === 'alert.created' && !seenAlerts.has(message.data.id)) {
            seenAlerts.add(message.data.id);
            if (seenAlerts.size > 200) seenAlerts.delete(seenAlerts.values().next().value!);
            toast.info(`New ${message.data.risk_level} wildlife-security event received${message.data.source === 'demo' ? ' · Simulated scenario' : ''}`);
          }
        } catch { /* Ignore malformed notifications; REST polling remains active. */ }
      };
      socket.onclose = () => {
        clearInterval(heartbeat);
        if (stopped) return;
        setConnected(false);
        const delay = Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)) + Math.random() * 500;
        retry = setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
    }
    connect();
    return () => { stopped = true; clearTimeout(retry); clearInterval(heartbeat); socket?.close(); };
  }, []);
  return connected;
}
