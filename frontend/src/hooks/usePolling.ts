import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { message } from "@/lib/utils";
import type { LiveMessage } from '@/types/api';
export function refreshData() {
  window.dispatchEvent(new Event("vanadrishti:refresh"));
}
export function usePolling<T>(loader: () => Promise<T>, interval = 15000,
  reduceLive?: (data: T, message: LiveMessage) => T) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date>();
  const generation = useRef(0);
  const lastError = useRef("");
  const currentData = useRef<T | undefined>(undefined);
  currentData.current = data;
  const refresh = useCallback(async () => {
    const current = ++generation.current;
    try {
      const value = await loader();
      if (current !== generation.current) return;
      setData(value);
      setError(undefined);
      setUpdatedAt(new Date());
      lastError.current = "";
    } catch (e) {
      if (current !== generation.current) return;
      const text = message(e);
      setError(text);
      if (text !== lastError.current)
        toast.error(text, { id: "connection-error" });
      lastError.current = text;
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [loader]);
  useEffect(() => {
    setData(undefined);
    setLoading(true);
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, interval);
    const handler = () => {
      void refresh();
    };
    window.addEventListener("vanadrishti:refresh", handler);
    return () => {
      clearInterval(timer);
      window.removeEventListener("vanadrishti:refresh", handler);
      generation.current++;
    };
  }, [refresh, interval]);
  useEffect(() => {
    if (!reduceLive) return;
    const handler = (event: globalThis.Event) => {
      const message = (event as CustomEvent<LiveMessage>).detail;
      if (currentData.current === undefined) { void refresh(); return; }
      generation.current++;
      setData(value => value === undefined ? value : reduceLive(value, message));
      setLoading(false);
    };
    window.addEventListener('vanadrishti:live', handler);
    return () => window.removeEventListener('vanadrishti:live', handler);
  }, [reduceLive, refresh]);
  return { data, error, loading, refresh, updatedAt };
}
