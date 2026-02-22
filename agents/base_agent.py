"""
SwarmCorp — Base Agent
Loads SOUL.md personality + skills, calls Claude API, returns structured JSON.
"""
import json, os, re
from typing import Optional
import anthropic
from config import MODELS, ANTHROPIC_API_KEY, WORKSPACE_ROOT, TokenUsage, WEB_SEARCH_ENABLED, WEB_SEARCH_AGENTS


class BaseAgent:
    def __init__(self, agent_id: str, client: Optional[anthropic.Anthropic] = None, on_event=None):
        self.agent_id = agent_id
        self.model = MODELS.get(agent_id, "claude-sonnet-4-5-20250929")
        self.client = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.total_usage = TokenUsage()
        self.web_search = WEB_SEARCH_ENABLED and agent_id in WEB_SEARCH_AGENTS
        self.on_event = on_event
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

    def _emit(self, event: dict):
        if self.on_event:
            self.on_event(event)

    def call(self, user_message: str, context: str = "", temperature: float = 0.7) -> dict:
        """Core agent loop step: context → prompt → model → parse → return."""
        system = self._build_system_prompt(context)
        emoji = "🔍" if self.web_search else "🤖"
        print(f"  {emoji} [{self.agent_id.upper()}] Denkt nach{' (+ Web Search)' if self.web_search else ''}...")
        self._emit({"type": "agent_thinking", "agent": self.agent_id, "web_search": self.web_search})

        kwargs = dict(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        if self.web_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]

        response = self.client.messages.create(**kwargs)

        # Agentic loop: keep going while the model wants to use tools
        messages = kwargs["messages"][:]
        loop_usage = TokenUsage(response.usage.input_tokens, response.usage.output_tokens)

        while response.stop_reason == "tool_use" and self.web_search:
            # Collect the assistant's content (tool_use + server_tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Build tool results for any client-side tool_use blocks
            tool_results = []
            for block in response.content:
                if block.type == "web_search_tool_result":
                    print(f"    🌐 Web-Suche durchgeführt")
                    self._emit({"type": "agent_web_search", "agent": self.agent_id})
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search completed.",
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                tools=kwargs.get("tools", []),
                messages=messages,
            )
            loop_usage = loop_usage + TokenUsage(response.usage.input_tokens, response.usage.output_tokens)

        self.total_usage = self.total_usage + loop_usage
        cost = loop_usage.cost(self.model)

        raw = "".join(b.text for b in response.content if b.type == "text")
        print(f"  ✅ [{self.agent_id.upper()}] {loop_usage.input_tokens}+{loop_usage.output_tokens} tok, ${cost:.4f}")

        result = self._parse_json(raw)
        self._emit({
            "type": "agent_done",
            "agent": self.agent_id,
            "tokens": {"input": loop_usage.input_tokens, "output": loop_usage.output_tokens},
            "cost": cost,
            "result": result,
        })
        return result

    def chat(self, messages: list[dict], context: str = "", temperature: float = 0.7) -> tuple[str, "TokenUsage"]:
        """Conversational chat without JSON enforcement. Returns (text, usage)."""
        parts = [self.soul]
        if self.skills:
            parts.append(f"\n## Verfügbare Skills\n{self.skills}")
        if context:
            parts.append(f"\n## Aktueller Firmenkontext\n{context}")
        parts.append(
            "\n## WICHTIG\n"
            "Antworte in natürlicher Sprache auf Deutsch. "
            "Du bist ein erfahrener Experte in deiner Rolle und antwortest "
            "auf Fragen zu den Ergebnissen der Simulation."
        )
        system = "\n\n".join(parts)

        self._emit({"type": "agent_thinking", "agent": self.agent_id, "web_search": False})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=temperature,
            system=system,
            messages=messages,
        )

        usage = TokenUsage(response.usage.input_tokens, response.usage.output_tokens)
        self.total_usage = self.total_usage + usage

        text = "".join(b.text for b in response.content if b.type == "text")
        cost = usage.cost(self.model)
        print(f"  💬 [{self.agent_id.upper()}] Chat: {usage.input_tokens}+{usage.output_tokens} tok, ${cost:.4f}")

        return text, usage

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
