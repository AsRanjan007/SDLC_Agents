"""LLM-mode (e.g. local Ollama) robustness tests for the Developer agent.

A fake backend stands in for a local OpenAI-compatible endpoint so we can assert
the agent verifies model output with the real per-language toolchain and recovers
when that output does not build/pass.
"""

from sdlc_agents.agents.developer import DeveloperAgent
from sdlc_agents.analysis import analyze
from sdlc_agents.artifacts.store import ArtifactStore
from sdlc_agents.config import AppConfig
from sdlc_agents.languages import get_language, resolve_framework
from sdlc_agents.llm.base import LLMResponse
from sdlc_agents.types import RunContext


class FakeLLM:
    name = "fake"

    def __init__(self, text: str):
        self._text = text

    def available(self):
        return True, "fake ready"

    def generate(self, system, prompt, max_tokens=2048, temperature=0.2):
        return LLMResponse(text=self._text, backend="fake", model="fake")


def _ctx(cfg):
    store = ArtifactStore(cfg)
    return RunContext(run_id=store.run_id, workspace=store.root, write_artifact=store.write)


def _cfg(language="python", framework="auto"):
    cfg = AppConfig()
    cfg.backend = "openai_compat"  # pretend a local Ollama endpoint is configured
    cfg.audio.enabled = False
    cfg.target_language = language
    cfg.test_framework = framework
    return cfg


_PASSING_PY = """\
=== FILE: src/app/core.py ===
VALUE = 42
=== END FILE ===
=== FILE: tests/unit/test_value.py ===
def test_value():
    assert True
=== END FILE ===
"""

_FAILING_PY = """\
=== FILE: src/app/core.py ===
VALUE = 1
=== END FILE ===
=== FILE: tests/unit/test_broken.py ===
def test_broken():
    assert False
=== END FILE ===
"""


def test_llm_python_output_is_executed_with_pytest_and_kept_when_green():
    cfg = _cfg("python", "pytest")
    agent = DeveloperAgent(llm=FakeLLM(_PASSING_PY), config=cfg)
    spec = analyze("Process records.", "record", "report", "python")
    res = agent.run(spec, [], _ctx(cfg))
    assert res.metrics["source"].startswith("LLM (")
    assert res.metrics["test_status"] == "passed"
    assert res.metrics["tests_passed"] >= 1


def test_llm_python_failing_output_falls_back_to_scaffold_and_passes():
    cfg = _cfg("python", "pytest")
    agent = DeveloperAgent(llm=FakeLLM(_FAILING_PY), config=cfg)
    spec = analyze("Process records.", "record", "report", "python")
    res = agent.run(spec, [], _ctx(cfg))
    # The model's code failed verification, so the robust path fell back.
    assert "fell back" in res.metrics["source"]
    assert res.metrics["test_status"] == "passed"
    assert res.metrics["tests_failed"] == 0


def test_llm_garbage_output_is_rejected_before_execution():
    cfg = _cfg("python", "pytest")
    agent = DeveloperAgent(llm=FakeLLM("no file blocks here, just prose"), config=cfg)
    spec = analyze("Process records.", "record", "report", "python")
    res = agent.run(spec, [], _ctx(cfg))
    assert res.metrics["source"] == "offline engine"
    assert res.metrics["test_status"] == "passed"


def test_ensure_runnable_backfills_missing_manifest_for_rust():
    cfg = _cfg("rust", "cargo-test")
    agent = DeveloperAgent(llm=FakeLLM(""), config=cfg)
    spec = analyze("Process records.", "record", "report", "rust")
    profile = get_language("rust")
    framework = resolve_framework("rust", "cargo-test")
    # Model emitted source but forgot Cargo.toml.
    from sdlc_agents.types import Artifact
    partial = [Artifact(path="src/lib.rs", content="pub fn x() -> i32 { 1 }\n", kind="code", language="rust")]
    completed = agent._ensure_runnable(partial, spec, profile, framework)
    assert any(a.path == "Cargo.toml" for a in completed)
