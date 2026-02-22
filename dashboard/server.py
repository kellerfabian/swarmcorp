"""
SwarmCorp — Dashboard Server
Real-time web dashboard via FastAPI + WebSocket.
"""
import asyncio
import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="SwarmCorp Dashboard")

TEMPLATE_DIR = Path(__file__).parent / "templates"


class EventBridge:
    """Bridges sync orchestrator events → async WebSocket broadcasts."""

    def __init__(self):
        self.clients: list[WebSocket] = []
        self.event_log: list[dict] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def emit(self, event: dict):
        """Called from orchestrator thread (sync). Queues broadcast to async loop."""
        self.event_log.append(event)
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self.loop)

    async def _broadcast(self, event: dict):
        dead = []
        msg = json.dumps(event, ensure_ascii=False, default=str)
        for ws in self.clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.remove(ws)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)
        # Send event history so late joiners catch up
        for event in self.event_log:
            try:
                await ws.send_text(json.dumps(event, ensure_ascii=False, default=str))
            except Exception:
                break

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)


bridge = EventBridge()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = TEMPLATE_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await bridge.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        bridge.disconnect(ws)


def _run_server(host: str, port: int):
    """Run uvicorn in a daemon thread."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_dashboard(idea: str = "", mode: str = "simulation", topic: str = ""):
    """Start dashboard server + run simulation with event bridge."""
    from config import DASHBOARD_HOST, DASHBOARD_PORT

    host = DASHBOARD_HOST
    port = DASHBOARD_PORT

    # Start server thread
    server_thread = threading.Thread(
        target=_run_server, args=(host, port), daemon=True
    )
    server_thread.start()

    # Give server time to start
    time.sleep(1.0)

    # Capture the event loop from the server for cross-thread bridging
    # We'll set it from the WebSocket handler on first connect, or just use a fresh one
    bridge.loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=bridge.loop.run_forever, daemon=True)
    loop_thread.start()

    url = f"http://localhost:{port}"
    print(f"\n  🌐 Dashboard: {url}")
    webbrowser.open(url)

    # Small delay so browser connects before simulation starts
    time.sleep(1.5)

    if mode == "discussion":
        _run_discussion_with_events(topic)
    else:
        _run_simulation_with_events(idea)


def _run_simulation_with_events(idea: str):
    from orchestration import SwarmCorpOrchestrator

    orch = SwarmCorpOrchestrator(idea=idea, on_event=bridge.emit)
    state = orch.run()

    print(f"\n{'='*60}\n  SIMULATION ABGESCHLOSSEN\n{'='*60}")
    print(f"  Firma: {state.company_name}")
    print(f"  Iterationen: {state.iteration}")
    if state.feedback_history:
        print(f"  Finale Zufriedenheit: {state.feedback_history[-1].get('satisfaction_score', '?')}")
    print(f"  Kosten: ${state.total_cost:.4f}")


def _run_discussion_with_events(topic: str):
    import anthropic
    from datetime import datetime
    from agents import CEOAgent, MarketingAgent, DeveloperAgent, CustomerAgent
    from config import ANTHROPIC_API_KEY, MEMORY_ROOT, WORKSPACE_ROOT
    from state import CompanyState

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    agents = {
        "ceo": CEOAgent(client=client, on_event=bridge.emit),
        "marketing": MarketingAgent(client=client, on_event=bridge.emit),
        "developer": DeveloperAgent(client=client, on_event=bridge.emit),
        "customer": CustomerAgent(client=client, on_event=bridge.emit),
    }

    state = CompanyState(started_at=datetime.now().isoformat())

    bridge.emit({"type": "phase_start", "phase": f"Diskussion: {topic}", "emoji": "🎙️", "iteration": 0})

    perspectives = {}
    for name, agent in agents.items():
        print(f"\n  {name.upper()}...")
        result = agent.call(
            f"Thema: {topic}\n\n"
            f"Deine Einschätzung als {name}: Chancen, Risiken, Empfehlung. "
            f"JSON mit: perspective, opportunities, risks, recommendation",
            temperature=0.8,
        )
        perspectives[name] = result
        state.log_message(name, "perspective", json.dumps(result, ensure_ascii=False)[:500])

    bridge.emit({"type": "phase_start", "phase": "CEO Synthese", "emoji": "👔", "iteration": 0})

    print(f"\n  CEO Synthese...")
    synthesis = agents["ceo"].call(
        f"Team-Perspektiven zu '{topic}':\n"
        f"{json.dumps(perspectives, ensure_ascii=False, indent=2)}\n\n"
        f"Synthetisiere zu einer Entscheidung. Welche Perspektive überzeugt?",
    )
    state.log_message("ceo", "synthesis", json.dumps(synthesis, ensure_ascii=False)[:500])

    total = sum(a.total_usage.cost(a.model) for a in agents.values())

    bridge.emit({
        "type": "simulation_complete",
        "state": {
            "company_name": "SwarmCorp Diskussion",
            "topic": topic,
            "synthesis": synthesis,
            "total_cost": total,
        },
    })

    print(f"\n{'='*60}\n  ENTSCHEIDUNG:\n{json.dumps(synthesis, ensure_ascii=False, indent=2)[:1000]}\n{'='*60}")
    print(f"\n  Kosten: ${total:.4f}")

    # Persist
    state.total_cost = total
    state.strategy = synthesis
    state.industry = topic
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    discussion_file = os.path.join(WORKSPACE_ROOT, f"discussion_{timestamp}.json")
    with open(discussion_file, "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "perspectives": perspectives, "synthesis": synthesis, "cost": total}, f, ensure_ascii=False, indent=2)
    state.save(os.path.join(MEMORY_ROOT, f"discussion_{timestamp}.json"))
    state.save_memory(MEMORY_ROOT)
