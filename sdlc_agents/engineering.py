"""Developer-side engineering analysis: code model, diagrams, traceability,
static analysis and test coverage.

Everything here is deterministic and offline. It inspects the *actual* generated
code (not just the spec) to produce:

* a **class diagram** and a code-level **sequence diagram** (Mermaid);
* the **design patterns** used and **detailed component descriptions**;
* **Design IDs** and a full **Architecture ID -> Design ID -> Code -> Test**
  traceability matrix, plus design-ID banners injected into the code and
  ``Covers:`` links injected into the tests;
* a **SonarQube-style static-analysis** pass (offline rule set);
* **code coverage** for the unit and integration suites (Python measured with a
  stdlib tracer; other languages reported best-effort).
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .analysis import ProjectSpec
from .languages import get_language
from .types import Artifact

_SOURCE_LANGS = {"python", "rust", "java", "kotlin", "c", "cpp"}


# ===========================================================================
# Code model (extracted from the actual generated code)
# ===========================================================================


@dataclass
class ClassModel:
    name: str
    methods: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    file: str = ""


def _is_source(art: Artifact) -> bool:
    return (
        not art.is_binary
        and art.kind in ("code", "test")
        and art.language in _SOURCE_LANGS
    )


def extract_code_model(artifacts: List[Artifact], language: str) -> List[ClassModel]:
    """Extract classes/methods/fields from the generated source files."""

    sources = [a for a in artifacts if _is_source(a) and a.kind == "code"]
    models: List[ClassModel] = []
    for art in sources:
        if art.language == "python":
            models.extend(_py_classes(art))
        else:
            models.extend(_regex_classes(art))
    return models


def _py_classes(art: Artifact) -> List[ClassModel]:
    out: List[ClassModel] = []
    try:
        tree = ast.parse(art.content)
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("__")]
            fields: List[str] = []

            def _add(name):
                if name and name not in fields and not name.startswith("_"):
                    fields.append(name)

            for n in node.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                    _add(n.target.id)
                elif isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            _add(t.id)
            # Instance attributes assigned via self.<name> = ... in any method.
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                                and t.value.id == "self"):
                            _add(t.attr)
            out.append(ClassModel(name=node.name, methods=methods, fields=fields, file=art.path))
    return out


_CLASS_RE = re.compile(r"\b(?:class|struct)\s+([A-Za-z_]\w*)")
_FN_RE = {
    "rust": re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*\("),
    "kotlin": re.compile(r"\bfun\s+([A-Za-z_]\w*)\s*\("),
    "java": re.compile(r"\b(?:public|private|protected)\s+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\("),
    "cpp": re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:const)?\s*[{;]"),
    "c": re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*[{;]"),
}
_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "new", "delete"}


def _regex_classes(art: Artifact) -> List[ClassModel]:
    # Drop Rust inline test modules so test fns don't pollute the class diagram.
    text = re.split(r"#\[cfg\(test\)\]", art.content)[0]
    names = _CLASS_RE.findall(text)
    fn_re = _FN_RE.get(art.language)
    methods: List[str] = []
    if fn_re:
        for m in fn_re.findall(text):
            if m not in _KEYWORDS and m not in methods:
                methods.append(m)
    cls_name = names[0] if names else Path(art.path).stem
    # Prefer a PascalCase type name if one was found.
    for n in names:
        if n[:1].isupper():
            cls_name = n
            break
    return [ClassModel(name=cls_name, methods=methods[:12], fields=[], file=art.path)]


def _primary(models: List[ClassModel]) -> Optional[ClassModel]:
    if not models:
        return None
    for m in models:
        low = [x.lower() for x in m.methods]
        if "process" in low and any("valid" in x for x in low):
            return m
    return max(models, key=lambda m: len(m.methods))


# ===========================================================================
# Diagrams from the code model
# ===========================================================================


def render_class_diagram(models: List[ClassModel]) -> str:
    if not models:
        return "```mermaid\nclassDiagram\n    class Service\n```\n"
    lines = ["classDiagram"]
    for m in models:
        lines.append(f"    class {m.name} {{")
        for f in m.fields[:8]:
            lines.append(f"        +{f}")
        for meth in m.methods[:10]:
            lines.append(f"        +{meth}()")
        lines.append("    }")
    primary = _primary(models)
    if primary:
        for m in models:
            if m is not primary:
                lines.append(f"    {primary.name} --> {m.name}")
    return "```mermaid\n" + "\n".join(lines) + "\n```\n"


def render_code_sequence(models: List[ClassModel]) -> str:
    primary = _primary(models)
    cls = primary.name if primary else "Service"
    has_validate = bool(primary and any("valid" in x.lower() for x in primary.methods))
    has_record = bool(primary and any(x.lower() in ("record", "audit") for x in primary.methods))
    steps = [
        "sequenceDiagram",
        "    actor Caller",
        f"    participant S as {cls}",
        "    Caller->>S: process(input)",
    ]
    if has_validate:
        steps += ["    S->>S: validate(input)", "    alt valid"]
        if has_record:
            steps.append('    S->>S: record("process")')
        steps += ["        S-->>Caller: result", "    else invalid",
                  "        S-->>Caller: validation error", "    end"]
    else:
        if has_record:
            steps.append('    S->>S: record("process")')
        steps.append("    S-->>Caller: result")
    return "```mermaid\n" + "\n".join(steps) + "\n```\n"


def design_patterns(models: List[ClassModel]) -> List[str]:
    patterns = [
        "**Layered architecture** — interface / core / domain / persistence separation.",
        "**Service (Facade) pattern** — a single core service exposes the use-case operations.",
    ]
    primary = _primary(models)
    if primary and any(x.lower() in ("record", "audit", "count") for x in primary.methods):
        patterns.append("**Audit Log / Ledger** — every operation is appended to an in-memory audit trail for traceability.")
    if any(m.name.lower() in ("record", "result", "model") or "model" in m.file.lower() for m in models):
        patterns.append("**Data Transfer Object** — plain `Record` / `Result` data holders carry state between layers.")
    return patterns


# ===========================================================================
# Design IDs + traceability
# ===========================================================================


@dataclass
class DesignElement:
    design_id: str
    name: str
    file: str
    realises: List[str]          # architecture component ids, e.g. ["C2 Core Service"]
    req_refs: List[str]          # FR ids, e.g. ["FR-1", "FR-2"]
    role: str                    # "core" | "model" | "support"


@dataclass
class DesignModel:
    elements: List[DesignElement]
    by_file: Dict[str, DesignElement]
    core: Optional[DesignElement]
    test_files: List[str]


def _arch_label(spec: ProjectSpec, keywords) -> str:
    for i, c in enumerate(spec.components, start=1):
        low = c.lower()
        if any(k in low for k in keywords):
            return f"C{i} {c.split('(')[0].strip()}"
    return "Layered architecture"


def build_design(spec: ProjectSpec, artifacts: List[Artifact]) -> DesignModel:
    sources = [a for a in artifacts if _is_source(a) and a.kind == "code"]
    tests = [a for a in artifacts if _is_source(a) and a.kind == "test"]
    fr_ids = [f"FR-{i}" for i in range(1, len(spec.functional_requirements) + 1)] or ["FR-1"]

    # Identify the core source file (has process + validate).
    def is_core(a: Artifact) -> bool:
        c = a.content.lower()
        return "process" in c and "valid" in c

    core_art = next((a for a in sources if is_core(a)), sources[0] if sources else None)

    elements: List[DesignElement] = []
    by_file: Dict[str, DesignElement] = {}
    core_el: Optional[DesignElement] = None
    n = 0
    for a in sources:
        n += 1
        did = f"DD-{n}"
        low = a.path.lower()
        if a is core_art:
            el = DesignElement(did, Path(a.path).name, a.path,
                               [_arch_label(spec, ("core", "service", "logic", "engine"))],
                               fr_ids, "core")
            core_el = el
        elif "model" in low or "record" in low or "types" in low:
            el = DesignElement(did, Path(a.path).name, a.path,
                               [_arch_label(spec, ("domain", "model"))], [], "model")
        elif any(k in low for k in ("conf", "manifest", "pyproject")):
            el = DesignElement(did, Path(a.path).name, a.path, ["Build/Config"], [], "support")
        else:
            el = DesignElement(did, Path(a.path).name, a.path,
                               [_arch_label(spec, ("interface", "input", "report", "persist", "store"))],
                               [], "support")
        elements.append(el)
        by_file[a.path] = el

    return DesignModel(elements=elements, by_file=by_file, core=core_el,
                       test_files=[t.path for t in tests])


def annotate_traceability(artifacts: List[Artifact], spec: ProjectSpec,
                          design: DesignModel, language: str) -> List[Artifact]:
    """Inject design-ID banners into code and ``Covers:`` links into tests."""

    comment = get_language(language).line_comment
    core = design.core
    covers = ""
    if core:
        fr_span = f"{core.req_refs[0]}..{core.req_refs[-1]}" if core.req_refs else "FR-*"
        covers = f"{core.design_id} ({core.name}) | {fr_span}"

    out: List[Artifact] = []
    for a in artifacts:
        if not _is_source(a):
            out.append(a)
            continue
        if a.kind == "test":
            banner = f"{comment} Covers: {covers or 'core design'} | verifies the generated implementation"
        else:
            el = design.by_file.get(a.path)
            if not el:
                out.append(a)
                continue
            refs = (" | Traceability: " + ", ".join(el.req_refs)) if el.req_refs else ""
            banner = f"{comment} Design: {el.design_id} ({el.name}) — realises {', '.join(el.realises)}{refs}"
        out.append(dataclasses.replace(a, content=banner + "\n" + a.content))
    return out


def render_component_descriptions(spec: ProjectSpec, design: DesignModel,
                                  models: List[ClassModel]) -> str:
    primary = _primary(models)
    iface = {}
    if primary:
        iface[primary.file] = primary.methods
    lines = ["| Arch ID | Component | Responsibility | Realised by | Key interface |",
             "|---------|-----------|----------------|-------------|---------------|"]
    # Map each architecture component to a design element when one realises it.
    for i, comp in enumerate(spec.components, start=1):
        cid = f"C{i}"
        realised = next((e for e in design.elements if any(cid in r for r in e.realises)), None)
        did = realised.design_id if realised else "—"
        methods = iface.get(realised.file, []) if realised else []
        iface_txt = ", ".join(f"{m}()" for m in methods[:4]) if methods else "—"
        resp = f"Owns the '{comp.split('(')[0].strip().lower()}' concern."
        lines.append(f"| {cid} | {comp} | {resp} | {did} | {iface_txt} |")
    return "\n".join(lines) + "\n"


def render_traceability_matrix(spec: ProjectSpec, design: DesignModel) -> str:
    out = ["### Architecture → Design → Code",
           "| Architecture ID | Design ID | Code file | Role |",
           "|-----------------|-----------|-----------|------|"]
    for e in design.elements:
        out.append(f"| {', '.join(e.realises)} | {e.design_id} | `{e.file}` | {e.role} |")

    out += ["", "### Requirement → Design → Code → Test",
            "| Requirement | Design ID | Code file | Verified by |",
            "|-------------|-----------|-----------|-------------|"]
    core = design.core
    test_list = ", ".join(f"`{t}`" for t in design.test_files) or "—"
    if core:
        for fr in core.req_refs:
            out.append(f"| {fr} | {core.design_id} | `{core.file}` | {test_list} |")
    else:
        out.append("| FR-* | — | — | — |")
    return "\n".join(out) + "\n"


# ===========================================================================
# Static analysis (SonarQube-style, offline)
# ===========================================================================


@dataclass
class Finding:
    rule: str
    severity: str   # BLOCKER | CRITICAL | MAJOR | MINOR | INFO
    file: str
    line: int
    message: str


_MAX_LINE = 120
_MAX_FUNC_LINES = 60


def static_analysis(artifacts: List[Artifact], language: str) -> List[Finding]:
    findings: List[Finding] = []
    for art in artifacts:
        if not _is_source(art):
            continue
        lines = art.content.splitlines()
        for i, line in enumerate(lines, start=1):
            if len(line) > _MAX_LINE:
                findings.append(Finding("S103", "MINOR", art.path, i, f"Line longer than {_MAX_LINE} characters."))
            if re.search(r"\b(TODO|FIXME|XXX)\b", line):
                findings.append(Finding("S1135", "INFO", art.path, i, "Track this 'TODO/FIXME' and resolve it."))
            if line.rstrip() != line and line.strip():
                findings.append(Finding("S1131", "INFO", art.path, i, "Remove trailing whitespace."))
            if re.search(r"except\s*:", line):
                findings.append(Finding("S5754", "MAJOR", art.path, i, "Do not use a bare 'except:'; catch a specific exception."))
        if art.language == "python":
            findings.extend(_py_static(art))
    # De-duplicate and cap noise.
    uniq = {(f.rule, f.file, f.line): f for f in findings}
    return sorted(uniq.values(), key=lambda f: (f.file, f.line))


def _py_static(art: Artifact) -> List[Finding]:
    out: List[Finding] = []
    try:
        tree = ast.parse(art.content)
    except SyntaxError:
        out.append(Finding("S2260", "CRITICAL", art.path, 1, "Source does not parse."))
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if end - node.lineno > _MAX_FUNC_LINES:
                out.append(Finding("S138", "MAJOR", art.path, node.lineno,
                                   f"Function '{node.name}' is too long ({end - node.lineno} lines)."))
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            out.append(Finding("S5754", "MAJOR", art.path, node.lineno, "Bare 'except' catches everything."))
    return out


def render_static_report(findings: List[Finding], language: str) -> str:
    order = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in order}
    summary = " · ".join(f"{s}: {counts[s]}" for s in order)
    head = (
        "## Static Analysis (SonarQube-style)\n"
        f"*Offline rule set over the generated {get_language(language).display} code.*\n\n"
        f"**Summary — {summary}**\n\n"
    )
    if not findings:
        return head + "No issues found by the offline rule set — the generated code is clean. " \
                      "Point a SonarQube/SonarLint scanner at the project for the full rule set.\n"
    rows = ["| Rule | Severity | File | Line | Message |", "|------|----------|------|------|---------|"]
    for f in findings[:100]:
        rows.append(f"| {f.rule} | {f.severity} | `{f.file}` | {f.line} | {f.message} |")
    return head + "\n".join(rows) + "\n"


# ===========================================================================
# Code coverage (unit + integration)
# ===========================================================================

_PY_COV_SCRIPT = r"""
import sys, os, ast, json, importlib.util, unittest
workspace, suite_dir = sys.argv[1], sys.argv[2]
src_dir = os.path.join(workspace, "src")
sys.path.insert(0, src_dir)

def walk(root, pred):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if pred(f):
                out.append(os.path.join(dp, f))
    return out

if not os.path.isdir(src_dir):
    print(json.dumps({"ok": False})); sys.exit(0)

src_files = walk(src_dir, lambda f: f.endswith(".py"))
src_real = {os.path.realpath(f) for f in src_files}

def stmt_lines(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception:
        return set()
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
        ):
            if getattr(node, "lineno", None):
                lines.add(node.lineno)
    return lines

total_map = {os.path.realpath(f): stmt_lines(f) for f in src_files}
total = sum(len(v) for v in total_map.values())
executed = set()

def tracer(frame, event, arg):
    if event == "line":
        rp = os.path.realpath(frame.f_code.co_filename)
        if rp in src_real:
            executed.add((rp, frame.f_lineno))
    return tracer

test_files = walk(suite_dir, lambda f: f.startswith("test_") and f.endswith(".py")) if os.path.isdir(suite_dir) else []

def run_mod(path):
    name = "covmod_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return
    for n in dir(mod):
        obj = getattr(mod, n)
        if n.startswith("test_") and callable(obj):
            try: obj()
            except Exception: pass
        elif isinstance(obj, type) and issubclass(obj, unittest.TestCase):
            try:
                inst = obj(methodName=[m for m in dir(obj) if m.startswith("test_")][0])
            except Exception:
                continue
            for m in dir(inst):
                if m.startswith("test_"):
                    try:
                        if hasattr(inst, "setUp"): inst.setUp()
                        getattr(inst, m)()
                    except Exception: pass

old = sys.gettrace()
sys.settrace(tracer)
try:
    for tf in test_files:
        run_mod(tf)
finally:
    sys.settrace(old)

covered = 0
for rp, lines in total_map.items():
    hit = {ln for (f, ln) in executed if f == rp}
    covered += len(lines & hit)
pct = round(100.0 * covered / total, 1) if total else 0.0
print(json.dumps({"ok": True, "covered": covered, "total": total, "pct": pct,
                  "tests": len(test_files)}))
"""


def _py_coverage(workspace: Path, suite_subdir: str) -> Optional[Dict]:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _PY_COV_SCRIPT, str(workspace), str(workspace / suite_subdir)],
            capture_output=True, text=True, timeout=300,
        )
        data = json.loads((proc.stdout or "").strip().splitlines()[-1])
        return data if data.get("ok") else None
    except Exception:
        return None


def _parse_jacoco_xml(text: str) -> Optional[Dict]:
    """Parse LINE coverage from a JaCoCo-format XML report (JaCoCo & Kover)."""

    import xml.etree.ElementTree as ET

    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.DOTALL)  # avoid DTD fetch
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None

    def line_counter(elem):
        for c in elem.findall("counter"):
            if c.get("type") == "LINE":
                return int(c.get("covered", 0)), int(c.get("missed", 0))
        return None

    lc = line_counter(root)
    if lc is None:  # fall back to the largest LINE counter anywhere
        best = None
        for c in root.iter("counter"):
            if c.get("type") == "LINE":
                cov, mis = int(c.get("covered", 0)), int(c.get("missed", 0))
                if best is None or (cov + mis) > (best[0] + best[1]):
                    best = (cov, mis)
        lc = best
    if not lc:
        return None
    covered, missed = lc
    total = covered + missed
    pct = round(100.0 * covered / total, 1) if total else 0.0
    return {"pct": pct, "covered": covered, "total": total}


def _read_first(workspace: Path, candidates) -> Optional[str]:
    for rel in candidates:
        p = workspace / rel
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return None


# (toolchain, build command tail, report paths, display name) per JVM language.
_JVM_COVERAGE = {
    "kotlin": ("gradle", ["koverXmlReport", "--console=plain"],
               ["build/reports/kover/report.xml", "build/reports/kover/xml/report.xml"], "Kover"),
    "java": ("mvn", ["-q", "-B", "test"],
             ["target/site/jacoco/jacoco.xml"], "JaCoCo"),
}


def _external_coverage(workspace: Path, lang: str) -> Optional[Dict]:
    """Measure coverage for JVM languages with Kover/JaCoCo when available."""

    from .testrunner import resolve_tool

    cfg = _JVM_COVERAGE.get(lang)
    if not cfg:
        return None
    toolchain, tail, reports, name = cfg

    # Reuse a report already produced by the test run (e.g. JaCoCo during `mvn test`).
    xml = _read_first(workspace, reports)
    if xml is None:
        tool = resolve_tool(toolchain, workspace)
        if not tool:
            return None  # fall through to the generic note
        try:
            proc = subprocess.run([tool, *tail], cwd=str(workspace),
                                  capture_output=True, text=True, timeout=1200)
        except subprocess.TimeoutExpired:
            return {"measured": False, "tool": name, "note": f"{name} build timed out."}
        except OSError as exc:
            return {"measured": False, "tool": name, "note": f"Could not run {name}: {exc}."}
        xml = _read_first(workspace, reports)
        if xml is None:
            return {"measured": False, "tool": name,
                    "note": f"Attempted {name} but no coverage report was produced "
                            f"(build exit {proc.returncode}); usually a missing dependency "
                            f"download. On a host with the toolchain and network, coverage "
                            f"is reported here."}
    parsed = _parse_jacoco_xml(xml)
    if not parsed:
        return {"measured": False, "tool": name, "note": f"{name} report could not be parsed."}
    return {"measured": True, "tool": name, "combined": True,
            "overall": parsed, "unit": None, "integration": None}


def measure_coverage(workspace: Path, language: str) -> Dict:
    """Measure unit + integration coverage; returns a structured result."""

    lang = get_language(language).id
    if lang == "python":
        unit = _py_coverage(workspace, "tests/unit")
        integ = _py_coverage(workspace, "tests/integration")
        overall = _py_coverage(workspace, "tests")
        return {
            "measured": True,
            "tool": "stdlib tracer (offline)",
            "unit": unit, "integration": integ, "overall": overall,
        }

    ext = _external_coverage(workspace, lang)
    if ext is not None:
        return ext

    tool = {
        "rust": "cargo-llvm-cov / tarpaulin",
        "c": "gcovr/lcov", "cpp": "gcovr/lcov",
    }.get(lang, "a coverage tool")
    return {
        "measured": False, "tool": tool,
        "note": f"Coverage for {get_language(language).display} is measured with {tool} on a host "
                f"with the toolchain installed; it is not computed on this device.",
    }


def render_coverage(cov: Dict) -> str:
    head = "## Code Coverage\n"
    if not cov.get("measured"):
        return head + f"*{cov.get('note', 'Not measured.')}*\n"

    def pct(block):
        if not block:
            return "n/a"
        return f"{block.get('pct', 0)}% ({block.get('covered', 0)}/{block.get('total', 0)} lines)"

    if cov.get("combined"):
        return (
            head + f"*Measured with {cov['tool']}. The JVM build runs all tests together, "
            "so unit and integration coverage are reported as a combined figure.*\n\n"
            "| Suite | Coverage |\n|-------|----------|\n"
            f"| Unit + integration (combined) | {pct(cov.get('overall'))} |\n"
        )

    return (
        head + f"*Measured with the {cov['tool']}.*\n\n"
        "| Suite | Coverage |\n|-------|----------|\n"
        f"| Unit tests | {pct(cov.get('unit'))} |\n"
        f"| Integration tests | {pct(cov.get('integration'))} |\n"
        f"| **Overall** | **{pct(cov.get('overall'))}** |\n"
    )


# ===========================================================================
# Design-document supplement (assembled for the Developer agent)
# ===========================================================================


def render_design_supplement(spec: ProjectSpec, artifacts: List[Artifact],
                             design: DesignModel, models: List[ClassModel]) -> str:
    patterns = "\n".join(f"- {p}" for p in design_patterns(models))
    return (
        "\n## Design Patterns\n" + patterns + "\n"
        "\n## Detailed Component Description\n"
        + render_component_descriptions(spec, design, models)
        + "\n## Class Diagram (from code)\n" + render_class_diagram(models)
        + "\n## Sequence Diagram (from code)\n" + render_code_sequence(models)
        + "\n## Traceability\n" + render_traceability_matrix(spec, design)
    )
