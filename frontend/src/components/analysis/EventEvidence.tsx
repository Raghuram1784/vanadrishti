import { UncertaintyNotice, detectionLabel } from "./UncertaintyNotice";
import type { Event } from '@/types/api';
import { evidenceUrl } from '@/services/api';
import { DetectionImage } from './DetectionImage';

export function EventEvidence({ event }: { event: Event }) {
  return <section className="stored-evidence">
    <h3>Stored evidence</h3>
    {event.evidence_image_url ? <DetectionImage url={evidenceUrl(event.evidence_image_url)} detections={event.detections}/> : <div className="evidence-note">No stored image evidence for this event.</div>}
    <div className="observation-summary"><h3>Detections & species</h3>
      {!event.detections.length && <p>No retained detections.</p>}
      {event.detections.map((d, i) => <div key={i}><p><strong className="capitalize">{i+1}. {detectionLabel(d)}</strong> · Detector score: {d.score.toFixed(4)}</p>
        {d.uncertain && <UncertaintyNotice detection={d} />}
        {!d.uncertain && d.species && <><p>{d.species.top1} · Ranking score: {d.species.ranking_score.toFixed(4)}</p><ol className="species-ranks">{d.species.top3.map(s => <li key={s.label}><span>{s.label}</span><strong>{s.ranking_score.toFixed(4)}</strong></li>)}</ol></>}
      </div>)}
      {event.detections.some(d => d.species) && <p>Species values are model ranking scores, not calibrated probabilities.</p>}
    </div>
  </section>;
}
