"""Workflow page: capture inputs, run the agent flow, show artifacts + narration."""

from __future__ import annotations

import io
import zipfile

import streamlit as st

from ..agents import AGENT_LABELS, AGENT_ORDER, Orchestrator, analyze_only
from ..analysis import plan_agents
from ..config import AppConfig
from ..languages import get_language, resolve_framework
from ..llm import backend_status


_EXAMPLE_INSTRUCTION = (
    "Build a service that accepts customer orders, validates them, applies "
    "discount rules, stores the processed order and generates a summary report. "
    "It must run fully offline on an edge device and keep all data confidential."
)


def render(config: AppConfig) -> None:
    st.header("🧩 Agentic SDLC Workflow")
    ok, msg = backend_status(config)
    (st.success if ok else st.warning)(f"Active backend: {msg}")

    with st.form("sdlc_inputs"):
        instruction = st.text_area(
            "Instruction (what should the software do?)",
            value=st.session_state.get("instruction", ""),
            placeholder=_EXAMPLE_INSTRUCTION,
            height=120,
        )
        c1, c2 = st.columns(2)
        input_exp = c1.text_area(
            "Input expectations",
            value=st.session_state.get("input_exp", ""),
            placeholder="e.g. JSON order with id, items, customer_id",
            height=110,
        )
        output_exp = c2.text_area(
            "Output expectations",
            value=st.session_state.get("output_exp", ""),
            placeholder="e.g. processed order + summary report; validation report",
            height=110,
        )
        selected = st.multiselect(
            "Agents to run",
            AGENT_ORDER,
            default=AGENT_ORDER,
            format_func=lambda a: AGENT_LABELS[a],
        )
        passphrase = ""
        if config.security.encrypt_artifacts:
            passphrase = st.text_input(
                "Artifact encryption passphrase (not stored)", type="password"
            )
        submitted = st.form_submit_button("▶️ Run agentic flow", type="primary")

    # Live preview of generated roles / tasks / prompts.
    if instruction.strip():
        with st.expander("🔎 Preview: generated roles, tasks & prompts for each agent"):
            spec = analyze_only(config, instruction, input_exp, output_exp)
            fw = resolve_framework(config.target_language, config.test_framework)
            st.caption(
                f"Language: {get_language(config.target_language).display} • "
                f"Unit tests: {fw.display} • Detected operations: {', '.join(spec.operations)}"
            )
            for plan in plan_agents(spec, framework_display=fw.display):
                if plan.agent_id not in selected:
                    continue
                st.markdown(f"**{plan.role_title}** — {plan.role_description}")
                st.markdown("Tasks:\n" + "\n".join(f"- {t}" for t in plan.tasks))
                st.code(plan.prompt, language="text")

    if submitted:
        if not instruction.strip():
            st.error("Please provide an instruction.")
            return
        if config.security.encrypt_artifacts and not passphrase:
            st.error("Encryption is enabled — please enter a passphrase.")
            return
        st.session_state.update(instruction=instruction, input_exp=input_exp, output_exp=output_exp)
        _run_flow(config, instruction, input_exp, output_exp, selected, passphrase)

    if "run_result" in st.session_state:
        _render_results(config)


def _run_flow(config, instruction, input_exp, output_exp, selected, passphrase):
    orch = Orchestrator(config, passphrase=passphrase)
    with st.status("Running agentic SDLC flow…", expanded=True) as status:
        def on_event(kind, data):
            if kind == "analysis":
                spec = data["spec"]
                status.write(f"🧠 Analysed requirements → project **{spec.title}** "
                             f"({len(spec.functional_requirements)} FRs, {len(spec.operations)} operations).")
            elif kind == "agent_start":
                status.write(f"➡️ **{data['label']}** started…")
            elif kind == "agent_done":
                status.write(f"✅ {AGENT_LABELS[data['agent_id']]}: {data['result'].summary}")
            elif kind == "narration_ready":
                status.write("🔊 Narration prepared.")
            elif kind == "complete":
                status.write(f"🎉 Flow complete. Run ID: `{data['run_id']}`")

        result = orch.run(
            instruction, input_exp, output_exp,
            selected_agents=selected, on_event=on_event,
        )
        status.update(label=f"Flow complete — {result.run_id}", state="complete")
    st.session_state["run_result"] = result


def _render_results(config: AppConfig):
    result = st.session_state["run_result"]
    st.divider()
    st.subheader("📦 Results")
    st.caption(f"Run `{result.run_id}` • backend: {result.backend_name} • stored at: `{result.workspace}`")

    tabs = st.tabs([AGENT_LABELS.get(r.agent_id, r.agent_id) for r in result.results] + ["🎬 Demo narration", "⬇️ Download"])

    for tab, res in zip(tabs, result.results):
        with tab:
            st.markdown(f"**Summary:** {res.summary}")
            if res.metrics:
                st.json({k: v for k, v in res.metrics.items() if not k.startswith("_")}, expanded=False)
            for art in res.artifacts:
                _render_artifact(result, art)

    # Narration tab
    with tabs[-2]:
        _render_narration(result)

    # Download tab
    with tabs[-1]:
        _render_downloads(result)


def _render_artifact(result, art):
    with st.expander(f"📄 {art.path}", expanded=(art.kind == "doc")):
        if art.kind == "excel" or art.path.endswith(".xlsx"):
            data = _artifact_bytes(result, art)
            st.download_button("Download Excel report", data, file_name=art.path.split("/")[-1],
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key=f"xl_{art.path}")
            st.caption("Sheets: Summary, Functional, NonFunctional, Architecture, TestResults, CodeQuality.")
        elif art.language == "markdown":
            st.markdown(art.content)
        elif art.kind in ("code", "test"):
            st.code(art.content, language="python" if art.language == "python" else "text")
        else:
            st.text(art.content[:5000])


def _artifact_bytes(result, art) -> bytes:
    if art.is_binary and art.data is not None:
        return art.data
    if result.store is not None:
        try:
            return result.store.read_bytes(art.path)
        except Exception:
            pass
    return art.content.encode("utf-8")


def _render_narration(result):
    st.markdown("Play the narration to follow each step of the agentic flow (English).")
    any_audio = False
    for i, step in enumerate(result.narration, start=1):
        st.markdown(f"**{i}. {step.title}**")
        st.write(step.caption)
        if step.audio_path and result.store is not None:
            try:
                audio_bytes = result.store.read_bytes(step.audio_path)
                st.audio(audio_bytes, format="audio/wav")
                any_audio = True
            except Exception:
                st.caption("(audio unavailable — caption shown above)")
    if not any_audio:
        st.info("Voice narration not synthesized (no offline TTS voice installed). Captions above cover the full flow.")


def _render_downloads(result):
    st.markdown("Download all generated artifacts for this run as a single archive.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in result.results:
            for art in res.artifacts:
                zf.writestr(art.path, _artifact_bytes(result, art))
    st.download_button(
        "⬇️ Download all artifacts (.zip)",
        buf.getvalue(),
        file_name=f"sdlc_{result.run_id}.zip",
        mime="application/zip",
    )
    st.caption(
        "Artifacts are also stored locally under your SDLC_AGENTS_HOME workspace "
        f"({result.workspace})."
    )
