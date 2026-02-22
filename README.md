# 🐝 SwarmCorp

Multi-Agent KI-Firma Simulation — CEO, Marketing, Developer und Customer Bots diskutieren, entwickeln Software und iterieren basierend auf Kundenfeedback.

## Architektur

Kombiniert Patterns aus **OpenClaw** (SOUL.md, Workspace-Isolation, Markdown-Memory), **Claude Agent SDK** (Orchestrator-Worker, Model-per-Role), und **MetaGPT/ChatDev** (JSON-Artefakte, Self-Review, Phased Pipeline).

```
                    ┌─────────────────────────────┐
                    │      SHARED STATE            │
                    │  strategy · products · feedback│
                    │  + MEMORY.md persistence      │
                    └──┬──────┬────────┬────────┬──┘
                       │      │        │        │
                 ┌─────▼──┐ ┌─▼──────┐ ┌▼──────┐ ┌▼────────┐
                 │  CEO   │ │Marketing│ │  Dev  │ │Customer │
                 │Sonnet  │ │ Sonnet  │ │Sonnet │ │ Haiku   │
                 │SOUL.md │ │SOUL.md  │ │SOUL.md│ │SOUL.md  │
                 └────────┘ └─────────┘ └───────┘ └─────────┘
```

## Ablauf

```
Phase 0  Marketing → Marktrecherche
Phase 1  CEO → Strategie + Tasks
         ┌──────────────────────────────┐
    ╭───▶│  Phase 2  Dev → Code/MVP     │
    │    │           Marketing → Position│
    │    │  Phase 3  Customer → Feedback │
    │    │  Phase 4  CEO → Entscheid     │
    │    └──────────────┬───────────────┘
    │         iterate ◄─┤
    │                   ├─► pivot (neue Richtung)
    ╰───────────────────┘
                        └─► ship  (Release!)
         Exit: score ≥ 0.85 | max_iter | ship
```

## Quick Start

```bash
cp .env.example .env          # API-Key eintragen
uv run main.py                                  # Volle Simulation
uv run main.py --discuss "KI-Tool für Lehrer?"  # Schnelle Diskussion
```

## Projektstruktur

```
swarmcorp/
├── main.py                     # Entry Point
├── config.py                   # Models, Kosten, Parameter
├── state.py                    # Shared State + Memory
├── agents/
│   ├── base_agent.py           # SOUL.md Loader + Claude API
│   ├── ceo.py                  # Strategie & Delegation
│   ├── marketing.py            # Marktanalyse
│   ├── developer.py            # Code + Self-Review Loop
│   └── customer.py             # Produkt-Bewertung
├── orchestration/
│   └── orchestrator.py         # Phasen-Loop
├── workspace/                  # Agent-Persönlichkeiten
│   ├── ceo/SOUL.md
│   ├── marketing/SOUL.md
│   ├── developer/SOUL.md
│   └── customer/SOUL.md
└── memory/                     # Persistente Ergebnisse
```

## Kosten

| Modus | ~Kosten |
|-------|---------|
| `--discuss` (1 Runde) | ~$0.05 |
| Simulation (3 Iterationen) | ~$0.30–0.50 |
| Simulation (5 Iterationen) | ~$0.50–1.00 |

## Anpassen

- **Persönlichkeit:** `workspace/<agent>/SOUL.md` editieren
- **Skills:** Markdown in `workspace/<agent>/skills/` ablegen
- **Modelle:** `MODELS` dict in `config.py` ändern
- **Parameter:** `MAX_ITERATIONS`, `TARGET_SATISFACTION` in `config.py`
