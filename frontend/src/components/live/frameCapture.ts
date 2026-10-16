/** One bounded JPEG operation. Late callbacks cannot settle a cancelled sample. */
export const ENCODE_TIMEOUT_MS = 5000;
export function encodeJpeg(canvas: HTMLCanvasElement, signal: AbortSignal, timeoutMs = ENCODE_TIMEOUT_MS): Promise<Blob> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = (error?: Error, blob?: Blob) => {
      if (settled) return;
      settled = true; clearTimeout(timer); signal.removeEventListener('abort', cancel);
      if (error) reject(error); else resolve(blob!);
    };
    const cancel = () => finish(new DOMException('Sample cancelled', 'AbortError'));
    signal.addEventListener('abort', cancel, { once: true });
    if (signal.aborted) { cancel(); return; }
    timer = setTimeout(() => finish(new DOMException('JPEG encoding did not complete within 5 seconds', 'TimeoutError')), timeoutMs);
    try {
      canvas.toBlob(blob => blob && blob.size > 0
        ? finish(undefined, blob)
        : finish(new Error('JPEG encoder returned an empty image')), 'image/jpeg', .82);
    } catch (error) { finish(error instanceof Error ? error : new Error('JPEG encoding failed')); }
  });
}
