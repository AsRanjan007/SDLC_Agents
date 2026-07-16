"""Backend factory + status helpers.

``build_backend`` returns a concrete :class:`LLMBackend` or ``None``. ``None``
means "run in offline mode" (use :mod:`sdlc_agents.llm.offline_engine`), which
is a fully-supported first-class path — not an error.
"""

from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from .base import LLMBackend


def build_backend(cfg: AppConfig) -> Optional[LLMBackend]:
    """Instantiate the configured backend, honouring the offline-only guard."""

    if cfg.backend == "llama_cpp":
        from . import llama_cpp_backend

        return llama_cpp_backend.build(cfg.llama_cpp)

    if cfg.backend == "openai_compat":
        if cfg.security.offline_only:
            # Refuse to build a network backend while offline-only is enforced.
            return None
        from . import openai_compat_backend

        return openai_compat_backend.build(cfg.openai_compat, cfg.proxy)

    # "offline" or anything unknown -> deterministic engine.
    return None


def backend_status(cfg: AppConfig) -> tuple[bool, str]:
    """Human-readable readiness string for the UI."""

    if cfg.backend == "offline":
        return True, "Offline deterministic engine (no model, no network)."

    if cfg.backend == "openai_compat" and cfg.security.offline_only:
        return False, (
            "OpenAI-compatible endpoint is blocked because 'offline-only' is ON "
            "(Settings -> Security). Falling back to the offline engine."
        )

    backend = build_backend(cfg)
    if backend is None:
        return True, "Offline deterministic engine (no model, no network)."
    return backend.available()
