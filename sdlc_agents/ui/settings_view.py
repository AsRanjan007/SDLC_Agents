"""Settings page: configure the LLM backend, proxy, security and audio."""

from __future__ import annotations

import streamlit as st

from ..config import AppConfig
from ..llm import backend_status
from ..audio import tts_available
from ..security import cryptography_available


BACKENDS = {
    "offline": "Offline engine (no model, no network) — always available",
    "llama_cpp": "Local GGUF model (llama-cpp-python) — recommended offline brain",
    "openai_compat": "Local OpenAI-compatible endpoint (Ollama / LM Studio / vLLM)",
}


def render(config: AppConfig) -> AppConfig:
    st.header("⚙️ Settings")
    st.caption(
        "All settings are stored locally under your SDLC_AGENTS_HOME directory. "
        "Nothing is transmitted anywhere."
    )

    # ---- LLM backend -----------------------------------------------------
    st.subheader("1. Agent LLM connection")
    backend_keys = list(BACKENDS.keys())
    backend = st.radio(
        "Backend",
        backend_keys,
        index=backend_keys.index(config.backend) if config.backend in backend_keys else 0,
        format_func=lambda k: BACKENDS[k],
    )
    config.backend = backend

    if backend == "llama_cpp":
        st.markdown("**Local GGUF model** — download a small `.gguf` once, place it on the device.")
        config.llama_cpp.model_path = st.text_input(
            "GGUF model path", value=config.llama_cpp.model_path,
            placeholder="/path/to/model.gguf",
        )
        c1, c2, c3 = st.columns(3)
        config.llama_cpp.n_ctx = c1.number_input("Context length", 512, 32768, config.llama_cpp.n_ctx, step=512)
        config.llama_cpp.n_threads = c2.number_input("CPU threads", 1, 64, config.llama_cpp.n_threads)
        config.llama_cpp.n_gpu_layers = c3.number_input("GPU layers", 0, 200, config.llama_cpp.n_gpu_layers)
        st.info("Tip: models like Qwen2.5-0.5B/1.5B-Instruct or Llama-3.2-1B (Q4) run well on edge CPUs.")
    elif backend == "openai_compat":
        st.markdown("**Local OpenAI-compatible endpoint** (keep it on-device, e.g. Ollama at `127.0.0.1:11434`).")
        config.openai_compat.base_url = st.text_input("Base URL", value=config.openai_compat.base_url)
        config.openai_compat.model = st.text_input("Model name", value=config.openai_compat.model)
        config.openai_compat.api_key = st.text_input("API key", value=config.openai_compat.api_key, type="password")
        config.openai_compat.verify_ssl = st.checkbox("Verify SSL", value=config.openai_compat.verify_ssl)
        if config.security.offline_only:
            st.warning("Offline-only mode is ON (Security section) — this network backend is blocked until you turn it off.")
    else:
        st.success("Offline engine selected — the full flow runs deterministically with no model or network.")

    ok, msg = backend_status(config)
    (st.success if ok else st.warning)(f"Backend status: {msg}")

    # ---- Generation ------------------------------------------------------
    st.subheader("2. Generation parameters")
    c1, c2 = st.columns(2)
    config.generation.temperature = c1.slider("Temperature", 0.0, 1.5, float(config.generation.temperature), 0.05)
    config.generation.max_tokens = c2.number_input("Max tokens", 256, 8192, int(config.generation.max_tokens), step=256)
    langs = ["python", "java", "javascript", "typescript", "go", "csharp"]
    config.target_language = st.selectbox(
        "Target implementation language",
        langs,
        index=langs.index(config.target_language) if config.target_language in langs else 0,
        help="Runnable test execution is fully supported for Python; other languages generate code and documents.",
    )

    # ---- Proxy -----------------------------------------------------------
    st.subheader("3. Corporate proxy (only used by the network endpoint)")
    config.proxy.use_system_proxy = st.checkbox("Use system proxy settings", value=config.proxy.use_system_proxy)
    if not config.proxy.use_system_proxy:
        config.proxy.http_proxy = st.text_input("HTTP proxy", value=config.proxy.http_proxy, placeholder="http://proxy:8080")
        config.proxy.https_proxy = st.text_input("HTTPS proxy", value=config.proxy.https_proxy, placeholder="http://proxy:8080")
        config.proxy.no_proxy = st.text_input("No-proxy list", value=config.proxy.no_proxy)

    # ---- Security --------------------------------------------------------
    st.subheader("4. Security & confidentiality")
    config.security.offline_only = st.checkbox(
        "Offline-only mode (block all network backends)",
        value=config.security.offline_only,
        help="When ON, the app cannot make any outbound network call. Recommended for confidential/air-gapped use.",
    )
    config.security.encrypt_artifacts = st.checkbox(
        "Encrypt generated artifacts at rest",
        value=config.security.encrypt_artifacts,
        help="Artifacts are encrypted on disk with a passphrase you enter per run (never stored).",
    )
    if config.security.encrypt_artifacts and not cryptography_available():
        st.warning("`cryptography` not installed — a weaker built-in fallback cipher will be used. Install it for AES-GCM.")

    # ---- Audio -----------------------------------------------------------
    st.subheader("5. Demo narration (offline audio)")
    config.audio.enabled = st.checkbox("Enable English audio narration", value=config.audio.enabled)
    if config.audio.enabled:
        c1, c2 = st.columns(2)
        config.audio.rate_wpm = c1.slider("Speech rate (wpm)", 100, 250, int(config.audio.rate_wpm), 5)
        config.audio.volume = c2.slider("Volume", 0.0, 1.0, float(config.audio.volume), 0.05)
        config.audio.voice = st.text_input("Preferred voice (optional substring)", value=config.audio.voice)
        tok, tmsg = tts_available()
        (st.success if tok else st.info)(tmsg + " (captions are always shown regardless.)")

    st.divider()
    if st.button("💾 Save settings", type="primary"):
        path = config.save()
        st.success(f"Settings saved to {path}")

    return config
