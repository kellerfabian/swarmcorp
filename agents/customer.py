"""SwarmCorp — Customer Agent"""
import json
from typing import Optional
import anthropic
from agents.base_agent import BaseAgent


class CustomerAgent(BaseAgent):
    def __init__(self, client: Optional[anthropic.Anthropic] = None, on_event=None):
        super().__init__(agent_id="customer", client=client, on_event=on_event)

    def evaluate_product(self, product: dict, marketing: dict, context: str) -> dict:
        return self.call(
            f"Produkt:\n{json.dumps(product, ensure_ascii=False)}\n\n"
            f"Marketing:\n{json.dumps(marketing, ensure_ascii=False)}\n\n"
            "Bewerte als Kunde. JSON mit: "
            "satisfaction_score (0.0-1.0), overall_assessment, "
            "strengths, weaknesses, suggestions, would_buy (bool)",
            context=context,
        )

    def evaluate_improvement(self, product: dict, previous_feedback: dict, marketing: dict, context: str) -> dict:
        return self.call(
            f"Verbessertes Produkt:\n{json.dumps(product, ensure_ascii=False)}\n\n"
            f"Vorheriges Feedback:\n{json.dumps(previous_feedback, ensure_ascii=False)}\n\n"
            f"Marketing:\n{json.dumps(marketing, ensure_ascii=False)}\n\n"
            "Bewerte die Verbesserungen. JSON mit: "
            "satisfaction_score (0.0-1.0), overall_assessment, "
            "improvements_noticed, remaining_issues, suggestions, would_buy (bool)",
            context=context,
        )
