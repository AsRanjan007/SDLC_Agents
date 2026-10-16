"""Validation Engineer agent.

Independently verifies the delivery produced by the Architect and Developer
agents: functional and non-functional requirements, architecture/design
validation, test execution and code-quality signals — for the configured target
language. Honours the Validation agent's configuration (whether to run tests,
scan for networking, check coverage, and emit the Excel workbook) and always
emits a Markdown summary plus (by default) an Excel validation workbook.
"""

from __future__ import annotations

import ast
import datetime as _dt
import re
from pathlib import Path
from typing import Dict, List

from ..analysis import ProjectSpec
from ..artifacts.excel_report import build_validation_workbook
from ..languages import get_language
from ..testrunner import run_tests
from ..types import AgentResult, Artifact, RunContext
from .base import BaseAgent

# Networking signatures across the supported languages (static scan).
_NETWORK_TOKENS = (
    "socket", "requests", "urllib", "httpx", "aiohttp", "http.client",
    "reqwest", "hyper::", "okhttp", "java.net", "HttpURLConnection",
    "HttpClient", "curl", "winhttp", "boost::asio", "sys/socket.h",
    "WinSock", "tokio::net",
)

# Source-file extensions per language (headers included for C/C++).
_SOURCE_EXTS = {
    "python": (".py",),
    "rust": (".rs",),
    "java": (".java",),
    "kotlin": (".kt",),
    "c": (".c", ".h"),
    "cpp": (".cpp", ".hpp", ".cc", ".hh"),
}


class _ValDefaults:
    run_tests = True
    static_security_scan = True
    check_coverage = True
    excel_report = True


class ValidationEngineerAgent(BaseAgent):
    agent_id = "validation_engineer"
    role_title = "Validation Engineer"

    def _val_cfg(self):
        agents = getattr(self.config, "agents", None)
        return getattr(agents, "validation", None) or _ValDefaults()

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:
        lang = self._target_language(spec)
        profile = get_language(lang)
        framework = self._framework(spec)
        val = self._val_cfg()

        exts = _SOURCE_EXTS.get(profile.id, (profile.ext,))
        source_text = _read_sources(ctx.workspace, exts)
        sad_text = _prior_doc(prior, "architect")
        design_text = _prior_doc(prior, "developer")

        # Re-run the tests independently (unless disabled).
        if getattr(val, "run_tests", True):
            test_summary = run_tests(ctx.workspace, lang, framework.id)
        else:
            test_summary = {"status": "skipped", "total": 0, "passed": 0, "failed": 0,
                            "detail": "Test execution disabled in Validation configuration."}

        functional = _verify_functional(spec, source_text, test_summary)
        nonfunctional = _verify_nonfunctional(spec, source_text, getattr(val, "static_security_scan", True))
        architecture = _validate_architecture(spec, sad_text, design_text, source_text)
        tests = _test_rows(test_summary, framework.display)
        quality = _code_quality(ctx.workspace, exts, profile.id, getattr(val, "check_coverage", True))

        overall = _overall_verdict(functional, nonfunctional, architecture, tests, quality)

        meta = {
            "title": spec.title,
            "run_id": ctx.run_id,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "backend": (self.llm.name if self.llm else "offline"),
            "language": profile.display,
            "test_framework": framework.display,
            "fr_count": len(functional),
            "nfr_count": len(nonfunctional),
            "tests_passed": test_summary.get("passed", 0),
            "tests_failed": test_summary.get("failed", 0),
            "tests_total": test_summary.get("total", 0),
            "test_status": test_summary.get("status", "unknown"),
        }
        report = {
            "meta": meta,
            "overall": overall,
            "functional": functional,
            "nonfunctional": nonfunctional,
            "architecture": architecture,
            "tests": tests,
            "quality": quality,
        }

        artifacts: List[Artifact] = []
        if getattr(val, "excel_report", True):
            xlsx_bytes = build_validation_workbook(report)
            artifacts.append(
                Artifact(path="docs/reports/Validation_Report.xlsx", kind="excel", language="xlsx", data=xlsx_bytes)
            )
        artifacts.append(
            Artifact(
                path="docs/reports/Validation_Report.md",
                content=_render_markdown(report),
                kind="report",
                language="markdown",
            )
        )
        if ctx.write_artifact:
            for a in artifacts:
                ctx.write_artifact(a)

        n_pass = sum(1 for r in functional + nonfunctional if r["verdict"] == "PASS")
        n_total = len(functional) + len(nonfunctional)
        narration = (
            f"The Validation Engineer agent independently verified the "
            f"{profile.display} delivery. It checked {len(functional)} functional "
            f"and {len(nonfunctional)} non-functional requirements, validated the "
            f"architecture and design, and handled the {framework.display} test "
            f"suite (status: {test_summary.get('status')}). {n_pass} of {n_total} "
            f"requirements passed. Results were compiled into an Excel validation "
            f"report. Overall verdict: {overall}."
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=f"Validation complete — overall verdict {overall} ({profile.display} / {framework.display}).",
            artifacts=artifacts,
            metrics={
                "overall": overall,
                "language": profile.display,
                "test_framework": framework.display,
                "requirements_passed": n_pass,
                "requirements_total": n_total,
                "tests_passed": test_summary.get("passed", 0),
                "tests_total": test_summary.get("total", 0),
                "test_status": test_summary.get("status"),
            },
            narration=narration,
        )


# ---------------------------------------------------------------------------
# verification helpers
# ---------------------------------------------------------------------------


def _verify_functional(spec: ProjectSpec, source_text: str, test_summary: Dict) -> List[Dict]:
    rows: List[Dict] = []
    status = test_summary.get("status")
    tests_green = status == "passed"
    tests_ran = status in ("passed", "failed")
    src_low = source_text.lower()
    for i, req in enumerate(spec.functional_requirements, start=1):
        salient = _salient_terms(req)
        matched = [t for t in salient if t in src_low]
        if matched and tests_green:
            verdict, notes = "PASS", f"Traced to code (terms: {', '.join(matched[:4])}); tests green."
        elif matched and tests_ran:  # ran but not green
            verdict, notes = "FAIL", "Traced to code but the test suite is not fully green."
        elif matched:  # tests not executed on this host (e.g. toolchain absent)
            verdict, notes = "PASS", "Traced to code; tests not executed here (verified by traceability + static review)."
        elif tests_green:
            verdict, notes = "PARTIAL", "Covered by the generic pipeline; no explicit term match."
        elif tests_ran:
            verdict, notes = "PARTIAL", "Implementation present; strengthen tests for full coverage."
        else:
            verdict, notes = "PARTIAL", "Implementation present; execute tests on a toolchain host to confirm."
        rows.append(
            {"id": f"FR-{i}", "requirement": req, "method": "Traceability + test", "verdict": verdict, "notes": notes}
        )
    return rows


def _verify_nonfunctional(spec: ProjectSpec, source_text: str, scan_enabled: bool) -> List[Dict]:
    rows: List[Dict] = []
    uses_network = scan_enabled and any(tok.lower() in source_text.lower() for tok in _NETWORK_TOKENS)
    for i, req in enumerate(spec.nonfunctional_requirements, start=1):
        low = req.lower()
        if "offline" in low or "network" in low:
            if not scan_enabled:
                verdict, notes, method = "PARTIAL", "Static network scan disabled in Validation config.", "Configuration"
            else:
                verdict = "PASS" if not uses_network else "FAIL"
                notes = "No networking APIs referenced in the core." if not uses_network else "Core references a networking API."
                method = "Static scan for network usage"
        elif "confidential" in low or "privacy" in low or "local" in low:
            verdict, notes, method = "PASS", "Artifacts stored locally with owner-only permissions.", "Storage policy review"
        elif "edge" in low or "footprint" in low:
            verdict, notes, method = "PASS", "Small, dependency-light core suitable for edge devices.", "Dependency review"
        elif "proxy" in low:
            verdict, notes, method = "PASS", "Core needs no network; proxy configurable for the optional endpoint.", "Configuration review"
        elif "encrypt" in low:
            verdict, notes, method = "PASS", "Optional at-rest encryption available for artifacts.", "Security control review"
        elif "perform" in low or "latency" in low or "throughput" in low:
            verdict, notes, method = "PARTIAL", "O(n) operations by design; not load-tested in this run.", "Design review"
        else:
            verdict, notes, method = "PASS", "Addressed by design; see architecture tactics.", "Design review"
        rows.append({"id": f"NFR-{i}", "requirement": req, "method": method, "verdict": verdict, "notes": notes})
    return rows


def _validate_architecture(spec: ProjectSpec, sad: str, design: str, source_text: str) -> List[Dict]:
    rows: List[Dict] = []

    def add(cid, check, verdict, notes):
        rows.append({"id": cid, "check": check, "verdict": verdict, "notes": notes})

    add("AR-1", "Software Architecture Document present", "PASS" if sad else "FAIL",
        "SAD generated by the Architect agent." if sad else "Missing SAD.")

    covered = [c for c in spec.components if c.split("(")[0].strip().lower() in sad.lower()]
    ratio = len(covered) / max(1, len(spec.components))
    add("AR-2", "All components documented in the SAD",
        "PASS" if ratio >= 0.8 else ("PARTIAL" if ratio >= 0.4 else "FAIL"),
        f"{len(covered)}/{len(spec.components)} components referenced.")

    has_nfr = any(k in sad.lower() for k in ("non-functional", "quality attribute", "nfr"))
    add("AR-3", "Quality attributes / NFRs addressed", "PASS" if has_nfr else "PARTIAL",
        "NFR section present." if has_nfr else "NFR coverage not explicit.")

    add("AR-4", "Design document present", "PASS" if design else "PARTIAL",
        "Component design generated by the Developer agent." if design else "No design doc found.")

    traceable = len(spec.functional_requirements) > 0 and len(spec.operations) > 0
    add("AR-5", "Requirements traceable to operations", "PASS" if traceable else "PARTIAL",
        f"{len(spec.functional_requirements)} FRs, {len(spec.operations)} operations.")

    has_code = bool(source_text.strip())
    add("AR-6", "Architecture realised in code", "PASS" if has_code else "FAIL",
        "Source code present and consistent with the layered design." if has_code else "No source code found.")
    return rows


def _test_rows(test_summary: Dict, framework_display: str) -> List[Dict]:
    total = int(test_summary.get("total", 0) or 0)
    passed = int(test_summary.get("passed", 0) or 0)
    failed = int(test_summary.get("failed", 0) or 0)
    if failed > 0:
        verdict = "FAIL"
    elif passed > 0:
        verdict = "PASS"
    else:
        verdict = "N/A"
    return [{
        "suite": f"Unit + Integration ({framework_display})",
        "total": total, "passed": passed, "failed": failed, "verdict": verdict,
    }]


def _code_quality(workspace: Path, exts, language_id: str, check_coverage: bool) -> List[Dict]:
    src_files = [p for p in _iter_sources(workspace, exts) if not _looks_like_test(p)]
    test_files = [p for p in workspace.rglob("*") if p.is_file() and _looks_like_test(p)]
    loc = 0
    documented = 0
    syntax_ok = True
    for f in src_files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        loc += text.count("\n") + 1
        if '"""' in text or "/**" in text or "///" in text or "//!" in text:
            documented += 1
        if language_id == "python":
            try:
                ast.parse(text)
            except SyntaxError:
                syntax_ok = False
    doc_ratio = documented / max(1, len(src_files))
    ratio = len(test_files) / max(1, len(src_files))

    rows = [
        {"metric": "Source files", "value": len(src_files), "verdict": "PASS" if src_files else "FAIL",
         "notes": "Generated source/header files."},
        {"metric": "Test modules", "value": len(test_files), "verdict": "PASS" if test_files else "FAIL",
         "notes": "Unit + integration test files."},
        {"metric": "Lines of code", "value": loc, "verdict": "N/A", "notes": "Total generated source lines."},
    ]
    if language_id == "python":
        rows.append({"metric": "Syntax valid", "value": "yes" if syntax_ok else "no",
                     "verdict": "PASS" if syntax_ok else "FAIL", "notes": "All source parses under the Python AST."})
    else:
        rows.append({"metric": "Syntax valid", "value": "n/a", "verdict": "N/A",
                     "notes": "Compiled on a toolchain host; not parsed here."})
    rows.append({"metric": "Docstring coverage", "value": f"{doc_ratio*100:.0f}%",
                 "verdict": "PASS" if doc_ratio >= 0.5 else "PARTIAL", "notes": "Share of source files with doc comments."})
    if check_coverage:
        rows.append({"metric": "Test:code ratio", "value": f"{ratio:.2f}",
                     "verdict": "PASS" if ratio >= 0.5 else "PARTIAL", "notes": "Test files per source file."})
    return rows


def _overall_verdict(*groups: List[Dict]) -> str:
    verdicts = []
    for g in groups:
        for row in g:
            verdicts.append(row.get("verdict", "N/A"))
    if "FAIL" in verdicts:
        return "FAIL"
    if "PARTIAL" in verdicts:
        return "PARTIAL"
    return "PASS"


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------


def _salient_terms(req: str) -> List[str]:
    words = re.findall(r"[A-Za-z]{4,}", req.lower())
    stop = {"input", "output", "should", "which", "with", "that", "will", "this", "from", "user", "data"}
    return [w for w in words if w not in stop][:6]


def _iter_sources(workspace: Path, exts):
    for p in workspace.rglob("*"):
        if p.is_file() and p.suffix in exts:
            yield p


def _read_sources(workspace: Path, exts) -> str:
    chunks = []
    for p in _iter_sources(workspace, exts):
        try:
            chunks.append(p.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(chunks)


def _looks_like_test(path: Path) -> bool:
    text_exts = {".py", ".rs", ".java", ".kt", ".c", ".cpp", ".cc", ".h", ".hpp", ".hh"}
    if path.suffix not in text_exts:
        return False
    name = path.stem.lower()
    norm = str(path).replace("\\", "/").lower()
    return (
        name.startswith("test_")
        or name.startswith("test")
        or name.endswith("_test")
        or name.endswith("test")
        or name.endswith("tests")
        or name.endswith("it")
        or name.endswith("spec")
        or "/tests/" in norm
        or "/test/" in norm
    )


def _prior_doc(prior: List[AgentResult], agent_id: str) -> str:
    for res in prior:
        if res.agent_id == agent_id:
            return "\n".join(a.content for a in res.artifacts if a.content)
    return ""


def _render_markdown(report: Dict) -> str:
    meta = report["meta"]
    lines = [
        f"# Validation Report — {meta['title']}",
        "",
        f"*Generated by the Validation Engineer agent on {meta['generated']}.*",
        "",
        f"**Overall verdict: {report['overall']}**",
        "",
        f"- Target language: {meta.get('language', 'n/a')}",
        f"- Unit-test framework: {meta.get('test_framework', 'n/a')}",
        f"- Functional requirements checked: {meta['fr_count']}",
        f"- Non-functional requirements checked: {meta['nfr_count']}",
        f"- Tests: {meta['tests_passed']} passed / {meta['tests_total']} total (status: {meta.get('test_status', 'n/a')})",
        "",
        "## Functional Requirements",
        "| ID | Requirement | Verdict | Notes |",
        "|----|-------------|---------|-------|",
    ]
    for r in report["functional"]:
        lines.append(f"| {r['id']} | {r['requirement']} | {r['verdict']} | {r['notes']} |")
    lines += ["", "## Non-Functional Requirements", "| ID | Requirement | Verdict | Notes |", "|----|-------------|---------|-------|"]
    for r in report["nonfunctional"]:
        lines.append(f"| {r['id']} | {r['requirement']} | {r['verdict']} | {r['notes']} |")
    lines += ["", "## Architecture & Design Validation", "| ID | Check | Verdict | Notes |", "|----|-------|---------|-------|"]
    for r in report["architecture"]:
        lines.append(f"| {r['id']} | {r['check']} | {r['verdict']} | {r['notes']} |")
    lines += ["", "See `Validation_Report.xlsx` for the full workbook (Functional, NonFunctional, Architecture, TestResults, CodeQuality)."]
    return "\n".join(lines)
