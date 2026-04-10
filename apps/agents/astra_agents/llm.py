"""CrewAI LLM configuration — Groq (fast, free) with Ollama fallback.

Priority:
1. **Groq** (cloud, ~1s responses): set `GROQ_API_KEY` in `.env`
   → model string: `groq/llama-3.1-8b-instant`
2. **Ollama** (local, slow on CPU): always available as fallback
   → model string: `ollama/llama3.1:8b-instruct-q4_K_M`

Two temperature profiles:
- `default` (temp 0.2): structured extraction, JSON output, scoring
- `creative` (temp 0.7): roadmap prose, judge personas, vault narration

Every CrewAI agent MUST use one of `get_default_llm()` / `get_creative_llm()`.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from crewai import LLM

logger = logging.getLogger("astra.llm")

# Groq config (preferred — fast + free)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("ASTRA_GROQ_MODEL", "groq/llama-3.1-8b-instant")

# Ollama config (fallback — local, slow on CPU)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ASTRA_LLM_MODEL", "ollama/llama3.1:8b-instruct-q4_K_M")

# Temperatures
DEFAULT_TEMPERATURE = float(os.getenv("ASTRA_LLM_TEMPERATURE_DEFAULT", "0.2"))
CREATIVE_TEMPERATURE = float(os.getenv("ASTRA_LLM_TEMPERATURE_CREATIVE", "0.7"))


def _select_model() -> tuple[str, str | None]:
    """Pick the best available model. Returns (model_string, base_url_or_none)."""
    if GROQ_API_KEY:
        logger.info("Using Groq LLM: %s", GROQ_MODEL)
        return GROQ_MODEL, None  # LiteLLM handles Groq's base URL
    logger.info("No GROQ_API_KEY — falling back to Ollama: %s", OLLAMA_MODEL)
    return OLLAMA_MODEL, OLLAMA_HOST


@lru_cache(maxsize=1)
def get_default_llm() -> LLM:
    """Low-temperature LLM for structured extraction and scoring."""
    model, base_url = _select_model()
    kwargs: dict = {"model": model, "temperature": DEFAULT_TEMPERATURE}
    if base_url:
        kwargs["base_url"] = base_url
    return LLM(**kwargs)


@lru_cache(maxsize=1)
def get_creative_llm() -> LLM:
    """Higher-temperature LLM for prose, personas, and roadmap generation."""
    model, base_url = _select_model()
    kwargs: dict = {"model": model, "temperature": CREATIVE_TEMPERATURE}
    if base_url:
        kwargs["base_url"] = base_url
    return LLM(**kwargs)
