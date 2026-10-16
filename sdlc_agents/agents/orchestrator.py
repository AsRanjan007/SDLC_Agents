"""Pipeline orchestrator.

Runs the selected agents in dependency order (Architect -> Developer ->
Validation Engineer), streaming progress events, persisting artifacts to the
local confidential store, and preparing the offline narration script (and audio,
when a TTS voice is available).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..analysis import ProjectSpec, analyze
from ..artifacts.store import ArtifactStore
from ..audio import build_flow_script, synthesize_step
from ..audio.narration import NarrationStep
from ..config import AppConfig
from ..llm import build_backend
from ..types import AgentResult, Artifact, RunContext
from .architect import ArchitectAgent
from .developer import DeveloperAgent
from .validation_engineer import ValidationEngineerAgent

# Canonical execution order and agent registry.
AGENT_ORDER = ["architect", "developer", "validation_engineer"]
_REGISTRY = {
    "architect": ArchitectAgent,
    "developer": DeveloperAgent,
    "validation_engineer": ValidationEngineerAgent,
}
AGENT_LABELS = {
    "architect": "Software Architect",
    "developer": "Software Developer",
    "validation_engineer": "Validation Engineer",
}


@dataclass
class RunResult:
    run_id: str
    workspace: Path
    backend_name: str
    results: List[AgentResult] = field(default_factory=list)
    narration: List[NarrationStep] = field(default_factory=list)
    store: Optional[ArtifactStore] = None


class Orchestrator:
    def __init__(self, config: AppConfig, passphrase: str = ""):
        self.config = config
        self.passphrase = passphrase
        self.backend = build_backend(config)

    @property
    def backend_name(self) -> str:
        return self.backend.name if self.backend else "offline"

    def run(
        self,
        instruction: str,
        input_expectations: str,
        output_expectations: str,
        selected_agents: Optional[List[str]] = None,
        on_event: Optional[Callable[[str, Dict], None]] = None,
        synthesize_audio: bool = True,
    ) -> RunResult:
        emit = on_event or (lambda *_: None)
        # Make document timestamps use the user's configured timezone (or local).
        from ..util import apply_timezone
        apply_timezone(getattr(self.config, "timezone", ""))
        selected = [a for a in AGENT_ORDER if not selected_agents or a in selected_agents]

        spec = analyze(instruction, input_expectations, output_expectations, self.config.target_language)
        emit("analysis", {"spec": spec})

        store = ArtifactStore(self.config, passphrase=self.passphrase)
        ctx = RunContext(run_id=store.run_id, workspace=store.root, write_artifact=store.write)

        results: List[AgentResult] = []
        for agent_id in selected:
            emit("agent_start", {"agent_id": agent_id, "label": AGENT_LABELS[agent_id]})
            agent = _REGISTRY[agent_id](
                llm=self.backend, generation=self.config.generation, config=self.config
            )
            result = agent.run(spec, results, ctx)
            # Persist any artifacts the agent did not already write.
            store.write_all(result.artifacts)
            results.append(result)
            emit("agent_done", {"agent_id": agent_id, "result": result})

        narration = build_flow_script(spec, results)
        if synthesize_audio and self.config.audio.enabled:
            narration = self._synthesize(narration, store, emit)

        emit("complete", {"run_id": store.run_id})
        return RunResult(
            run_id=store.run_id,
            workspace=store.root,
            backend_name=self.backend_name,
            results=results,
            narration=narration,
            store=store,
        )

    def _synthesize(self, steps: List[NarrationStep], store: ArtifactStore, emit) -> List[NarrationStep]:
        out: List[NarrationStep] = []
        for step in steps:
            rel = f"docs/narration/{step.key}.wav"
            plain_path = store.root / rel
            produced = synthesize_step(step.caption, plain_path, self.config.audio)
            if produced and store.encrypting:
                data = plain_path.read_bytes()
                plain_path.unlink(missing_ok=True)
                store.write(Artifact(path=rel, kind="audio", language="wav", data=data))
                step.audio_path = rel
            elif produced:
                step.audio_path = rel
            out.append(step)
        emit("narration_ready", {"steps": out})
        return out


def analyze_only(config: AppConfig, instruction: str, inp: str, out: str) -> ProjectSpec:
    """Convenience for the UI's live preview of roles/tasks/prompts."""

    return analyze(instruction, inp, out, config.target_language)
