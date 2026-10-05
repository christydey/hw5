"""Model, Portkey and limit settings for the Campus Customs agent team.

Every agent uses the single model built here. There is deliberately no
environment override and no fallback model: the team may only ever call
MODEL_NAME through Portkey.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent  # homeworks/hwv5
PROMPTS_DIR = BACKEND_DIR / "prompts"
REPO_ENV_FILE = PROJECT_ROOT / ".env"  # a clone keeps its .env here (copied from .env.example)
ENV_FILE = PROJECT_ROOT.parents[1] / ".env"  # fallback: the course workspace root (AI-Foundation/.env)
MCP_CONFIG_FILE = PROJECT_ROOT / ".mcp.json"
MCP_SERVER_NAME = "campus-customs"
AUDIT_FILE = PROJECT_ROOT / "output" / "audit_trail.json"

# The only model the team may use.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- Bounds on the agent loop -------------------------------------------------
MAX_DELEGATION_DEPTH = 3  # boss -> specialist -> specialist -> specialist, no deeper
MAX_DELEGATIONS_PER_RUN = 8  # total hand-offs across the whole team for one ticket
MAX_LOOP_STEPS_PER_AGENT = 30  # graph nodes one agent run may take before we stop it
AGENT_RETRIES = 2  # tool-argument / output-validation retries per agent run
MODEL_HTTP_RETRIES = 2  # transport retries inside the OpenAI client
MODEL_TIMEOUT_SECONDS = 90
MCP_CALL_TIMEOUT_SECONDS = 30
MAX_TASK_CHARS = 1500  # longest task text one agent may hand another

# Shared by every agent in one ticket run (the RunUsage object is passed down
# each delegation), so these are team-wide totals, not per-agent.
TEAM_USAGE_LIMITS = UsageLimits(
    request_limit=40,
    tool_calls_limit=60,
    total_tokens_limit=250_000,
)

MODEL_SETTINGS = ModelSettings(
    max_tokens=4_000,  # includes reasoning tokens on reasoning models
    timeout=MODEL_TIMEOUT_SECONDS,
)


class ConfigurationError(RuntimeError):
    pass


def portkey_api_key() -> str:
    """Read PORTKEY_API_KEY from the environment, loading the repo's .env and
    then AI-Foundation/.env (neither overrides variables already set). The
    value is never logged or returned to callers outside this module except
    to build the client."""
    load_dotenv(REPO_ENV_FILE)
    load_dotenv(ENV_FILE)
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise ConfigurationError(
            f"PORTKEY_API_KEY is not set. Copy .env.example to {REPO_ENV_FILE} and fill it in, "
            "or export it in the environment."
        )
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = portkey_api_key()
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={
            "x-portkey-api-key": key,
            "x-portkey-provider": "openai",
            # Always generate a fresh answer. Without this, Portkey can replay a cached
            # response when a run repeats an earlier run's exact prompts (e.g. after a reset).
            "x-portkey-cache-force-refresh": "true",
        },
        max_retries=MODEL_HTTP_RETRIES,
        timeout=MODEL_TIMEOUT_SECONDS,
    )
    # Responses API, not Chat Completions: Portkey's gpt-6-luna deployment rejects
    # function tools on /v1/chat/completions unless reasoning is switched off.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
