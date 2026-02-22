"""SwarmCorp — Developer Agent"""
import json
from typing import Optional
import anthropic
from agents.base_agent import BaseAgent


class DeveloperAgent(BaseAgent):
    def __init__(self, client: Optional[anthropic.Anthropic] = None):
        super().__init__(agent_id="developer", client=client)

    def build_mvp(self, strategy: dict, context: str) -> dict:
        return self.call(
            f"Strategie:\n{json.dumps(strategy, ensure_ascii=False)}\n\n"
            "Baue ein MVP. JSON mit: "
            "product_name, tech_stack, features (Liste), architecture, "
            "feasibility, timeline, risks",
            context=context,
        )

    def improve_from_feedback(self, feedback: dict, tasks: list, product: dict, context: str) -> dict:
        return self.call(
            f"Aktuelles Produkt:\n{json.dumps(product, ensure_ascii=False)}\n\n"
            f"Kundenfeedback:\n{json.dumps(feedback, ensure_ascii=False)}\n\n"
            f"Aufgaben:\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
            "Verbessere das Produkt basierend auf Feedback. JSON mit: "
            "product_name, improvements, tech_stack, features, feasibility, risks",
            context=context,
        )
