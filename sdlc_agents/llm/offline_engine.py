"""Deterministic offline artifact renderer.

Given a :class:`~sdlc_agents.analysis.ProjectSpec`, this module renders real,
runnable artifacts with **no model and no network**: a Software Architecture
Document, component design, source code, unit tests, integration tests and a
developer build report. The generated Python is syntactically valid and its
tests pass, so the Validation Engineer can execute them for real.

Templates use simple ``__TOKEN__`` placeholders (not ``str.format``) to avoid
brace-escaping in the generated code bodies.
"""

from __future__ import annotations

import datetime as _dt
import keyword
import re
from typing import List, Optional

from ..analysis import ProjectSpec
from ..types import Artifact


# ---------------------------------------------------------------------------
# naming helpers
# ---------------------------------------------------------------------------


def pkg_name(spec: ProjectSpec) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", spec.slug.lower()).strip("_") or "app"
    if name[0].isdigit() or keyword.iskeyword(name):
        name = f"app_{name}"
    return name


def class_name(spec: ProjectSpec) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", spec.title) if p]
    camel = "".join(p[:1].upper() + p[1:] for p in parts) or "App"
    if camel[0].isdigit():
        camel = "App" + camel
    return camel + "Service"


def _ident(name: str) -> str:
    ident = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "op"
    if ident[0].isdigit() or keyword.iskeyword(ident):
        ident = f"op_{ident}"
    return ident


def _operation_idents(spec: ProjectSpec) -> List[str]:
    seen: List[str] = []
    for op in spec.operations:
        ident = _ident(op)
        # 'process' / 'report' / 'validate_input' are reserved built-in methods.
        if ident in {"process", "report", "validate_input"} or ident in seen:
            continue
        seen.append(ident)
    return seen or ["handle_request"]


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Architect artifact
# ---------------------------------------------------------------------------


def _mm_label(text: str) -> str:
    """Mermaid-safe label: drop quotes/brackets that break node syntax."""

    return re.sub(r'[\"\[\]{}()|<>]', "", text).strip() or "Component"


def _find_component(comps, *keywords):
    """Return (id, name) of the first component matching any keyword, or None."""

    for i, c in enumerate(comps, start=1):
        low = c.lower()
        if any(k in low for k in keywords):
            return f"C{i}", c
    return None


def _build_diagram_blocks(spec: ProjectSpec) -> dict:
    """Build the five Mermaid diagrams (+ an ASCII overview) as a dict of blocks.

    Every node label is quoted so parentheses, colons, commas and other special
    characters in component/operation names can never break the Mermaid parser.
    """

    comps = spec.components or [
        "Input/Interface Layer", "Core Service (business logic)", "Domain Model",
        "Validation & Rules Engine", "Persistence/Artifact Store", "Reporting Module",
    ]
    ops = spec.operations or ["process_request", "validate_input", "build_report"]

    interface = _find_component(comps, "interface", "input", "ui", "api")
    core = _find_component(comps, "core", "service", "logic", "engine") or ("C1", comps[0])
    validation = _find_component(comps, "valid", "rule")
    domain = _find_component(comps, "domain", "model")
    persistence = _find_component(comps, "persist", "store", "repository", "database")
    reporting = _find_component(comps, "report", "output")

    def fence(lines) -> str:
        return "```mermaid\n" + "\n".join(lines) + "\n```\n"

    # --- Overall architecture (ASCII + Mermaid) ---------------------------
    ascii_box = (
        "```\n"
        "          +--------------------------+\n"
        "  User -> |  Interface / Input Layer |\n"
        "          +------------+-------------+\n"
        "                       v\n"
        "          +--------------------------+\n"
        "          |   Core Service (logic)   |\n"
        "          +--+--------+--------+-----+\n"
        "             v        v        v\n"
        "        Validation  Domain   Persistence\n"
        "             \\        |        /\n"
        "              v       v       v\n"
        "          +--------------------------+\n"
        "          |     Reporting Module     | -> Artifacts (local, confidential)\n"
        "          +--------------------------+\n"
        "```\n"
    )
    overall = ["flowchart LR", '    User(["User"])']
    for i, c in enumerate(comps, start=1):
        overall.append(f'    C{i}["{_mm_label(c)}"]')
    if interface:
        overall.append(f"    User --> {interface[0]}")
        overall.append(f"    {interface[0]} --> {core[0]}")
    else:
        overall.append(f"    User --> {core[0]}")
    for role in (validation, domain, persistence, reporting):
        if role and role[0] != core[0]:
            overall.append(f"    {core[0]} --> {role[0]}")
    sink = reporting[0] if reporting else core[0]
    overall.append(f'    {sink} --> Out(["Local, confidential artifacts"])')

    # --- Component diagram ------------------------------------------------
    comp_lines = ["flowchart TB"]
    for i, c in enumerate(comps, start=1):
        comp_lines.append(f'    C{i}["{_mm_label(c)}"]')
    if interface:
        comp_lines.append(f"    {interface[0]} -->|requests| {core[0]}")
    for role in (validation, domain, persistence, reporting):
        if role and role[0] != core[0]:
            comp_lines.append(f"    {core[0]} -->|uses| {role[0]}")
    if reporting and persistence and reporting[0] != persistence[0]:
        comp_lines.append(f"    {reporting[0]} -->|reads| {persistence[0]}")

    # --- Data flow diagram ------------------------------------------------
    op_valid = next((o for o in ops if "valid" in o.lower()), "validate")
    op_main = next((o for o in ops if o.lower() != op_valid.lower()), ops[0])
    flow = [
        "flowchart LR",
        '    IN(["Input data"])',
        f'    V["{_mm_label(op_valid)}"]',
        f'    P["{_mm_label(op_main)} / process"]',
        '    S[("Local store")]',
        '    R["Report"]',
        '    OUT(["Result or error"])',
        "    IN --> V",
        "    V -->|valid| P",
        "    V -->|invalid| OUT",
        "    P --> S",
        "    P --> R",
        "    R --> OUT",
    ]

    # --- Sequence diagram -------------------------------------------------
    sequence = [
        "sequenceDiagram",
        "    actor User",
        "    participant UI as Interface Layer",
        "    participant Core as Core Service",
        "    participant Val as Validation and Rules",
        "    participant Store as Persistence",
        "    participant Rep as Reporting",
        "    User->>UI: submit input",
        "    UI->>Core: process(input)",
        "    Core->>Val: validate(input)",
        "    Val-->>Core: ok or errors",
        "    alt input valid",
        "        Core->>Store: persist(record)",
        "        Store-->>Core: stored",
        "        Core->>Rep: summarise()",
        "        Rep-->>Core: report",
        "        Core-->>UI: result",
        "    else input invalid",
        "        Core-->>UI: validation error",
        "    end",
        "    UI-->>User: result or error",
    ]

    # --- Use case diagram (valid flowchart, not invented syntax) ----------
    uc = ["flowchart LR", '    User(["User"])']
    for i, o in enumerate(ops[:6], start=1):
        uc.append(f'    UC{i}(["{_mm_label(o.replace("_", " "))}"])')
        uc.append(f"    User --> UC{i}")

    return {
        "ascii": ascii_box,
        "overall": fence(overall),
        "component": fence(comp_lines),
        "dataflow": fence(flow),
        "sequence": fence(sequence),
        "usecase": fence(uc),
    }


def render_diagrams(spec: ProjectSpec) -> str:
    """Render the full architecture diagram suite as Mermaid + ASCII.

    Produces five diagrams grounded in the project's components and operations:
    overall architecture, component, data flow, sequence and use case. Everything
    is deterministic and offline, so the SAD always contains them regardless of
    whether an LLM is in use.
    """

    b = _build_diagram_blocks(spec)
    return (
        "### 3.1 Overall Architecture Diagram\n"
        "A plain-text overview (renders everywhere) followed by a Mermaid diagram:\n\n"
        + b["ascii"] + "\n" + b["overall"] + "\n"
        + "### 3.2 Component Diagram\n"
        "Components and their dependencies:\n\n" + b["component"] + "\n"
        + "### 3.3 Data Flow Diagram\n"
        "How data moves from input to validated output and reports:\n\n" + b["dataflow"] + "\n"
        + "### 3.4 Sequence Diagram\n"
        "The runtime interaction for a typical request:\n\n" + b["sequence"] + "\n"
        + "### 3.5 Use Case Diagram\n"
        "The actor and the use cases derived from the requirements:\n\n" + b["usecase"]
    )


_DIAGRAM_ORDER = ["overall", "component", "dataflow", "sequence", "usecase"]


def _classify_diagram(heading: str) -> Optional[str]:
    low = heading.lower()
    if "use case" in low or "use-case" in low or "usecase" in low:
        return "usecase"
    if "sequence" in low:
        return "sequence"
    if "data flow" in low or "dataflow" in low or "data-flow" in low or "dfd" in low:
        return "dataflow"
    if "component" in low:
        return "component"
    if "overall" in low or "high-level" in low or "high level" in low or "architecture diagram" in low:
        return "overall"
    return None


def _find_mermaid_ranges(lines: List[str]):
    """Return (start, end) line ranges of every ```mermaid block.

    Robust to malformed input: an unterminated fence runs to the next fence (or
    end of document), so a missing closing ``` can never swallow later content.
    """

    ranges = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].lstrip().startswith("```mermaid"):
            j = i + 1
            while j < n and not lines[j].lstrip().startswith("```"):
                j += 1
            end = j + 1 if j < n else n  # include the closing fence when present
            ranges.append((i, end))
            i = end
        else:
            i += 1
    return ranges


def sanitize_llm_diagrams(doc: str, spec: ProjectSpec) -> str:
    """Replace Mermaid blocks in an LLM-authored SAD with valid, known-good ones.

    LLMs frequently emit Mermaid that does not parse (unquoted labels with
    parentheses/colons, invented ``actor``/``rectangle`` keywords in flowcharts,
    or even an unterminated code fence). Rather than trust them, this works
    line-by-line: every ``mermaid`` block is located (even unterminated ones) and
    swapped — classified by its nearest preceding heading, falling back to
    document order — for the deterministic block of the same type. Any diagram
    type that never appeared is appended. Because every block emitted here is
    properly fenced, the result can never contain a dangling code fence.
    """

    blocks = _build_diagram_blocks(spec)
    lines = doc.split("\n")
    ranges = _find_mermaid_ranges(lines)
    if not ranges:
        return doc.rstrip() + "\n\n## Architecture Diagrams\n" + render_diagrams(spec)

    def heading_before(start: int) -> str:
        for k in range(start - 1, -1, -1):
            s = lines[k].strip()
            if s.startswith("#"):
                return s
        return ""

    used: set = set()
    kinds = []
    for (start, _end) in ranges:
        kind = _classify_diagram(heading_before(start))
        if kind is None or kind in used:
            kind = next((k for k in _DIAGRAM_ORDER if k not in used), None)
        kinds.append(kind)
        if kind:
            used.add(kind)

    out: List[str] = []
    cursor = 0
    for (start, end), kind in zip(ranges, kinds):
        out.extend(lines[cursor:start])
        if kind and blocks.get(kind):
            out.extend(blocks[kind].rstrip("\n").split("\n"))
        else:
            out.extend(lines[start:end])
        cursor = end
    out.extend(lines[cursor:])
    result = "\n".join(out)

    missing = [k for k in _DIAGRAM_ORDER if k not in used]
    if missing:
        extra = "\n".join(blocks[k].rstrip("\n") for k in missing)
        result = result.rstrip() + "\n\n### Additional Diagrams\n\n" + extra + "\n"
    return result


def render_architecture_document(
    spec: ProjectSpec,
    *,
    framework_display: str | None = None,
    detail_level: str = "standard",
    include_diagrams: bool = True,
    include_risks: bool = True,
    include_adrs: bool = True,
) -> str:
    """Render the Software Architecture Document.

    The keyword arguments mirror the Architect agent's configuration so the
    document reflects the user's choices (target test framework, level of
    detail, and whether to include context diagrams, ADRs and a risk register).
    """

    comp_rows = "\n".join(
        f"| C{i+1} | {c} | Responsible for the '{c.split('(')[0].strip().lower()}' concern. |"
        for i, c in enumerate(spec.components)
    )
    nfr_rows = "\n".join(
        f"| NFR-{i+1} | {n} | {_tactic_for(n)} |"
        for i, n in enumerate(spec.nonfunctional_requirements)
    )
    fr_list = "\n".join(f"- **FR-{i+1}**: {r}" for i, r in enumerate(spec.functional_requirements))
    op_list = ", ".join(f"`{o}`" for o in spec.operations)
    framework_line = f"\nUnit-test framework: **{framework_display}**." if framework_display else ""

    parts: List[str] = [
        f"# Software Architecture Document\n## {spec.title}\n\n"
        f"*Generated by the Architect agent on {_now()} — offline, on-device.*\n"
    ]

    if detail_level != "brief":
        parts.append(
            "## 1. Introduction\n### 1.1 Purpose\n"
            "This document describes the software architecture for "
            f"**{spec.title}**. It is derived from the supplied instruction and "
            "input/output expectations and is the authoritative reference for the "
            "Software Developer and Validation Engineer agents.\n\n"
            f"### 1.2 Scope\n{spec.summary}\n\n"
            f"Target implementation language: **{spec.language}**.{framework_line}\n"
        )
    else:
        parts.append(
            f"## 1. Overview\n{spec.summary}\n\n"
            f"Target implementation language: **{spec.language}**.{framework_line}\n"
        )

    parts.append(
        "## 2. Architectural Goals & Constraints\n"
        "- The system must operate **fully offline** on edge hardware.\n"
        "- It must work inside a corporate network behind an HTTP proxy.\n"
        "- All generated artifacts must remain **confidential and local**.\n"
        "- No external communication is permitted for core functionality.\n"
    )

    if include_diagrams:
        parts.append("## 3. Architecture Diagrams\n" + render_diagrams(spec))

    parts.append(
        "## 4. Logical Component View\n"
        "| ID | Component | Responsibility |\n"
        "|----|-----------|----------------|\n"
        f"{comp_rows}\n"
    )

    parts.append(
        "## 5. Key Operations\n"
        "The core service exposes these operations derived from the "
        f"requirements:\n{op_list}.\n"
    )

    if include_diagrams:
        parts.append(
            "## 6. Data Flow\n"
            "1. Input is received by the Input/Interface Layer and validated.\n"
            "2. The Core Service applies the business rules and executes operations.\n"
            "3. Results are persisted to the local Artifact Store.\n"
            "4. The Reporting Module summarises outcomes for the user.\n"
        )

    parts.append(f"## 7. Functional Requirements\n{fr_list}\n")

    parts.append(
        "## 8. Quality Attributes (Non-Functional Requirements)\n"
        "| ID | Requirement | Architectural Tactic |\n"
        "|----|-------------|----------------------|\n"
        f"{nfr_rows}\n"
    )

    if include_adrs:
        parts.append(
            "## 9. Architecture Decisions\n"
            "- **AD-1**: Layered architecture (interface / core / model / "
            "persistence) for testability and clear separation of concerns.\n"
            "- **AD-2**: Deterministic, dependency-light core so it runs on "
            "constrained edge devices without external services.\n"
            "- **AD-3**: All I/O confined to the local device; optional at-rest "
            "encryption for artifact confidentiality.\n"
        )

    if include_risks:
        parts.append(
            "## 10. Risks & Mitigations\n"
            "- *Risk*: Limited edge compute. *Mitigation*: keep the core "
            "lightweight and avoid heavy runtime dependencies.\n"
            "- *Risk*: Data leakage. *Mitigation*: enforce offline-only mode and "
            "local-only artifact storage with restrictive permissions.\n"
        )

    if detail_level == "detailed":
        parts.append(
            "## 10a. Detailed Design Considerations\n"
            "- Each component exposes a narrow, testable interface.\n"
            "- Inputs are validated at the boundary before any processing.\n"
            "- Operations are recorded to an audit trail for traceability.\n"
        )

    parts.append(
        "## 11. Traceability\n"
        "Every functional requirement (FR-x) maps to one or more operations, and "
        "each is verified by the Validation Engineer's report.\n"
    )

    return "\n".join(parts)


def _tactic_for(nfr: str) -> str:
    low = nfr.lower()
    if "offline" in low or "network" in low:
        return "No network calls in the core; offline-only guard enforced."
    if "edge" in low or "footprint" in low:
        return "Minimal dependencies; pure-Python core."
    if "proxy" in low:
        return "Proxy-aware configuration; core needs no network."
    if "confidential" in low or "privacy" in low or "secure" in low or "encrypt" in low:
        return "Local-only storage, owner-only permissions, optional encryption."
    if "perform" in low or "latency" in low or "throughput" in low:
        return "Streaming/iterative processing; O(n) operations."
    if "reliab" in low or "availab" in low:
        return "Input validation and graceful error handling."
    return "Addressed via design review and validation checks."


# ---------------------------------------------------------------------------
# Developer artifacts
# ---------------------------------------------------------------------------


def render_component_design(spec: ProjectSpec) -> str:
    cls = class_name(spec)
    pkg = pkg_name(spec)
    ops = _operation_idents(spec)
    op_doc = "\n".join(f"- `{cls}.{o}(payload)` — records and returns the '{o}' outcome." for o in ops)
    return f"""# Component Design
## {spec.title}

*Generated by the Software Developer agent on {_now()}.*

## Package Layout
```
src/{pkg}/
    __init__.py
    models.py     # Record, Result data models
    core.py       # {cls} business logic
tests/
    unit/test_core.py
    integration/test_integration.py
```

## Public Interface: `{cls}`
- `validate_input(data) -> list[str]` — returns validation errors (empty = valid).
- `process(data) -> Result` — main pipeline: validate, build a Record, audit.
- `report() -> dict` — aggregate operation statistics.
- `audit_log` — immutable view of every recorded operation.
{op_doc}

## Data Models
- `Record(id, payload, status)` — a processed unit of work.
- `Result(ok, errors, record)` — the outcome of `process`.

## Design Notes
The component is deterministic and side-effect free apart from its in-memory
audit log, which makes it trivially unit-testable and safe for edge devices.
"""


def render_source_files(spec: ProjectSpec) -> List[Artifact]:
    cls = class_name(spec)
    pkg = pkg_name(spec)
    ops = _operation_idents(spec)

    init_py = f'"""Package for {spec.title} (auto-generated)."""\n\nfrom .core import {cls}\nfrom .models import Record, Result\n\n__all__ = ["{cls}", "Record", "Result"]\n'

    models_py = (
        '"""Data models (auto-generated by the Software Developer agent)."""\n\n'
        "from __future__ import annotations\n\n"
        "from dataclasses import dataclass\n"
        "from typing import Any, List, Optional\n\n\n"
        "@dataclass\n"
        "class Record:\n"
        '    """A processed unit of work."""\n\n'
        "    id: str\n"
        "    payload: Any\n"
        '    status: str = "new"\n\n\n'
        "@dataclass\n"
        "class Result:\n"
        '    """The outcome of a processing call."""\n\n'
        "    ok: bool\n"
        "    errors: List[str]\n"
        "    record: Optional[Record]\n"
    )

    op_methods = ""
    for op in ops:
        op_methods += _OP_METHOD_TEMPLATE.replace("__OP__", op)

    core_py = (
        _CORE_TEMPLATE.replace("__TITLE__", spec.title)
        .replace("__CLASS__", cls)
        .replace("__OP_METHODS__", op_methods)
    )

    return [
        Artifact(path=f"src/{pkg}/__init__.py", content=init_py, kind="code", language="python"),
        Artifact(path=f"src/{pkg}/models.py", content=models_py, kind="code", language="python"),
        Artifact(path=f"src/{pkg}/core.py", content=core_py, kind="code", language="python"),
        Artifact(path="conftest.py", content=_CONFTEST, kind="code", language="python"),
    ]


_OP_METHOD_TEMPLATE = '''
    def __OP__(self, payload: Any = None) -> Dict[str, Any]:
        """Operation '__OP__' derived from the requirements."""
        return self._record("__OP__", payload)
'''


_CORE_TEMPLATE = '''"""Core service for __TITLE__.

Auto-generated by the SDLC Agents Software Developer agent. Deterministic,
dependency-light and fully offline.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import Record, Result


class __CLASS__:
    """Business logic for __TITLE__.

    Every operation is written to an in-memory audit log so the Validation
    Engineer can trace and verify behaviour.
    """

    def __init__(self) -> None:
        self._audit: List[Dict[str, Any]] = []

    @property
    def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit)

    def validate_input(self, data: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(data, dict):
            return ["input must be a mapping"]
        if "id" not in data:
            errors.append("missing required field: id")
        if "payload" not in data:
            errors.append("missing required field: payload")
        return errors

    def _record(self, operation: str, payload: Any) -> Dict[str, Any]:
        entry = {"operation": operation, "payload": payload, "ok": True}
        self._audit.append(entry)
        return entry
__OP_METHODS__
    def process(self, data: Dict[str, Any]) -> Result:
        errors = self.validate_input(data)
        if errors:
            return Result(ok=False, errors=errors, record=None)
        record = Record(id=str(data["id"]), payload=data["payload"], status="processed")
        self._record("process", data.get("id"))
        return Result(ok=True, errors=[], record=record)

    def report(self) -> Dict[str, Any]:
        by_op: Dict[str, int] = {}
        for entry in self._audit:
            by_op[entry["operation"]] = by_op.get(entry["operation"], 0) + 1
        return {"total_operations": len(self._audit), "by_operation": by_op}
'''


_CONFTEST = (
    '"""Test bootstrap: make the src/ package importable (auto-generated)."""\n\n'
    "import os\n"
    "import sys\n\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), \"src\"))\n"
)


def render_unit_tests(spec: ProjectSpec) -> List[Artifact]:
    cls = class_name(spec)
    pkg = pkg_name(spec)
    ops = _operation_idents(spec)
    first_op = ops[0]
    op_tests = ""
    for op in ops[:3]:
        op_tests += (
            f"\n\ndef test_{op}_records_audit():\n"
            f"    svc = {cls}()\n"
            f"    svc.{op}({{\"k\": \"v\"}})\n"
            f"    assert svc.audit_log[-1][\"operation\"] == \"{op}\"\n"
        )
    content = f'''"""Unit tests for {spec.title} (auto-generated)."""

from {pkg}.core import {cls}


def test_validate_input_missing_fields():
    svc = {cls}()
    errors = svc.validate_input({{}})
    assert "missing required field: id" in errors
    assert "missing required field: payload" in errors


def test_validate_input_accepts_valid():
    svc = {cls}()
    assert svc.validate_input({{"id": 1, "payload": {{}}}}) == []


def test_validate_input_rejects_non_mapping():
    svc = {cls}()
    assert svc.validate_input("not a dict") == ["input must be a mapping"]


def test_process_success():
    svc = {cls}()
    result = svc.process({{"id": "r1", "payload": {{"x": 1}}}})
    assert result.ok is True
    assert result.record is not None
    assert result.record.status == "processed"


def test_process_rejects_invalid():
    svc = {cls}()
    result = svc.process({{}})
    assert result.ok is False
    assert result.errors


def test_report_counts_operations():
    svc = {cls}()
    svc.{first_op}()
    svc.{first_op}()
    report = svc.report()
    assert report["total_operations"] == 2
    assert report["by_operation"]["{first_op}"] == 2{op_tests}
'''
    return [Artifact(path="tests/unit/test_core.py", content=content, kind="test", language="python")]


def render_integration_tests(spec: ProjectSpec) -> List[Artifact]:
    cls = class_name(spec)
    pkg = pkg_name(spec)
    ops = _operation_idents(spec)
    op_calls = "\n".join(f"    svc.{op}({{\"seq\": {i}}})" for i, op in enumerate(ops[:3]))
    content = f'''"""Integration tests for {spec.title} (auto-generated).

Exercises the components together end-to-end.
"""

from {pkg}.core import {cls}


def test_end_to_end_flow():
    svc = {cls}()
    for i in range(3):
        result = svc.process({{"id": f"rec-{{i}}", "payload": {{"value": i}}}})
        assert result.ok is True
{op_calls}
    report = svc.report()
    assert report["total_operations"] >= 3
    assert "process" in report["by_operation"]


def test_invalid_then_valid_flow():
    svc = {cls}()
    bad = svc.process({{"payload": {{}}}})
    assert bad.ok is False
    good = svc.process({{"id": "ok-1", "payload": {{"a": 1}}}})
    assert good.ok is True
    assert svc.report()["total_operations"] >= 1
'''
    return [Artifact(path="tests/integration/test_integration.py", content=content, kind="test", language="python")]


def render_build_report(spec: ProjectSpec, test_summary: dict | None = None) -> str:
    ts = test_summary or {}
    status = ts.get("status", "not-run")
    passed = ts.get("passed", "-")
    failed = ts.get("failed", "-")
    total = ts.get("total", "-")
    return f"""# Developer Build & Validation Report
## {spec.title}

*Generated by the Software Developer agent on {_now()}.*

## Delivered Artifacts
- Component design document.
- Source code: `{class_name(spec)}` core service + data models.
- Unit tests (`tests/unit/test_core.py`).
- Integration tests (`tests/integration/test_integration.py`).

## Operations Implemented
{", ".join(spec.operations)}

## Local Test Execution
- Status: **{status}**
- Total: {total} | Passed: {passed} | Failed: {failed}

## Notes
All code is deterministic, dependency-light and runs offline on edge devices.
The Validation Engineer agent independently re-executes these tests and records
the outcome in the Excel validation report.
"""
