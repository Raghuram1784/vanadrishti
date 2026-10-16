import { useState } from "react";
import { FlaskConical, Play, LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { getDemoScenarios, runDemoScenario } from "@/services/api";
import { usePolling, refreshData } from "@/hooks/usePolling";
import type { Event } from "@/types/api";
import { Button } from "@/components/ui/button";
import { ErrorBanner, RiskBadge } from "@/components/ui/shared";
import { ResultPanels } from "@/components/analysis/ResultPanels";
import { message } from "@/lib/utils";
export function DemoPanel() {
  const scenarios = usePolling(getDemoScenarios, 60000);
  const [busy, setBusy] = useState<string>();
  const [results, setResults] = useState<Event[]>();
  const [title, setTitle] = useState("");
  async function run(id: string, name: string) {
    setBusy(id);
    try {
      const response = await runDemoScenario(id);
      setResults(response.events);
      setTitle(name);
      refreshData();
      toast.success("Simulated scenario completed and saved.");
    } catch (error) {
      toast.error(message(error));
    } finally {
      setBusy(undefined);
    }
  }
  return (
    <section className="panel demo-panel">
      <div className="panel-heading">
        <div>
          <h2>
            <FlaskConical size={17} /> Demo scenarios
          </h2>
          <p>Explore the existing context and risk engine.</p>
        </div>
        <span className="subtle-badge">SIMULATED SCENARIOS</span>
      </div>
      <ErrorBanner text={scenarios.error} retry={scenarios.refresh} />
      <div className="scenario-list">
        {scenarios.loading && <p className="muted">Loading scenarios…</p>}
        {scenarios.data?.scenarios.map((scenario, i) => (
          <div className="scenario-row" key={scenario.scenario_id}>
            <span className="scenario-number">0{i + 1}</span>
            <div>
              <h3>{scenario.title}</h3>
              <span>
                Simulated scenario · expected{" "}
                {scenario.expected_risk_level.toLowerCase()} risk
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={!!busy}
              onClick={() => run(scenario.scenario_id, scenario.title)}
              aria-label={`Run scenario: ${scenario.title}`}
            >
              {busy === scenario.scenario_id ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <Play />
              )}
              Run scenario
            </Button>
          </div>
        ))}
      </div>
      {results && (
        <div className="demo-result">
          <div className="eyebrow">SIMULATED SCENARIO RESULT</div>
          <h3>{title}</h3>
          {results.map((event, i) => (
            <div key={event.event_id}>
              <div className="demo-event-heading">
                Event {i + 1} · {event.detections.map((d) => d.type).join(", ")}{" "}
                <RiskBadge level={event.risk.level} />
              </div>
              <ResultPanels event={event} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
