import type { LiveFrameResponse } from '@/types/api';

export const FRAME_REQUEST_TIMEOUT_MS = 120000;
export interface FrameRequestOptions {
  signal?: AbortSignal;
  onUploaded?: () => void;
  onReceiving?: () => void;
}

/** XHR provides an actual upload-complete milestone; it does not imply inference started. */
export function uploadCameraFrame(url: string, form: FormData, options: FrameRequestOptions = {}, timeoutMs = FRAME_REQUEST_TIMEOUT_MS): Promise<LiveFrameResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = (error?: Error, result?: LiveFrameResponse) => {
      if (settled) return;
      settled = true; clearTimeout(timer); options.signal?.removeEventListener('abort', cancel);
      xhr.onload = xhr.onerror = xhr.onabort = xhr.ontimeout = null;
      xhr.upload.onload = null;
      if (error) reject(error); else resolve(result!);
    };
    const cancel = () => {
      finish(new DOMException('Frame request cancelled; server processing may still finish', 'AbortError'));
      xhr.abort();
    };
    options.signal?.addEventListener('abort', cancel, { once: true });
    if (options.signal?.aborted) { cancel(); return; }
    const timeout = () => {
      finish(new DOMException('Frame request exceeded 120 seconds. Server processing may still finish; check Events and backend status before resuming.', 'TimeoutError'));
      xhr.abort();
    };
    timer = setTimeout(timeout, timeoutMs);
    try {
      xhr.open('POST', url);
      xhr.timeout = timeoutMs;
      xhr.upload.onload = () => { if (!settled) options.onUploaded?.(); };
      xhr.onload = () => {
        if (settled) return;
        options.onReceiving?.();
        if (xhr.status < 200 || xhr.status >= 300) {
          finish(new Error(`Frame request failed (HTTP ${xhr.status}). Check backend status before resuming.`));
          return;
        }
        try { finish(undefined, JSON.parse(xhr.responseText) as LiveFrameResponse); }
        catch { finish(new Error('Backend returned an invalid frame response')); }
      };
      xhr.onerror = () => finish(new Error('Cannot reach the backend. Check FastAPI on port 8000 before resuming.'));
      xhr.onabort = () => finish(new DOMException('Frame request cancelled', 'AbortError'));
      xhr.ontimeout = timeout;
      xhr.send(form);
    } catch (error) { finish(error instanceof Error ? error : new Error('Frame upload failed')); }
  });
}
