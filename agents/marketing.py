"""SwarmCorp — Marketing Agent"""
import json
from typing import Optional
import anthropic
from agents.base_agent import BaseAgent


class MarketingAgent(BaseAgent):
    def __init__(self, client: Optional[anthropic.Anthropic] = None, on_event=None):
        super().__init__(agent_id="marketing", client=client, on_event=on_event)

    def research_market(self, context: str) -> dict:
        return self.call(
            "Fuehre eine gruendliche Marktrecherche durch. "
            "Nutze Web-Recherche um echte, aktuelle Daten zu finden: "
            "reale Wettbewerber, aktuelle Marktgroessen, neueste Trends. "
            "JSON mit: target_market, market_size, competitors, trends, "
            "opportunities, risks, recommendation, sources (Liste der genutzten Quellen-URLs)",
            context=context,
        )

    def develop_positioning(self, strategy: dict, context: str) -> dict:
        return self.call(
            f"Strategie:\n{json.dumps(strategy, ensure_ascii=False)}\n\n"
            "Entwickle Marketing-Positionierung. Recherchiere aktuelle "
            "Wettbewerber-Positionierungen und Marketing-Trends im Zielmarkt. "
            "JSON mit: value_proposition, tagline, target_audience, channels, "
            "messaging, differentiation",
            context=context,
        )

    def refine_from_feedback(self, feedback: dict, tasks: list, context: str) -> dict:
        return self.call(
            f"Kundenfeedback:\n{json.dumps(feedback, ensure_ascii=False)}\n\n"
            f"Aufgaben:\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
            "Verfeinere die Marketing-Strategie basierend auf dem Feedback. JSON mit: "
            "value_proposition, tagline, adjustments, channels, messaging",
            context=context,
        )
