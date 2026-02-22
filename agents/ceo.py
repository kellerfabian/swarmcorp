"""SwarmCorp — CEO Agent"""
import json
from typing import Optional
import anthropic
from agents.base_agent import BaseAgent


class CEOAgent(BaseAgent):
    def __init__(self, client: Optional[anthropic.Anthropic] = None):
        super().__init__(agent_id="ceo", client=client)

    def set_initial_strategy(self, market_data: dict, context: str) -> dict:
        return self.call(
            f"Marktdaten:\n{json.dumps(market_data, ensure_ascii=False)}\n\n"
            "Definiere eine Unternehmensstrategie. JSON mit: "
            "company_name, business_model, strategy_summary, target_market, "
            "competitive_advantage, tasks (Liste konkreter Aufgaben), revenue_model",
            context=context,
        )

    def review_and_adjust(self, dev: dict, mkt: dict, feedback: dict, context: str) -> dict:
        return self.call(
            f"Development:\n{json.dumps(dev, ensure_ascii=False)}\n\n"
            f"Marketing:\n{json.dumps(mkt, ensure_ascii=False)}\n\n"
            f"Kundenfeedback:\n{json.dumps(feedback, ensure_ascii=False)}\n\n"
            "Bewerte den Fortschritt und entscheide: iterate, pivot, oder ship. "
            "JSON mit: decision, strategy_summary, tasks, adjustments, reasoning",
            context=context,
        )

    def final_report(self, context: str) -> dict:
        return self.call(
            "Erstelle den finalen Unternehmensbericht. JSON mit: "
            "company_name, business_model, achievements, lessons_learned, "
            "next_steps, overall_assessment",
            context=context,
        )
