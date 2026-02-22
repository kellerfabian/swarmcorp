# SwarmCorp - CLAUDE.md

## Project Overview

SwarmCorp is a multi-agent AI company simulation. Four specialized Claude-powered agents (CEO, Marketing, Developer, Customer) collaborate through a phased pipeline to develop business strategies, build products, and iterate based on customer feedback.

## Tech Stack

- **Language:** Python 3.11+
- **Package manager:** uv (use `uv run` to execute)
- **LLM:** Anthropic Claude API (`anthropic` SDK)
- **Config:** python-dotenv (`.env` file for `ANTHROPIC_API_KEY`)
- **No web framework** — CLI-only application

## Project Structure

```
swarmcorp/
├── main.py                  # Entry point: --discuss (quick) or full simulation
├── config.py                # Models, pricing, parameters, TokenUsage dataclass
├── state.py                 # CompanyState — shared state + memory persistence
├── agents/
│   ├── __init__.py          # Re-exports all agent classes
│   ├── base_agent.py        # BaseAgent: SOUL.md loader, Claude API call, JSON parser
│   ├── ceo.py               # CEOAgent: strategy, review, final report
│   ├── marketing.py         # MarketingAgent: market research, positioning, refinement
│   ├── developer.py         # DeveloperAgent: MVP build, improvement from feedback
│   └── customer.py          # CustomerAgent: product evaluation, improvement scoring
├── orchestration/
│   ├── __init__.py          # Re-exports SwarmCorpOrchestrator
│   └── orchestrator.py      # Phased simulation loop (Strategy → Build → Review → Adjust)
├── workspace/               # Agent personalities (SOUL.md files, skills/) — currently empty
├── memory/                  # Persistent state checkpoints + daily markdown memories
├── pyproject.toml           # uv project definition
└── uv.lock                  # Locked dependencies
```

## Key Architecture Decisions

- **All agent responses are JSON.** Agents are instructed to return only valid JSON. `BaseAgent._parse_json()` handles extraction robustly (direct parse → code block → regex).
- **SOUL.md personality system.** Each agent loads `workspace/<agent_id>/SOUL.md` as its system prompt base. Skills are loaded from `workspace/<agent_id>/skills/*.md`.
- **Shared state.** `CompanyState` (dataclass) is the single source of truth, passed as context summaries to agent prompts.
- **Web search.** Marketing and CEO agents use Anthropic's built-in `web_search_20250305` server tool. Controlled by `WEB_SEARCH_ENABLED` and `WEB_SEARCH_AGENTS` in config.
- **Model routing.** Each agent role maps to a model in `config.MODELS` — CEO/Marketing/Developer use Sonnet, Customer uses Haiku.
- **Token cost tracking.** `TokenUsage` dataclass tracks input/output tokens per agent. Pricing defined in `config.PRICING`.

## Common Commands

```bash
# Run a quick multi-agent discussion (~$0.05)
uv run main.py --discuss "topic"

# Run full simulation loop (~$0.30–1.00)
uv run main.py

# Install dependencies
uv sync
```

## Conventions

- **Language:** Code is in English, prompts and UI output are in German.
- **Imports:** Lazy imports inside functions in `main.py` to keep startup fast.
- **Agent pattern:** All agents extend `BaseAgent`. Constructor takes optional `anthropic.Anthropic` client. Domain methods call `self.call()` with a prompt and return `dict`.
- **State persistence:** Checkpoints saved as JSON in `memory/`. Daily markdown summaries appended to `memory/YYYY-MM-DD.md`.
- **No tests exist yet.** The project has no test suite.

## Important Notes

- Never commit `.env` — it contains the Anthropic API key.
- `memory/*.json` and `memory/*.md` are gitignored (generated output).
- The `workspace/` directory exists but has no SOUL.md files yet — agents work without them (empty string system prompt prefix).
- `SwarmCorpOrchestrator.__init__` does not accept an `idea` parameter currently, but `main.py` passes one — this is a known inconsistency.
