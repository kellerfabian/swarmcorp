"""
SwarmCorp — Configuration
Multi-Agent KI-Firma Simulation
"""
import os, sys
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows ProactorEventLoop assertion error (must run before any event loop)
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEBUG = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

# Model routing per agent role
MODELS = {
    "ceo":       "claude-sonnet-4-6",
    "marketing": "claude-sonnet-4-6",
    "developer": "claude-sonnet-4-6",
    "customer":  "claude-haiku-4-5-20251001",
}

# Simulation parameters
MAX_ITERATIONS = 5
TARGET_SATISFACTION = 0.85
MAX_DEV_REVIEW_LOOPS = 3

# Web Search — Anthropic built-in server tool
WEB_SEARCH_ENABLED = True
WEB_SEARCH_AGENTS = ["marketing", "ceo"]  # Agenten mit Web-Recherche

# Dashboard
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8050

# Paths (OpenClaw workspace pattern)
PROJECT_ROOT = os.path.dirname(__file__)
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, "workspace")
MEMORY_ROOT = os.path.join(PROJECT_ROOT, "memory")
ARCHIVE_ROOT = os.path.join(MEMORY_ROOT, "archive")

# Pricing per 1M tokens
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001":  {"input": 1.0, "output": 5.0},
}


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def cost(self, model: str) -> float:
        p = PRICING.get(model, {"input": 3.0, "output": 15.0})
        return (self.input_tokens * p["input"] + self.output_tokens * p["output"]) / 1_000_000

    def __add__(self, other):
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


# Ensure UTF-8 output on Windows for all log() calls
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure") and getattr(_stream, "encoding", "") != "utf-8":
            _stream.reconfigure(encoding="utf-8", errors="replace")


def log(*args, **kwargs):
    """Print with HH:MM:SS timestamp prefix."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}]", *args, **kwargs)
