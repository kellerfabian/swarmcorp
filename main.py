#!/usr/bin/env python3
"""
🐝 SwarmCorp — Multi-Agent KI-Firma Simulation

Usage:
    cp .env.example .env   # API-Key eintragen
    uv run main.py --idea "Geschäftsidee"       # Simulation mit Idee
    uv run main.py --discuss "Thema"            # Schnelle Agent-Diskussion
    uv run main.py                              # Simulation ohne Vorgabe
"""
import sys, os, json, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from config import ANTHROPIC_API_KEY


def run_discussion(topic: str):
    """All agents discuss a topic, CEO synthesizes. Persists to memory + workspace."""
    import anthropic
    from datetime import datetime
    from agents import CEOAgent, MarketingAgent, DeveloperAgent, CustomerAgent
    from config import MEMORY_ROOT, WORKSPACE_ROOT
    from state import CompanyState

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    agents = {
        "ceo": CEOAgent(client=client),
        "marketing": MarketingAgent(client=client),
        "developer": DeveloperAgent(client=client),
        "customer": CustomerAgent(client=client),
    }

    state = CompanyState(started_at=datetime.now().isoformat())

    print(f"\n{'='*60}\n🐝 SWARMCORP DISKUSSION: {topic}\n{'='*60}")

    perspectives = {}
    for name, agent in agents.items():
        print(f"\n🎙️  {name.upper()}...")
        result = agent.call(
            f"Thema: {topic}\n\n"
            f"Deine Einschätzung als {name}: Chancen, Risiken, Empfehlung. "
            f"JSON mit: perspective, opportunities, risks, recommendation",
            temperature=0.8,
        )
        perspectives[name] = result
        state.log_message(name, "perspective", json.dumps(result, ensure_ascii=False)[:500])
        print(f"  → {str(result.get('recommendation', result.get('perspective', '')))[:150]}")

    print(f"\n👔 CEO Synthese...")
    synthesis = agents["ceo"].call(
        f"Team-Perspektiven zu '{topic}':\n"
        f"{json.dumps(perspectives, ensure_ascii=False, indent=2)}\n\n"
        f"Synthetisiere zu einer Entscheidung. Welche Perspektive überzeugt?",
    )
    state.log_message("ceo", "synthesis", json.dumps(synthesis, ensure_ascii=False)[:500])

    print(f"\n{'='*60}\n📋 ENTSCHEIDUNG:\n{json.dumps(synthesis, ensure_ascii=False, indent=2)[:1000]}\n{'='*60}")
    total = sum(a.total_usage.cost(a.model) for a in agents.values())
    print(f"\n💰 Kosten: ${total:.4f}")

    # Persist to memory + workspace
    state.total_cost = total
    state.strategy = synthesis
    state.industry = topic

    # Save discussion to workspace
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    discussion_file = os.path.join(WORKSPACE_ROOT, f"discussion_{timestamp}.json")
    discussion_data = {
        "topic": topic,
        "timestamp": datetime.now().isoformat(),
        "perspectives": perspectives,
        "synthesis": synthesis,
        "cost": total,
    }
    with open(discussion_file, "w", encoding="utf-8") as f:
        json.dump(discussion_data, f, ensure_ascii=False, indent=2)

    # Save state checkpoint + memory
    state.save(os.path.join(MEMORY_ROOT, f"discussion_{timestamp}.json"))
    state.save_memory(MEMORY_ROOT)

    print(f"\n  💾 Gespeichert: {discussion_file}")
    print(f"  💾 Memory: {MEMORY_ROOT}/")


def run_simulation(idea: str = ""):
    """Full company simulation with feedback loops."""
    from orchestration import SwarmCorpOrchestrator

    orch = SwarmCorpOrchestrator(idea=idea)
    state = orch.run()

    print(f"\n{'='*60}\n🎉 SIMULATION ABGESCHLOSSEN\n{'='*60}")
    print(f"  Firma: {state.company_name}")
    print(f"  Iterationen: {state.iteration}")
    if state.feedback_history:
        print(f"  Finale Zufriedenheit: {state.feedback_history[-1].get('satisfaction_score', '?')}")
    print(f"  Kosten: ${state.total_cost:.4f}")


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY fehlt — cp .env.example .env und Key eintragen")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="SwarmCorp")
    parser.add_argument("--idea", type=str, help="Geschäftsidee als Startpunkt")
    parser.add_argument("--discuss", type=str, help="Schnelle Agent-Diskussion")
    args = parser.parse_args()

    if args.discuss:
        run_discussion(args.discuss)
    else:
        run_simulation(idea=args.idea or "")
