"""
SwarmCorp — Dashboard Server
Real-time web dashboard via FastAPI + WebSocket.
Supports multiple simulation sessions and post-simulation CEO chat.
"""
import asyncio
import json
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows (module-level prints use emojis)
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from dashboard.sessions import SessionManager

app = FastAPI(title="SwarmCorp Dashboard")

TEMPLATE_DIR = Path(__file__).parent / "templates"

sessions = SessionManager()

# Load previously archived sessions so they show in sidebar on startup
try:
    from config import ARCHIVE_ROOT as _archive_root
    sessions.load_archived_sessions(_archive_root)
    if sessions.archived_sessions:
        print(f"  📂 {len(sessions.archived_sessions)} archivierte Session(s) geladen aus {_archive_root}")
        for a in sessions.archived_sessions:
            print(f"     ↳ {a.get('company_name') or a.get('idea', '?')} (Score: {a.get('satisfaction', '—')}, ${a.get('cost', 0):.4f})")
    else:
        print(f"  📂 Kein Archiv gefunden (wird erstellt nach erster Simulation)")
except Exception as e:
    print(f"  ⚠️  Archiv laden fehlgeschlagen: {e}")


class EventBridge:
    """Bridges sync orchestrator events → async WebSocket broadcasts."""

    def __init__(self):
        self.clients: list[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def emit(self, event: dict):
        """Called from orchestrator thread (sync). Queues broadcast to async loop."""
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
        session_list = sessions.list_sessions()
        active = [s for s in session_list if s["status"] != "archived"]
        archived = [s for s in session_list if s["status"] == "archived"]
        print(f"  🔌 WebSocket verbunden ({len(self.clients)} Client(s)) — {len(active)} aktiv, {len(archived)} archiviert")
        # Send session list
        await ws.send_text(json.dumps({
            "type": "session_list",
            "sessions": session_list,
        }, ensure_ascii=False, default=str))
        # Replay active session events
        if sessions.active_session_id:
            session = sessions.get_session(sessions.active_session_id)
            if session:
                for event in session.event_log:
                    try:
                        await ws.send_text(json.dumps(event, ensure_ascii=False, default=str))
                    except Exception:
                        break

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)
            print(f"  🔌 WebSocket getrennt ({len(self.clients)} Client(s) verbleibend)")


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
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "submit_idea":
                _handle_submit_idea(msg)
            elif msg_type == "chat_message":
                _handle_chat_message(msg)
    except WebSocketDisconnect:
        bridge.disconnect(ws)


def _handle_submit_idea(msg: dict):
    idea = msg.get("idea", "").strip()
    if not idea:
        bridge.emit({"type": "error", "message": "Keine Idee angegeben"})
        return

    # Reject if a simulation is already running
    if sessions.active_session_id:
        active = sessions.get_session(sessions.active_session_id)
        if active and active.status == "running":
            bridge.emit({"type": "error", "message": "Eine Simulation läuft bereits"})
            return

    session = sessions.create_session(idea)
    sessions.active_session_id = session.session_id
    print(f"\n  🆕 Session erstellt: {session.session_id}")
    print(f"     Idee: {idea}")

    bridge.emit({
        "type": "session_started",
        "session_id": session.session_id,
        "idea": idea,
    })

    thread = threading.Thread(
        target=_run_session_simulation,
        args=(session,),
        daemon=True,
    )
    thread.start()


def _handle_chat_message(msg: dict):
    session_id = msg.get("session_id")
    message = msg.get("message", "").strip()

    if not message:
        return

    session = sessions.get_session(session_id) if session_id else None
    if not session or session.status != "complete" or not session.ceo_agent:
        bridge.emit({"type": "error", "message": "Session nicht verfügbar"})
        return

    bridge.emit({"type": "chat_thinking", "session_id": session_id})

    thread = threading.Thread(
        target=_run_chat,
        args=(session, message),
        daemon=True,
    )
    thread.start()


def _run_session_simulation(session):
    """Worker thread: run the full simulation for a session."""
    from orchestration import SwarmCorpOrchestrator

    def on_event(event):
        event["session_id"] = session.session_id
        session.event_log.append(event)
        bridge.emit(event)

    try:
        orch = SwarmCorpOrchestrator(idea=session.idea, on_event=on_event)
        state = orch.run()
        session.state = state
        session.ceo_agent = orch.ceo
        session.total_cost = state.total_cost
        session.status = "complete"

        # Archive completed session to disk
        try:
            from config import ARCHIVE_ROOT
            print(f"\n  📦 Archiviere Session {session.session_id}...")
            sessions.archive_session(session.session_id, ARCHIVE_ROOT)
            print(f"  ✅ Archiv gespeichert: {ARCHIVE_ROOT}/{session.session_id}_*/")
        except Exception as e:
            print(f"  ⚠️  Archiv fehlgeschlagen: {e}")

        # Broadcast updated session list
        bridge.emit({
            "type": "session_list",
            "sessions": sessions.list_sessions(),
        })

        print(f"\n{'='*60}\n  SIMULATION ABGESCHLOSSEN\n{'='*60}")
        print(f"  Firma: {state.company_name}")
        print(f"  Iterationen: {state.iteration}")
        if state.feedback_history:
            print(f"  Finale Zufriedenheit: {state.feedback_history[-1].get('satisfaction_score', '?')}")
        print(f"  Kosten: ${state.total_cost:.4f}")
        print(f"  💬 CEO Chat verfügbar im Dashboard.")
    except Exception as e:
        session.status = "error"
        bridge.emit({
            "type": "error",
            "session_id": session.session_id,
            "message": str(e),
        })


def _run_chat(session, message: str):
    """Worker thread: run CEO chat for a session."""
    try:
        context = session.state.get_context_summary() if session.state else ""

        text, usage = session.ceo_agent.chat_about_results(
            user_message=message,
            chat_history=session.chat_history,
            context=context,
        )

        session.chat_history.append({"role": "user", "content": message})
        session.chat_history.append({"role": "assistant", "content": text})

        cost = usage.cost(session.ceo_agent.model)
        session.total_cost += cost

        bridge.emit({
            "type": "chat_response",
            "session_id": session.session_id,
            "message": text,
            "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
            "cost": cost,
            "total_cost": session.total_cost,
        })
    except Exception as e:
        bridge.emit({
            "type": "error",
            "session_id": session.session_id,
            "message": f"Chat-Fehler: {e}",
        })


def _run_server(host: str, port: int):
    """Run uvicorn in a daemon thread."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_dashboard(idea: str = "", mode: str = "simulation", topic: str = ""):
    """Start dashboard server + optionally run simulation with event bridge."""
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

    # Event loop for cross-thread bridging
    bridge.loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=bridge.loop.run_forever, daemon=True)
    loop_thread.start()

    url = f"http://localhost:{port}"
    print(f"\n  🌐 Dashboard: {url}")
    webbrowser.open(url)

    # Small delay so browser connects before simulation starts
    time.sleep(1.5)

    if mode == "discussion" and topic:
        _run_discussion_with_events(topic)
    elif idea:
        # CLI-provided idea: create session and run immediately
        session = sessions.create_session(idea)
        sessions.active_session_id = session.session_id
        bridge.emit({
            "type": "session_started",
            "session_id": session.session_id,
            "idea": idea,
        })
        _run_session_simulation(session)
    else:
        print("  ⏳ Warte auf Idee vom Dashboard...")

    # Keep process alive for chat / new simulations
    print("  💬 Dashboard aktiv. Ctrl+C zum Beenden.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Dashboard beendet.")


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
