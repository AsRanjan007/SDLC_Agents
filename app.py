"""SDLC Agents — Streamlit entrypoint.

Run with:  streamlit run app.py

A fully offline, edge-friendly multi-agent workbench that turns plain-language
instructions into architecture, code, tests and validation reports. No external
communication is required or performed by the core flow.
"""

from __future__ import annotations

import os

# Belt-and-braces: disable Streamlit telemetry before importing it.
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import streamlit as st  # noqa: E402

from sdlc_agents import __version__  # noqa: E402
from sdlc_agents.config import home_dir, load_config  # noqa: E402
from sdlc_agents.llm import backend_status  # noqa: E402
from sdlc_agents.ui import settings_view, workflow_view  # noqa: E402


st.set_page_config(page_title="SDLC Agents", page_icon="🤖", layout="wide")


def _init_config():
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    return st.session_state["config"]


def main():
    config = _init_config()

    with st.sidebar:
        st.title("🤖 SDLC Agents")
        st.caption(f"v{__version__} • offline • edge-ready")
        page = st.radio("Navigate", ["Workflow", "Settings", "About"], label_visibility="collapsed")

        st.divider()
        ok, msg = backend_status(config)
        st.markdown("**Backend**")
        (st.success if ok else st.warning)(msg)
        st.markdown("**Security**")
        st.write("🔒 Offline-only" if config.security.offline_only else "🌐 Network allowed")
        st.write("🔐 Artifact encryption ON" if config.security.encrypt_artifacts else "📂 Artifacts stored locally")
        st.caption(f"Home: `{home_dir()}`")

    if page == "Workflow":
        workflow_view.render(config)
    elif page == "Settings":
        st.session_state["config"] = settings_view.render(config)
    else:
        _about()


def _about():
    st.header("About SDLC Agents")
    st.markdown(
        """
This app runs a small **multi-agent software delivery flow** entirely on your
device:

| Agent | Produces |
|-------|----------|
| 🏛️ **Software Architect** | Software Architecture Document (SAD) |
| 👩‍💻 **Software Developer** | Component design, source code, unit + integration tests, build report |
| 🔎 **Validation Engineer** | Functional & non-functional verification, architecture/design validation, **Excel validation report** |

**Design principles**
- **Fully offline** — the core flow performs *no* external communication.
- **Edge-ready** — deterministic engine needs no model; optionally plug in a
  local GGUF model or a local OpenAI-compatible endpoint.
- **Corporate-network friendly** — proxy-aware for the optional endpoint.
- **Confidential by default** — artifacts are stored locally with owner-only
  permissions and optional at-rest encryption.
- **Explainable** — an embedded English narration walks viewers through the flow.

Configure everything under **Settings**; run flows under **Workflow**.
        """
    )
    ok, msg = backend_status(st.session_state["config"])
    st.info(f"Current backend: {msg}")


if __name__ == "__main__":
    main()
