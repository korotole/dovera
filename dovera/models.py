"""LLM backend factory: Anthropic, OpenAI, or a local Ollama model.

One function, `build_model`, is all callers use. Selection: explicit
backend argument, else DOVERA_BACKEND, else first present key (Anthropic,
OpenAI), else a reachable local Ollama. Any LangChain chat model works —
the checker only calls `.invoke`/`.bind_tools`.
"""

from __future__ import annotations

import os

ANTHROPIC_MODEL = "claude-sonnet-5"
OPENAI_MODEL = "gpt-5.1"
OLLAMA_MODEL = "qwen3:14b"
OLLAMA_URL = "http://localhost:11434"


def _anthropic(model: str):
    from langchain_anthropic import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN not set")
    return ChatAnthropic(model=model, max_tokens=8000, timeout=600,
                         api_key=api_key,
                         base_url=os.environ.get("ANTHROPIC_BASE_URL") or None)


def _openai(model: str):
    from langchain_openai import ChatOpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")
    return ChatOpenAI(model=model, timeout=600,
                      base_url=os.environ.get("OPENAI_BASE_URL") or None)


def _ollama(model: str):
    from langchain_ollama import ChatOllama

    host = os.environ.get("OLLAMA_HOST") or OLLAMA_URL
    if not host.startswith("http"):
        host = f"http://{host}"
    return ChatOllama(model=model, base_url=host,
                      num_ctx=32768, temperature=0.2, keep_alive="30m")


_BACKENDS = {"anthropic": (ANTHROPIC_MODEL, _anthropic),
             "openai": (OPENAI_MODEL, _openai),
             "ollama": (OLLAMA_MODEL, _ollama)}


def ollama_reachable() -> bool:
    try:
        import httpx

        return httpx.get(OLLAMA_URL + "/api/version", timeout=2).status_code == 200
    except Exception:  # noqa: BLE001 — unreachable local server is a normal state
        return False


def pick_backend() -> str:
    """DOVERA_BACKEND, else first present key, else reachable Ollama."""
    env = os.environ.get("DOVERA_BACKEND")
    if env:
        return env
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if ollama_reachable():
        return "ollama"
    raise RuntimeError(
        "No LLM backend: set ANTHROPIC_API_KEY or OPENAI_API_KEY, or start "
        f"Ollama (`ollama serve`) and pull `{OLLAMA_MODEL}`.")


def build_model(backend: str | None = None, model: str | None = None):
    """Return a LangChain chat model for `backend` (default: auto-pick)."""
    backend = backend or pick_backend()
    if backend not in _BACKENDS:
        raise ValueError(f"unknown backend {backend!r} (known: {', '.join(_BACKENDS)})")
    default_model, factory = _BACKENDS[backend]
    return factory(model or default_model)
