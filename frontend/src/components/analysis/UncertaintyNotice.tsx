import type { Detection } from '@/types/api';
export function detectionLabel(d: Detection) {
  return d.uncertain ? (d.candidate_signals?.length ? 'Ambiguous object' : `Possible ${d.type}`) : d.type;
}
export function UncertaintyNotice({ detection: d }: { detection: Detection }) {
  return <div role="status" className="uncertainty-notice">
    <strong>Uncertain Detection</strong>
    <p>Species: Not classified</p>
    <p>{d.uncertainty_reason}</p>
    {!!d.candidate_signals?.length && <p>Candidate signals: {d.candidate_signals.map(c => `${c.type}: ${c.score.toFixed(4)}`).join(' · ')}</p>}
    <p>Additional observation recommended.</p>
  </div>;
}
