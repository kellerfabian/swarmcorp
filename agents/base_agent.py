"""
SwarmCorp — Base Agent
Loads SOUL.md personality + skills, calls Claude API, returns structured JSON.
"""
import json, os, re
from typing import Optional
import anthropic
from config import MODELS, ANTHROPIC_API_KEY, WORKSPACE_ROOT, TokenUsage


class BaseAgent:
    def __init__(self, agent_id: str, client: Optional[anthropic.Anthropic] = None):
        self.agent_id = agent_id
        self.model = MODELS.get(agent_id, "claude-sonnet-4-5-20250929")
        self.client = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.total_usage = TokenUsage()
        self.soul = self._load_file("SOUL.md")
        self.skills = self._load_skills()

    def _load_file(self, filename: str) -> str:
        path = os.path.join(WORKSPACE_ROOT, self.agent_id, filename)
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def _load_skills(self) -> str:
        skills_dir = os.path.join(WORKSPACE_ROOT, self.agent_id, "skills")
        if not os.path.exists(skills_dir):
            return ""
        parts = []
        for fname in sorted(os.listdir(skills_dir)):
            if fname.endswith(".md"):
                with open(os.path.join(skills_dir, fname)) as f:
                    parts.append(f.read())
        return "\n\n---\n\n".join(parts)

    def _build_system_prompt(self, context: str = "") -> str:
        """Assemble: SOUL.md + Skills + Context + JSON instruction."""
        parts = [self.soul]
        if self.skills:
            parts.append(f"\n## Verfügbare Skills\n{self.skills}")
        if context:
            parts.append(f"\n## Aktueller Firmenkontext\n{context}")
        parts.append(
            "\n## WICHTIG\n"
            "Antworte AUSSCHLIESSLICH mit validem JSON. "
            "Kein Markdown, kein Text drumherum, nur das JSON-Objekt."
        )
        return "\n\n".join(parts)

    def call(self, user_message: str, context: str = "", temperature: float = 0.7) -> dict:
        """Core agent loop step: context → prompt → model → parse → return."""
        system = self._build_system_prompt(context)
        print(f"  🤖 [{self.agent_id.upper()}] Denkt nach...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        usage = TokenUsage(response.usage.input_tokens, response.usage.output_tokens)
        self.total_usage = self.total_usage + usage
        cost = usage.cost(self.model)

        raw = "".join(b.text for b in response.content if b.type == "text")
        print(f"  ✅ [{self.agent_id.upper()}] {usage.input_tokens}+{usage.output_tokens} tok, ${cost:.4f}")

        return self._parse_json(raw)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Robust JSON extraction."""
        text = text.strip()
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # From code block
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Find JSON object
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_response": text, "parse_error": True}
