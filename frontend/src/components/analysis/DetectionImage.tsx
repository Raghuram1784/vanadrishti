import { detectionLabel } from "./UncertaintyNotice";
import type { Detection } from "@/types/api";
import { useEffect, useState } from 'react';
export function DetectionImage({
  url,
  detections,
}: {
  url: string;
  detections: Detection[];
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  if (failed) return <div className="evidence-note">Stored image could not be loaded. Check the backend connection or select another event.</div>;
  return (
    <div className="image-stage">
      <div className="image-coordinate-space">
        <img src={url} alt="Forest image evidence with detection overlays" onError={() => setFailed(true)} />
        {detections.map(
          (d, i) =>
            d.bbox && (
              <div
                key={i}
                className={`detection-box box-${d.type}`}
                style={{
                  left: `${d.bbox[0] * 100}%`,
                  top: `${d.bbox[1] * 100}%`,
                  width: `${(d.bbox[2] - d.bbox[0]) * 100}%`,
                  height: `${(d.bbox[3] - d.bbox[1]) * 100}%`,
                }}
                aria-label={`${d.type} detection ${i + 1}`}
              >
                <span className="box-label">
                  {i + 1} · {detectionLabel(d)}
                  {!d.uncertain && d.species ? ` · ${d.species.top1}` : ""}
                </span>
              </div>
            ),
        )}
      </div>
    </div>
  );
}
