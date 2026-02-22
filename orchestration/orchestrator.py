"""
SwarmCorp — Orchestrator
Phased simulation loop: Strategy → Build → Review → Adjust
"""
import json, os
from datetime import datetime
import anthropic

from config import ANTHROPIC_API_KEY, MAX_ITERATIONS, TARGET_SATISFACTION, MEMORY_ROOT, TokenUsage
from state import CompanyState
from agents import CEOAgent, MarketingAgent, DeveloperAgent, CustomerAgent


class SwarmCorpOrchestrator:
    def __init__(self, idea: str = ""):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.state = CompanyState(
            started_at=datetime.now().isoformat(),
            industry=idea,
        )
        self.ceo = CEOAgent(client=self.client)
        self.marketing = MarketingAgent(client=self.client)
        self.developer = DeveloperAgent(client=self.client)
        self.customer = CustomerAgent(client=self.client)
        self.agents = [self.ceo, self.marketing, self.developer, self.customer]

    def run(self) -> CompanyState:
        self._header("SWARMCORP SIMULATION GESTARTET")

        # Phase 0: Market Research
        self._phase("Phase 0: Marktrecherche", "📊")
        market_data = self.marketing.research_market(self.state.get_context_summary())
        self.state.marketing = market_data
        self.state.log_message("marketing", "research", json.dumps(market_data, ensure_ascii=False)[:300])
        self._preview("Marketing", market_data)

        # Phase 1: Initial Strategy
        self._phase("Phase 1: CEO definiert Strategie", "🎯")
        strategy = self.ceo.set_initial_strategy(market_data, self.state.get_context_summary())
        self.state.strategy = strategy
        self.state.business_model = strategy.get("business_model", "TBD")
        self.state.company_name = strategy.get("company_name", "SwarmCorp Venture")
        self.state.log_message("ceo", "strategy", json.dumps(strategy, ensure_ascii=False)[:300])
        self._preview("CEO", strategy)

        # Iteration Loop
        for i in range(MAX_ITERATIONS):
            self.state.iteration = i + 1
            self._header(f"ITERATION {i+1}/{MAX_ITERATIONS}")
            if self._iterate(i) == "ship":
                break

        # Final Report
        self._header("FINALER BERICHT")
        final = self.ceo.final_report(self.state.get_context_summary())
        self.state.log_message("ceo", "final_report", json.dumps(final, ensure_ascii=False)[:500])
        self._preview("CEO", final)

        self._save()
        self._costs()
        return self.state

    def _iterate(self, i: int) -> str:
        ctx = self.state.get_context_summary
        tasks = self.state.strategy.get("tasks", [])

        # Developer
        self._phase("Development", "💻")
        if i == 0:
            dev = self.developer.build_mvp(self.state.strategy, self.state.get_context_summary())
        else:
            dev = self.developer.improve_from_feedback(
                self.state.feedback_history[-1] if self.state.feedback_history else {},
                tasks,
                self.state.products[-1] if self.state.products else {},
                self.state.get_context_summary(),
            )
        self.state.products.append(dev)
        self.state.log_message("developer", "build", json.dumps(dev, ensure_ascii=False)[:300])
        self._preview("Developer", dev)

        # Marketing
        self._phase("Marketing", "📢")
        if i == 0:
            mkt = self.marketing.develop_positioning(self.state.strategy, self.state.get_context_summary())
        else:
            mkt = self.marketing.refine_from_feedback(
                self.state.feedback_history[-1] if self.state.feedback_history else {},
                tasks,
                self.state.get_context_summary(),
            )
        self.state.marketing = mkt
        self.state.log_message("marketing", "positioning", json.dumps(mkt, ensure_ascii=False)[:300])
        self._preview("Marketing", mkt)

        # Customer Review
        self._phase("Kundenbewertung", "👤")
        if i == 0:
            fb = self.customer.evaluate_product(dev, mkt, self.state.get_context_summary())
        else:
            fb = self.customer.evaluate_improvement(
                dev, self.state.feedback_history[-1], mkt, self.state.get_context_summary(),
            )
        self.state.feedback_history.append(fb)
        self.state.log_message("customer", "feedback", json.dumps(fb, ensure_ascii=False)[:300])
        self._preview("Customer", fb)

        score = fb.get("satisfaction_score", 0)
        print(f"\n  📈 Zufriedenheit: {score}")

        if score >= TARGET_SATISFACTION:
            print(f"  ✅ Ziel erreicht! (≥ {TARGET_SATISFACTION})")
            return "ship"

        # CEO Review
        self._phase("CEO Review", "👔")
        decision = self.ceo.review_and_adjust(dev, mkt, fb, self.state.get_context_summary())
        self.state.strategy = decision
        self.state.log_message("ceo", "review", json.dumps(decision, ensure_ascii=False)[:300])
        self._preview("CEO", decision)

        self.state.save(os.path.join(MEMORY_ROOT, f"checkpoint_{i}.json"))
        self.state.save_memory(MEMORY_ROOT)

        return decision.get("decision", "iterate")

    def _save(self):
        self.state.total_cost = sum(a.total_usage.cost(a.model) for a in self.agents)
        self.state.save(os.path.join(MEMORY_ROOT, "final_state.json"))
        self.state.save_memory(MEMORY_ROOT)
        log_path = os.path.join(MEMORY_ROOT, "conversation_log.json")
        with open(log_path, "w") as f:
            json.dump(self.state.conversation_log, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 Gespeichert: {MEMORY_ROOT}/")

    def _costs(self):
        self._header("KOSTEN")
        total = 0
        for a in self.agents:
            c = a.total_usage.cost(a.model)
            total += c
            print(f"  {a.agent_id:12s} {a.total_usage.input_tokens:>8,} in + {a.total_usage.output_tokens:>8,} out = ${c:.4f}")
        print(f"  {'─'*50}")
        print(f"  {'TOTAL':12s} ${total:.4f}")

    def _preview(self, agent: str, data: dict):
        keys = ["strategy_summary", "business_model", "decision", "satisfaction_score",
                "recommendation", "overall_assessment", "value_proposition", "tagline",
                "feasibility", "target_market", "tech_stack", "company_name"]
        lines = []
        for k in keys:
            v = self._deep(data, k)
            if v is not None:
                lines.append(f"    {k}: {str(v)[:120]}")
        if lines:
            print(f"\n  📄 [{agent}]")
            for l in lines[:5]:
                print(l)

    def _deep(self, d: dict, key: str):
        if key in d:
            return d[key]
        for v in d.values():
            if isinstance(v, dict):
                r = self._deep(v, key)
                if r is not None:
                    return r
        return None

    @staticmethod
    def _header(text: str):
        print(f"\n{'='*60}\n🐝 {text}\n{'='*60}")

    @staticmethod
    def _phase(text: str, emoji: str = ""):
        print(f"\n{emoji} {text}...")
