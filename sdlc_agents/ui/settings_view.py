"""Settings page: configure the LLM backend, proxy, security and audio."""

from __future__ import annotations

import streamlit as st

from ..config import AppConfig
from ..languages import LANGUAGE_ORDER, framework_choices, get_language, normalize_language
from ..llm import backend_status
from ..audio import tts_available
from ..security import cryptography_available

DETAIL_LEVELS = ["brief", "standard", "detailed"]


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

    # ---- Language & test framework --------------------------------------
    st.subheader("3. Target language & unit-test framework")
    langs = list(LANGUAGE_ORDER)
    current_lang = normalize_language(config.target_language)
    c1, c2 = st.columns(2)
    config.target_language = c1.selectbox(
        "Target implementation language",
        langs,
        index=langs.index(current_lang) if current_lang in langs else 0,
        format_func=lambda k: get_language(k).display,
        help="The Developer agent generates idiomatic code and the chosen test framework for this language.",
    )
    choices = framework_choices(config.target_language)  # [(id, display), ...]
    fw_ids = [c[0] for c in choices]
    fw_labels = {c[0]: c[1] for c in choices}
    # Reset a stale framework selection when it does not apply to the language.
    if config.test_framework not in fw_ids:
        config.test_framework = fw_ids[0]
    config.test_framework = c2.selectbox(
        "Unit-test framework",
        fw_ids,
        index=fw_ids.index(config.test_framework),
        format_func=lambda k: fw_labels[k],
        help="cargo test (Rust), JUnit (Java), Kotest (Kotlin), GoogleTest (C/C++), pytest/unittest (Python).",
    )
    if get_language(config.target_language).runnable_in_process:
        st.caption("✅ Tests for this language run in-process on any device.")
    else:
        st.caption(
            f"ℹ️ Generated tests use a real {get_language(config.target_language).manifest_name} project. "
            "They execute when the language toolchain is installed; otherwise they are reported as skipped."
        )

    config.timezone = st.text_input(
        "Document timezone (IANA name, optional)",
        value=config.timezone,
        placeholder="e.g. Asia/Kolkata, America/New_York — blank uses the system local time",
        help="Timestamps in the generated documents and reports use this timezone. "
             "Set it when the app runs in a container whose clock is UTC.",
    ).strip()
    from ..util import now_str
    st.caption(f"🕒 Current document timestamp: **{now_str(config.timezone)}**")

    # ---- Per-agent configuration ----------------------------------------
    st.subheader("4. Agent configuration")
    _render_agent_config(config)

    # ---- Proxy -----------------------------------------------------------
    st.subheader("5. Corporate proxy (only used by the network endpoint)")
    config.proxy.use_system_proxy = st.checkbox("Use system proxy settings", value=config.proxy.use_system_proxy)
    if not config.proxy.use_system_proxy:
        config.proxy.http_proxy = st.text_input("HTTP proxy", value=config.proxy.http_proxy, placeholder="http://proxy:8080")
        config.proxy.https_proxy = st.text_input("HTTPS proxy", value=config.proxy.https_proxy, placeholder="http://proxy:8080")
        config.proxy.no_proxy = st.text_input("No-proxy list", value=config.proxy.no_proxy)

    # ---- Security --------------------------------------------------------
    st.subheader("6. Security & confidentiality")
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
    st.subheader("7. Demo narration (offline audio)")
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


def _render_agent_config(config: AppConfig) -> None:
    """Per-agent options that steer what each agent generates and validates."""

    agents = config.agents

    with st.expander("🏛️ Software Architect", expanded=False):
        a = agents.architect
        a.detail_level = st.select_slider(
            "Document detail level",
            options=DETAIL_LEVELS,
            value=a.detail_level if a.detail_level in DETAIL_LEVELS else "standard",
            help="How much depth the Software Architecture Document carries.",
        )
        c1, c2, c3 = st.columns(3)
        a.include_diagrams = c1.checkbox("Context diagrams", value=a.include_diagrams)
        a.include_adrs = c2.checkbox("Decision records (ADRs)", value=a.include_adrs)
        a.include_risks = c3.checkbox("Risk register", value=a.include_risks)

    with st.expander("👩‍💻 Software Developer", expanded=False):
        d = agents.developer
        c1, c2 = st.columns(2)
        d.generate_unit_tests = c1.checkbox("Generate unit tests", value=d.generate_unit_tests)
        d.generate_integration_tests = c2.checkbox("Generate integration tests", value=d.generate_integration_tests)
        c3, c4 = st.columns(2)
        d.include_build_manifest = c3.checkbox(
            "Include build manifest", value=d.include_build_manifest,
            help="Cargo.toml / pom.xml / build.gradle.kts / CMakeLists.txt / pyproject.toml.",
        )
        d.run_tests = c4.checkbox(
            "Run tests after generating", value=d.run_tests,
            help="Executes the suite when the language toolchain is available.",
        )

    with st.expander("🔎 Validation Engineer", expanded=False):
        v = agents.validation
        c1, c2 = st.columns(2)
        v.run_tests = c1.checkbox("Independently re-run tests", value=v.run_tests)
        v.static_security_scan = c2.checkbox(
            "Static security scan", value=v.static_security_scan,
            help="Scans generated code for networking APIs to verify offline/confidentiality NFRs.",
        )
        c3, c4 = st.columns(2)
        v.check_coverage = c3.checkbox("Check test:code coverage ratio", value=v.check_coverage)
        v.excel_report = c4.checkbox("Emit Excel validation workbook", value=v.excel_report)
