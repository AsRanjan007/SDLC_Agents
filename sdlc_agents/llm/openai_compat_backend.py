"""OpenAI-compatible HTTP backend (Ollama / LM Studio / vLLM / llama.cpp server).

Intended for a **local** endpoint (e.g. ``http://127.0.0.1:11434/v1``). Corporate
proxy settings are honoured for the rare case where the endpoint is a
network-internal model gateway. When ``security.offline_only`` is enabled the
factory refuses to build this backend at all, guaranteeing no packets leave the
device.

Uses only the standard library (``urllib``) so there is no third-party HTTP
dependency to vet for an air-gapped deployment.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .base import LLMBackend, LLMResponse
from ..config import OpenAICompatConfig, ProxyConfig


def _build_opener(proxy: ProxyConfig, verify_ssl: bool):
    handlers = []
    if not proxy.use_system_proxy:
        proxies = {}
        if proxy.http_proxy:
            proxies["http"] = proxy.http_proxy
        if proxy.https_proxy:
            proxies["https"] = proxy.https_proxy
        handlers.append(urllib.request.ProxyHandler(proxies))
    if not verify_ssl:
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers)


class OpenAICompatBackend(LLMBackend):
    name = "openai_compat"

    def __init__(self, cfg: OpenAICompatConfig, proxy: ProxyConfig | None = None):
        self.cfg = cfg
        self.proxy = proxy or ProxyConfig()

    @property
    def label(self) -> str:
        netloc = urlparse(self.cfg.base_url).netloc or self.cfg.base_url
        model = self.cfg.model or "model"
        return f"{model} @ {netloc}"

    def _endpoint(self) -> str:
        base = self.cfg.base_url.rstrip("/")
        return f"{base}/chat/completions"

    def available(self) -> tuple[bool, str]:
        host = urlparse(self.cfg.base_url).hostname or ""
        if not self.cfg.base_url:
            return False, "No endpoint URL configured."
        local = host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
        note = "local" if local else "remote (network) endpoint"
        return True, f"Endpoint configured: {self.cfg.base_url} ({note}, model={self.cfg.model})"

    def generate(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint(),
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.api_key}",
            },
            method="POST",
        )
        opener = _build_opener(self.proxy, self.cfg.verify_ssl)
        try:
            with opener.open(req, timeout=self.cfg.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise RuntimeError(f"LLM endpoint error: {exc}") from exc
        text = body["choices"][0]["message"]["content"] or ""
        return LLMResponse(text=text.strip(), backend=self.name, model=self.cfg.model)


def build(cfg: OpenAICompatConfig, proxy: ProxyConfig) -> OpenAICompatBackend:
    return OpenAICompatBackend(cfg, proxy)
