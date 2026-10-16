"""Abstract LLM backend interface.

An ``LLMBackend`` is a thin, uniform wrapper around "give me text for this
system+user prompt". Concrete backends:

* :class:`~sdlc_agents.llm.llama_cpp_backend.LlamaCppBackend` - local GGUF file
* :class:`~sdlc_agents.llm.openai_compat_backend.OpenAICompatBackend` - a local
  OpenAI-compatible HTTP endpoint (Ollama / LM Studio / vLLM ...)

When *no* backend is configured or reachable, the app falls back to the
deterministic :mod:`sdlc_agents.llm.offline_engine`, which needs no model at
all. Agents therefore treat "no LLM" as a first-class, fully-supported mode.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    backend: str
    model: str


class LLMBackend(abc.ABC):
    """Common interface implemented by every real model backend."""

    #: short, stable identifier ("llama_cpp", "openai_compat")
    name: str = "base"

    @abc.abstractmethod
    def available(self) -> tuple[bool, str]:
        """Return ``(ok, human_readable_status)`` without raising."""

    @abc.abstractmethod
    def generate(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a completion for the given system + user prompt."""

    def describe(self) -> str:
        return self.name

    @property
    def label(self) -> str:
        """Human-friendly identifier for reports (model/endpoint, not the id)."""

        return self.name
