"""
SwarmCorp — Shared Company State
OpenClaw-inspired MEMORY.md persistence + session state.
"""
import json, os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class CompanyState:
    """Shared state all agents read/write."""

    company_name: str = ""
    industry: str = ""
    business_model: str = ""
    strategy: dict = field(default_factory=dict)
    products: list = field(default_factory=list)
    marketing: dict = field(default_factory=dict)
    feedback_history: list = field(default_factory=list)
    conversation_log: list = field(default_factory=list)
    iteration: int = 0
    total_cost: float = 0.0
    started_at: str = ""
    last_updated: str = ""

    def log_message(self, agent: str, role: str, content: str):
        self.conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "role": role,
            "content": content[:500],
        })

    def get_context_summary(self) -> str:
        """Compact context for agent prompts (OpenClaw-style compaction)."""
        lines = [f"## SwarmCorp Status — Iteration {self.iteration}"]
        if self.industry:
            lines.append(f"- Geschäftsidee: {self.industry}")
        if self.company_name:
            lines.append(f"- Firma: {self.company_name}")
        if self.business_model:
            lines.append(f"- Geschäftsmodell: {self.business_model}")
        if self.strategy:
            lines.append(f"- Strategie: {json.dumps(self.strategy, ensure_ascii=False)[:300]}")
        if self.products:
            lines.append(f"- Produkt: {json.dumps(self.products[-1], ensure_ascii=False)[:300]}")
        if self.feedback_history:
            fb = self.feedback_history[-1]
            lines.append(f"- Letztes Feedback (Score {fb.get('satisfaction_score','?')}): {fb.get('overall_assessment','')[:200]}")
        if self.marketing:
            lines.append(f"- Marketing: {json.dumps(self.marketing, ensure_ascii=False)[:200]}")
        lines.append(f"- Kosten bisher: ${self.total_cost:.4f}")
        return "\n".join(lines)

    def to_dashboard_dict(self) -> dict:
        """JSON-serializable snapshot for the dashboard."""
        return {
            "company_name": self.company_name,
            "industry": self.industry,
            "business_model": self.business_model,
            "iteration": self.iteration,
            "total_cost": self.total_cost,
            "satisfaction": self.feedback_history[-1].get("satisfaction_score") if self.feedback_history else None,
            "strategy_summary": self.strategy.get("strategy_summary", ""),
            "started_at": self.started_at,
        }

    def save(self, filepath: str):
        self.last_updated = datetime.now().isoformat()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "CompanyState":
        with open(filepath, encoding="utf-8") as f:
            return cls(**json.load(f))

    def save_memory(self, memory_dir: str):
        """Write daily markdown memory (OpenClaw pattern)."""
        os.makedirs(memory_dir, exist_ok=True)
        path = os.path.join(memory_dir, f"{datetime.now():%Y-%m-%d}.md")
        content = (
            f"# SwarmCorp Memory — {datetime.now():%Y-%m-%d}\n\n"
            f"## Iteration {self.iteration}\n"
            f"- Strategie: {self.strategy.get('strategy_summary', 'N/A')}\n"
        )
        if self.feedback_history:
            fb = self.feedback_history[-1]
            content += f"- Zufriedenheit: {fb.get('satisfaction_score', '?')}\n"
            content += f"- Feedback: {fb.get('overall_assessment', '')[:200]}\n"
        content += f"- Kosten: ${self.total_cost:.4f}\n"
        content += f"- Entscheidung: {self.strategy.get('decision', 'N/A')}\n\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
