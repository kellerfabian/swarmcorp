"""
SwarmCorp — Base Agent
Loads SOUL.md personality + skills, calls Claude API, returns structured JSON.
"""
import json, os, re, textwrap, time
from typing import Optional
import anthropic
from config import MODELS, ANTHROPIC_API_KEY, WORKSPACE_ROOT, TokenUsage, WEB_SEARCH_ENABLED, WEB_SEARCH_AGENTS, DEBUG, log

API_TIMEOUT = 180  # Total seconds per streaming call (hard wall-clock limit)
MAX_RETRIES = 3    # Retry attempts before giving up
RETRY_BACKOFF = [5, 15, 30]  # Seconds to wait between retries

# Errors that are worth retrying (transient / server-side)
RETRYABLE = (
    TimeoutError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


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

    @staticmethod
    def _debug(label: str, text: str, max_len: int = 500):
        """Print debug info when DEBUG=true."""
        if not DEBUG:
            return
        separator = f"  {'-'*60}"
        log(separator)
        log(f"  [DEBUG] {label}")
        log(separator)
        truncated = textwrap.shorten(text, width=max_len, placeholder="... [truncated]")
        for line in truncated.split("\n"):
            log(f"     {line}")
        log(separator)

    # ── API call layer ─────────────────────────────────────────────

    def _stream_call(self, **kwargs):
        """Single streaming API call with real-time progress logging + timeout."""
        start = time.time()
        search_count = 0
        tag = self.agent_id.upper()

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                elapsed = time.time() - start
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    block = event.content_block
                    btype = getattr(block, "type", "")
                    if btype == "server_tool_use":
                        log(f"    🌐 [{elapsed:.0f}s] Web-Suche gestartet...")
                    elif btype == "web_search_tool_result":
                        search_count += 1
                        log(f"    🔍 [{elapsed:.0f}s] Web-Ergebnis #{search_count} empfangen")
                    elif btype == "text":
                        log(f"    📝 [{elapsed:.0f}s] Generiere Antwort...")
                    elif btype == "tool_use":
                        name = getattr(block, "name", "?")
                        log(f"    🔧 [{elapsed:.0f}s] Tool-Aufruf: {name}")

                if elapsed > API_TIMEOUT:
                    raise TimeoutError(f"[{tag}] Streaming exceeded {API_TIMEOUT}s")

            response = stream.get_final_message()

        total = time.time() - start
        searches = f", {search_count} Web-Suchen" if search_count else ""
        log(f"    ⏱️  [{total:.0f}s] Antwort erhalten{searches}")
        return response

    def _call_with_retry(self, **kwargs):
        """Retry wrapper: up to MAX_RETRIES, with backoff. Last resort drops web search."""
        tag = self.agent_id.upper()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._stream_call(**kwargs)
            except RETRYABLE as e:
                last_error = e
                wait = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
                log(f"  ⚠️  [{tag}] Versuch {attempt}/{MAX_RETRIES} fehlgeschlagen: {type(e).__name__}")
                self._emit({"type": "agent_retry", "agent": self.agent_id, "attempt": attempt, "error": type(e).__name__})
                if attempt < MAX_RETRIES:
                    log(f"  ⏳ [{tag}] Warte {wait}s vor nächstem Versuch...")
                    time.sleep(wait)
            except Exception as e:
                log(f"  ❌ [{tag}] Unerwarteter Fehler: {type(e).__name__}: {e}")
                raise

        # All retries exhausted — last resort: drop web search tools and try once more
        if "tools" in kwargs:
            log(f"  🔄 [{tag}] Letzter Versuch ohne Web Search...")
            fallback_kwargs = {k: v for k, v in kwargs.items() if k != "tools"}
            try:
                return self._stream_call(**fallback_kwargs)
            except Exception as e:
                log(f"  ❌ [{tag}] Auch ohne Web Search fehlgeschlagen: {type(e).__name__}")

        log(f"  ❌ [{tag}] Alle {MAX_RETRIES} Versuche fehlgeschlagen!")
        self._emit({"type": "agent_failed", "agent": self.agent_id, "error": str(last_error)})
        return None  # Caller handles None → error dict

    # ── Main call method ─────────────────────────────────────────

    def call(self, user_message: str, context: str = "", temperature: float = 0.7) -> dict:
        """Core agent loop step: context → prompt → model → parse → return."""
        system = self._build_system_prompt(context)
        emoji = "🔍" if self.web_search else "🤖"
        log(f"  {emoji} [{self.agent_id.upper()}] Denkt nach{' (+ Web Search)' if self.web_search else ''}...")
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

        self._debug(
            f"[{self.agent_id.upper()}] REQUEST → {self.model}",
            f"system ({len(system)} chars): {system}\n\nuser: {user_message}",
        )

        response = self._call_with_retry(**kwargs)
        if response is None:
            return {"error": "API call failed after all retries", "agent": self.agent_id}

        # Agentic loop: keep going while the model wants to use tools
        messages = kwargs["messages"][:]
        loop_usage = TokenUsage(response.usage.input_tokens, response.usage.output_tokens)

        max_loops = 5
        loop_count = 0
        while response.stop_reason == "tool_use" and self.web_search and loop_count < max_loops:
            loop_count += 1
            self._debug(
                f"[{self.agent_id.upper()}] TOOL LOOP #{loop_count}/{max_loops} (stop={response.stop_reason})",
                f"content blocks: {[b.type for b in response.content]}",
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "web_search_tool_result":
                    log(f"    🌐 Web-Suche durchgeführt")
                    self._emit({"type": "agent_web_search", "agent": self.agent_id})
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search completed.",
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            loop_response = self._call_with_retry(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                tools=kwargs.get("tools", []),
                messages=messages,
            )
            if loop_response is None:
                log(f"  ⚠️  [{self.agent_id.upper()}] Tool-Loop abgebrochen nach Fehler")
                break
            response = loop_response
            loop_usage = loop_usage + TokenUsage(response.usage.input_tokens, response.usage.output_tokens)

        self.total_usage = self.total_usage + loop_usage
        cost = loop_usage.cost(self.model)

        raw = "".join(b.text for b in response.content if b.type == "text")
        log(f"  ✅ [{self.agent_id.upper()}] {loop_usage.input_tokens}+{loop_usage.output_tokens} tok, ${cost:.4f}")

        self._debug(
            f"[{self.agent_id.upper()}] RESPONSE (stop={response.stop_reason})",
            raw,
        )

        result = self._parse_json(raw)

        self._debug(
            f"[{self.agent_id.upper()}] PARSED JSON ({len(result)} keys: {', '.join(result.keys())})",
            json.dumps(result, ensure_ascii=False, indent=2),
        )

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

        self._debug(
            f"[{self.agent_id.upper()}] CHAT REQUEST → {self.model}",
            f"system ({len(system)} chars): {system}\n\nmessages ({len(messages)}): {json.dumps(messages, ensure_ascii=False)[:500]}",
        )

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
        log(f"  💬 [{self.agent_id.upper()}] Chat: {usage.input_tokens}+{usage.output_tokens} tok, ${cost:.4f}")

        self._debug(
            f"[{self.agent_id.upper()}] CHAT RESPONSE (stop={response.stop_reason})",
            text,
        )

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
