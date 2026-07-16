"""Local GGUF backend using ``llama-cpp-python``.

This backend runs a quantised model entirely on-device. It performs **zero**
network I/O: the model file must already be present on disk (downloaded once,
out of band). Import of ``llama_cpp`` is lazy so the rest of the app works even
when the package or its native library is not installed.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .base import LLMBackend, LLMResponse
from ..config import LlamaCppConfig


class LlamaCppBackend(LLMBackend):
    name = "llama_cpp"

    def __init__(self, cfg: LlamaCppConfig):
        self.cfg = cfg
        self._llm = None

    # ---- availability ----------------------------------------------------

    def available(self) -> tuple[bool, str]:
        try:
            import llama_cpp  # noqa: F401
        except Exception:  # pragma: no cover - depends on host install
            return False, (
                "llama-cpp-python is not installed. Install it with "
                "`pip install llama-cpp-python` (fully offline once wheels are "
                "cached), then set a model path in Settings."
            )
        if not self.cfg.model_path:
            return False, "No GGUF model path configured (Settings -> LLM)."
        if not os.path.isfile(self.cfg.model_path):
            return False, f"GGUF model not found: {self.cfg.model_path}"
        return True, f"Local GGUF ready: {os.path.basename(self.cfg.model_path)}"

    # ---- model loading ---------------------------------------------------

    def _load(self):
        if self._llm is not None:
            return self._llm
        from llama_cpp import Llama

        kwargs = dict(
            model_path=self.cfg.model_path,
            n_ctx=self.cfg.n_ctx,
            n_threads=self.cfg.n_threads or None,
            n_gpu_layers=self.cfg.n_gpu_layers,
            verbose=False,
        )
        if self.cfg.chat_format:
            kwargs["chat_format"] = self.cfg.chat_format
        self._llm = Llama(**kwargs)
        return self._llm

    # ---- generation ------------------------------------------------------

    def generate(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        llm = self._load()
        result = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = result["choices"][0]["message"]["content"] or ""
        model = os.path.basename(self.cfg.model_path)
        return LLMResponse(text=text.strip(), backend=self.name, model=model)


@lru_cache(maxsize=4)
def _cached_backend(model_path: str, n_ctx: int, n_threads: int, n_gpu_layers: int, chat_format: str):
    return LlamaCppBackend(
        LlamaCppConfig(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            chat_format=chat_format,
        )
    )


def build(cfg: LlamaCppConfig) -> LlamaCppBackend:
    """Return a process-cached backend so the model is loaded only once."""

    return _cached_backend(
        cfg.model_path, cfg.n_ctx, cfg.n_threads, cfg.n_gpu_layers, cfg.chat_format
    )
