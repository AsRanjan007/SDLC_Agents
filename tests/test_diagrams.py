"""Tests that the Architect always produces the full diagram suite."""

from sdlc_agents.agents.architect import ArchitectAgent, _has_all_diagrams
from sdlc_agents.analysis import analyze
from sdlc_agents.artifacts.store import ArtifactStore
from sdlc_agents.config import AppConfig
from sdlc_agents.llm import offline_engine
from sdlc_agents.llm.base import LLMResponse
from sdlc_agents.types import RunContext

_DIAGRAM_HEADINGS = [
    "### 3.1 Overall Architecture Diagram",
    "### 3.2 Component Diagram",
    "### 3.3 Data Flow Diagram",
    "### 3.4 Sequence Diagram",
    "### 3.5 Use Case Diagram",
]


def _spec():
    return analyze(
        "Build a calculator for +, -, *, /. Validate input and compute the result.",
        "two operands and an operator",
        "result or validation error",
        "python",
    )


def test_render_diagrams_contains_all_five_types():
    out = offline_engine.render_diagrams(_spec())
    for heading in _DIAGRAM_HEADINGS:
        assert heading in out
    assert out.count("```mermaid") == 5
    assert "sequenceDiagram" in out


def test_offline_sad_always_includes_diagram_suite():
    doc = offline_engine.render_architecture_document(_spec())
    for heading in _DIAGRAM_HEADINGS:
        assert heading in doc
    assert doc.count("```mermaid") >= 5


def test_include_diagrams_false_omits_suite():
    doc = offline_engine.render_architecture_document(_spec(), include_diagrams=False)
    assert "```mermaid" not in doc


def _ctx(cfg):
    store = ArtifactStore(cfg)
    return RunContext(run_id=store.run_id, workspace=store.root, write_artifact=store.write)


class FakeLLM:
    name = "fake"

    def __init__(self, text):
        self._text = text

    def available(self):
        return True, "ok"

    def generate(self, system, prompt, max_tokens=2048, temperature=0.2):
        return LLMResponse(text=self._text, backend="fake", model="fake")


def test_llm_sad_without_diagrams_gets_them_appended():
    # A plausible-but-diagramless SAD from the model.
    doc = "# Software Architecture Document\n\n## Intro\n" + ("Lots of prose. " * 60) + "\n## More\n### Sub\ntext\n"
    cfg = AppConfig()
    cfg.backend = "openai_compat"
    cfg.audio.enabled = False
    agent = ArchitectAgent(llm=FakeLLM(doc), config=cfg)
    res = agent.run(_spec(), [], _ctx(cfg))
    sad = res.artifacts[0].content
    assert not _has_all_diagrams(doc)        # model output lacked them
    assert _has_all_diagrams(sad)            # agent guaranteed them
    for heading in _DIAGRAM_HEADINGS:
        assert heading in sad
    assert "diagrams validated" in res.metrics["source"]


def test_has_all_diagrams_detects_complete_suite():
    assert _has_all_diagrams(offline_engine.render_diagrams(_spec()) + " use case")
    assert not _has_all_diagrams("no diagrams here")


# A SAD whose Mermaid reproduces the three real parse errors seen in the app.
_BROKEN_LLM_SAD = """# Software Architecture Document

## 6. Architecture Diagrams

### 6.1 Overall Architecture Diagram
```mermaid
graph TD
    A[User] --> D[Core Service (Business Logic)];
```

### 6.3 Data Flow Diagram (DFD)
```mermaid
graph TD
    A[Raw Input: (A, Op, B)] --> B(Input Layer);
```

### 6.5 Use Case Diagram
```mermaid
graph TD
    actor User
    rectangle C
```
"""


def test_sanitizer_replaces_broken_llm_mermaid_with_valid_blocks():
    fixed = offline_engine.sanitize_llm_diagrams(_BROKEN_LLM_SAD, _spec())
    # The invalid constructs are gone.
    assert "D[Core Service (Business Logic)]" not in fixed
    assert "Raw Input: (A, Op, B)" not in fixed
    assert "rectangle C" not in fixed            # invented flowchart syntax
    assert "graph TD\n    actor" not in fixed    # 'actor' is only valid in sequenceDiagram
    # Replaced by valid, quoted deterministic diagrams + the missing types added.
    assert fixed.count("```mermaid") == 5
    assert "sequenceDiagram" in fixed
    # No unquoted parentheses inside flowchart square-bracket labels remain
    # (the cylinder shape `[("...")]` is excluded — it is valid Mermaid).
    import re as _re
    assert not _re.search(r"\[[^\"\]\n(]+\([^)\n]*\)[^\]\n]*\]", fixed)


def test_sanitizer_appends_suite_when_no_mermaid_present():
    doc = "# SAD\n\n## Overview\nSome prose only, no diagrams.\n"
    fixed = offline_engine.sanitize_llm_diagrams(doc, _spec())
    assert fixed.count("```mermaid") == 5
    assert "## Architecture Diagrams" in fixed
