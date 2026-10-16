"""
VanaDrishti Phase 3: Risk Engine Interactive Scenario Demonstrator.

Executes deterministic forest surveillance scenarios and outputs explainable
ranger-security decision-support assessments.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.context import ContextEngine, RiskEngine, WildlifeEvent


def load_scenario(scenario_path: Path) -> Dict[str, Any]:
    """Load scenario definition from JSON file."""
    with open(scenario_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_scenario(
    scenario_path: Path,
    risk_engine: RiskEngine,
) -> List[Dict[str, Any]]:
    """Execute scenario events through the RiskEngine."""
    data = load_scenario(scenario_path)
    title = data.get("title", scenario_path.stem)
    events_data = data.get("events", [])

    print("\n" + "=" * 65)
    print(f"SCENARIO: {title}")
    print(f"File: {scenario_path.name}")
    print(f"Description: {data.get('description', '')}")
    print("=" * 65)

    assessments = []

    for idx, e_dict in enumerate(events_data, 1):
        event = WildlifeEvent.from_dict(e_dict)
        cam = risk_engine.context.cameras.get(event.camera_id)
        zone_str = (event.zone_type or (cam.zone_type if cam else "BUFFER")).upper()

        assessment = risk_engine.evaluate(event, camera=cam)
        assessments.append(assessment.to_dict())

        # Format output
        time_str = event.timestamp.strftime("%H:%M")
        patrol_str = "Yes" if event.patrol_authorized or (cam and cam.patrol_authorized) else "No"

        print(f"\n--- Event {idx}/{len(events_data)}: [{event.event_id}] ---")
        print("VanaDrishti Risk Assessment")
        print("-" * 35)
        print(f"Camera:            {event.camera_id} ({cam.name if cam else 'Unknown'})")
        print(f"Object:            {event.object_type}")
        if event.species:
            print(f"Species:           {event.species} (score={event.species_score:.2f})")
        print(f"Zone:              {zone_str}")
        print(f"Time:              {time_str}")
        print(f"Patrol authorized: {patrol_str}")
        print(f"\nRisk Score:        {assessment.risk_score} / 100")
        print(f"Risk Level:        {assessment.risk_level}")
        print(f"Alert Generated:   {'YES' if assessment.alert else 'NO'}")
        print("\nReasons:")
        for r in assessment.reasons:
            print(f"  - {r}")
        print(f"\nRecommended Action:\n  {assessment.recommended_action}")

    print("\n" + "-" * 65)
    return assessments


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 3: Security Risk Engine Demonstration"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="all",
        help="Scenario name or filename (e.g., scenario_02_person_core_night), or 'all'",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default="data/demo/scenarios",
        help="Directory containing scenario JSON files",
    )

    args = parser.parse_args()

    scenarios_dir = Path(args.scenarios_dir)
    if not scenarios_dir.is_absolute():
        scenarios_dir = PROJECT_ROOT / scenarios_dir

    if not scenarios_dir.exists():
        print(f"Scenarios directory not found: {scenarios_dir}")
        sys.exit(1)

    # Initialize Context and Risk Engine
    context_engine = ContextEngine.create_default(PROJECT_ROOT / "config")
    risk_engine = RiskEngine(context_engine=context_engine)

    scenario_files: List[Path] = []
    if args.scenario.lower() == "all":
        scenario_files = sorted(scenarios_dir.glob("scenario_*.json"))
    else:
        name = args.scenario
        if not name.endswith(".json"):
            name = f"{name}.json"
        p = scenarios_dir / name
        if not p.exists():
            # Try searching
            matches = list(scenarios_dir.glob(f"*{args.scenario}*.json"))
            if matches:
                p = matches[0]
        if not p.exists():
            print(f"Scenario file not found: {args.scenario}")
            sys.exit(1)
        scenario_files = [p]

    for sf in scenario_files:
        # Re-initialize context engine for isolated scenario testing
        context_engine = ContextEngine.create_default(PROJECT_ROOT / "config")
        engine = RiskEngine(context_engine=context_engine)
        run_scenario(sf, engine)


if __name__ == "__main__":
    main()
