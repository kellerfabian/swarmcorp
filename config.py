"""
SwarmCorp — Configuration
Multi-Agent KI-Firma Simulation
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model routing per agent role
MODELS = {
    "ceo":       "claude-sonnet-4-5-20250929",
    "marketing": "claude-sonnet-4-5-20250929",
    "developer": "claude-sonnet-4-5-20250929",
    "customer":  "claude-haiku-4-5-20251001",
}

# Simulation parameters
MAX_ITERATIONS = 5
TARGET_SATISFACTION = 0.85
MAX_DEV_REVIEW_LOOPS = 3

# Web Search — Anthropic built-in server tool
WEB_SEARCH_ENABLED = True
WEB_SEARCH_AGENTS = ["marketing", "ceo"]  # Agenten mit Web-Recherche

# Paths (OpenClaw workspace pattern)
PROJECT_ROOT = os.path.dirname(__file__)
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, "workspace")
MEMORY_ROOT = os.path.join(PROJECT_ROOT, "memory")

# Pricing per 1M tokens
PRICING = {
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
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
