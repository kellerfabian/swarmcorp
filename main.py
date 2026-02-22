#!/usr/bin/env python3
"""
🐝 SwarmCorp — Multi-Agent KI-Firma Simulation

Usage:
    cp .env.example .env   # API-Key eintragen
    uv run main.py                              # Volle Simulation
    uv run main.py --discuss "Thema"            # Schnelle Agent-Diskussion
"""
import sys, os, json, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from config import ANTHROPIC_API_KEY


def run_discussion(topic: str):
    """All agents discuss a topic, CEO synthesizes."""
    import anthropic
    from agents import CEOAgent, MarketingAgent, DeveloperAgent, CustomerAgent

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    agents = {
        "ceo": CEOAgent(client=client),
        "marketing": MarketingAgent(client=client),
        "developer": DeveloperAgent(client=client),
        "customer": CustomerAgent(client=client),
    }

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
        print(f"  → {str(result.get('recommendation', result.get('perspective', '')))[:150]}")

    print(f"\n👔 CEO Synthese...")
    synthesis = agents["ceo"].call(
        f"Team-Perspektiven zu '{topic}':\n"
        f"{json.dumps(perspectives, ensure_ascii=False, indent=2)}\n\n"
        f"Synthetisiere zu einer Entscheidung. Welche Perspektive überzeugt?",
    )

    print(f"\n{'='*60}\n📋 ENTSCHEIDUNG:\n{json.dumps(synthesis, ensure_ascii=False, indent=2)[:1000]}\n{'='*60}")
    total = sum(a.total_usage.cost(a.model) for a in agents.values())
    print(f"\n💰 Kosten: ${total:.4f}")


def run_simulation():
    """Full company simulation with feedback loops."""
    from orchestration import SwarmCorpOrchestrator

    orch = SwarmCorpOrchestrator()
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
    parser.add_argument("--discuss", type=str, help="Schnelle Agent-Diskussion")
    args = parser.parse_args()

    if args.discuss:
        run_discussion(args.discuss)
    else:
        run_simulation()
