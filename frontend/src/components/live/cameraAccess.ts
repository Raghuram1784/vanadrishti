/** Laptop-only acquisition helpers. Device IDs remain in memory, never persisted. */
export function errorName(error: unknown): string {
  return typeof error === 'object' && error !== null && 'name' in error ? String(error.name) : 'Error';
}
export function cameraErrorMessage(error: unknown): string {
  switch (errorName(error)) {
    case 'NotAllowedError': return 'Camera permission was denied. Allow camera access for this site before trying again.';
    case 'NotFoundError': return 'No camera device was found by the browser.';
    case 'NotReadableError': return 'Camera exists but could not be opened. It may be in use by another application.';
    case 'OverconstrainedError': return 'The selected camera does not support the requested settings.';
    case 'AbortError': return 'Camera startup was interrupted. Try starting the camera again.';
    case 'SecurityError': return 'Browser security settings blocked camera access. Use localhost and check the site camera settings.';
    case 'TimeoutError': return 'The camera opened but did not provide a playable video frame. Stop and retry the camera.';
    default: return 'Camera startup failed. Review the failure stage and error name in Camera Diagnostics.';
  }
}
export function validDeviceId(devices: MediaDeviceInfo[], selected: string): string {
  return devices.some(device => device.kind === 'videoinput' && device.deviceId === selected) ? selected : '';
}
export async function listVideoInputs(media: Pick<MediaDevices, 'enumerateDevices'>) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const devices = await Promise.race([
      media.enumerateDevices(),
      new Promise<MediaDeviceInfo[]>((_, reject) => {
        timer = setTimeout(() => reject(new DOMException('Enumeration timed out', 'TimeoutError')), 8000);
      }),
    ]);
    return devices.filter(device => device.kind === 'videoinput');
  } finally { clearTimeout(timer); }
}
export async function openLaptopCamera(
  media: Pick<MediaDevices, 'getUserMedia'>,
  selected: string,
  attempt: (description: string) => void,
  signal: AbortSignal,
  preferredFacingMode?: 'user' | 'environment',
) {
  const open = async (video: boolean | MediaTrackConstraints) => {
    signal.throwIfAborted();
    const stream = await media.getUserMedia({ video, audio: false });
    if (signal.aborted) {
      stream.getTracks().forEach(track => track.stop());
      signal.throwIfAborted();
    }
    return stream;
  };
  if (selected) {
    attempt('Selected camera: exact deviceId; audio disabled');
    try { return await open({ deviceId: { exact: selected } }); }
    catch (error) {
      if (signal.aborted || !['NotFoundError', 'OverconstrainedError'].includes(errorName(error))) throw error;
      attempt(`Selected camera unavailable (${errorName(error)}); fallback: video=true; audio disabled`);
      return open(preferredFacingMode ? { facingMode: { ideal: preferredFacingMode } } : true);
    }
  }
  if (preferredFacingMode) {
    attempt(`Camera facing: ${preferredFacingMode}; audio disabled`);
    try {
      return await open({ facingMode: { ideal: preferredFacingMode } });
    } catch {
      attempt('Facing mode unavailable; fallback: video=true; audio disabled');
      return open(true);
    }
  }
  attempt('Default camera: video=true; audio disabled');
  return open(true);
}
export async function waitForPreview(video: HTMLVideoElement, stream: MediaStream, signal: AbortSignal) {
  video.srcObject = stream;
  await new Promise<void>((resolve, reject) => {
    let finished = false;
    const clean = () => {
      clearTimeout(timer); video.removeEventListener('loadedmetadata', ready);
      video.removeEventListener('loadeddata', ready); signal.removeEventListener('abort', cancel);
    };
    const finish = (error?: Error) => { if (finished) return; finished = true; clean(); error ? reject(error) : resolve(); };
    const ready = () => { if (video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= 2) finish(); };
    const cancel = () => finish(new DOMException('Cancelled', 'AbortError'));
    const timer = setTimeout(() => finish(new DOMException('Preview timeout', 'TimeoutError')), 15000);
    video.addEventListener('loadedmetadata', ready); video.addEventListener('loadeddata', ready);
    signal.addEventListener('abort', cancel, { once: true });
    if (signal.aborted) { cancel(); return; }
    void video.play().then(ready).catch(error => finish(error)); ready();
  });
}
export async function cameraPermission(): Promise<string> {
  try { return (await navigator.permissions.query({ name: 'camera' as PermissionName })).state; }
  catch { return 'unknown'; }
}
