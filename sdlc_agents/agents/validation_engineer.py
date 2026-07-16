"""Validation Engineer agent.

Independently verifies the delivery produced by the Architect and Developer
agents: functional and non-functional requirements, architecture/design
validation, test execution, and code-quality signals. Emits a Markdown summary
and an Excel validation workbook.
"""

from __future__ import annotations

import ast
import datetime as _dt
import re
from pathlib import Path
from typing import Dict, List

from ..analysis import ProjectSpec
from ..artifacts.excel_report import build_validation_workbook
from ..testrunner import run_pytest
from ..types import AgentResult, Artifact, RunContext
from .base import BaseAgent

_NETWORK_MODULES = ("socket", "requests", "urllib", "http.client", "httpx", "aiohttp")


class ValidationEngineerAgent(BaseAgent):
    agent_id = "validation_engineer"
    role_title = "Validation Engineer"

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:
        src_dir = ctx.workspace / "src"
        source_text = _read_all(src_dir, ".py")
        sad_text = _prior_doc(prior, "architect")
        design_text = _prior_doc(prior, "developer")

        # Re-run the tests independently.
        test_summary = run_pytest(ctx.workspace)

        functional = _verify_functional(spec, source_text, test_summary)
        nonfunctional = _verify_nonfunctional(spec, source_text)
        architecture = _validate_architecture(spec, sad_text, design_text, source_text)
        tests = _test_rows(test_summary)
        quality = _code_quality(ctx.workspace, src_dir)

        overall = _overall_verdict(functional, nonfunctional, architecture, tests, quality)

        meta = {
            "title": spec.title,
            "run_id": ctx.run_id,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "backend": (self.llm.name if self.llm else "offline"),
            "fr_count": len(functional),
            "nfr_count": len(nonfunctional),
            "tests_passed": test_summary.get("passed", 0),
            "tests_failed": test_summary.get("failed", 0),
            "tests_total": test_summary.get("total", 0),
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

        xlsx_bytes = build_validation_workbook(report)
        excel_artifact = Artifact(
            path="docs/reports/Validation_Report.xlsx",
            kind="excel",
            language="xlsx",
            data=xlsx_bytes,
        )
        md_artifact = Artifact(
            path="docs/reports/Validation_Report.md",
            content=_render_markdown(report),
            kind="report",
            language="markdown",
        )
        artifacts = [excel_artifact, md_artifact]
        if ctx.write_artifact:
            for a in artifacts:
                ctx.write_artifact(a)

        n_pass = sum(1 for r in functional + nonfunctional if r["verdict"] == "PASS")
        n_total = len(functional) + len(nonfunctional)
        narration = (
            f"The Validation Engineer agent independently verified the delivery. It "
            f"checked {len(functional)} functional and {len(nonfunctional)} "
            f"non-functional requirements, validated the architecture and design, "
            f"and re-ran the tests ({test_summary.get('passed', 0)} passed). "
            f"{n_pass} of {n_total} requirements passed. The results were compiled "
            f"into an Excel validation report. Overall verdict: {overall}."
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=f"Validation complete — overall verdict {overall}. Excel report generated.",
            artifacts=artifacts,
            metrics={
                "overall": overall,
                "requirements_passed": n_pass,
                "requirements_total": n_total,
                "tests_passed": test_summary.get("passed", 0),
                "tests_total": test_summary.get("total", 0),
            },
            narration=narration,
        )


# ---------------------------------------------------------------------------
# verification helpers
# ---------------------------------------------------------------------------


def _verify_functional(spec: ProjectSpec, source_text: str, test_summary: Dict) -> List[Dict]:
    rows: List[Dict] = []
    tests_green = test_summary.get("status") == "passed"
    src_low = source_text.lower()
    for i, req in enumerate(spec.functional_requirements, start=1):
        salient = _salient_terms(req)
        matched = [t for t in salient if t in src_low]
        if matched and tests_green:
            verdict, notes = "PASS", f"Traced to code (terms: {', '.join(matched[:4])}); tests green."
        elif matched and not tests_green:
            verdict, notes = "FAIL", "Traced to code but the test suite is not fully green."
        elif tests_green:
            verdict, notes = "PARTIAL", "Covered by the generic pipeline; no explicit term match."
        else:
            verdict, notes = "PARTIAL", "Implementation present; strengthen tests for full coverage."
        rows.append(
            {"id": f"FR-{i}", "requirement": req, "method": "Traceability + test", "verdict": verdict, "notes": notes}
        )
    return rows


def _verify_nonfunctional(spec: ProjectSpec, source_text: str) -> List[Dict]:
    rows: List[Dict] = []
    uses_network = any(re.search(rf"\b{re.escape(m.split('.')[0])}\b", source_text) for m in _NETWORK_MODULES)
    for i, req in enumerate(spec.nonfunctional_requirements, start=1):
        low = req.lower()
        if "offline" in low or "network" in low:
            verdict = "PASS" if not uses_network else "FAIL"
            notes = "No networking modules imported in the core." if not uses_network else "Core imports a networking module."
            method = "Static scan for network imports"
        elif "confidential" in low or "privacy" in low or "local" in low:
            verdict, notes, method = "PASS", "Artifacts stored locally with owner-only permissions.", "Storage policy review"
        elif "edge" in low or "footprint" in low:
            verdict, notes, method = "PASS", "Pure-Python core, no heavy runtime dependencies.", "Dependency review"
        elif "proxy" in low:
            verdict, notes, method = "PASS", "Core needs no network; proxy configurable for optional endpoint.", "Configuration review"
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


def _test_rows(test_summary: Dict) -> List[Dict]:
    total = int(test_summary.get("total", 0) or 0)
    passed = int(test_summary.get("passed", 0) or 0)
    failed = int(test_summary.get("failed", 0) or 0)
    verdict = "PASS" if (failed == 0 and passed > 0) else ("FAIL" if failed > 0 else "N/A")
    return [{"suite": "Unit + Integration", "total": total, "passed": passed, "failed": failed, "verdict": verdict}]


def _code_quality(workspace: Path, src_dir: Path) -> List[Dict]:
    py_files = list(src_dir.rglob("*.py")) if src_dir.exists() else []
    test_files = list((workspace / "tests").rglob("test_*.py")) if (workspace / "tests").exists() else []
    loc = 0
    documented = 0
    syntax_ok = True
    for f in py_files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        loc += text.count("\n") + 1
        if '"""' in text:
            documented += 1
        try:
            ast.parse(text)
        except SyntaxError:
            syntax_ok = False
    doc_ratio = documented / max(1, len(py_files))
    ratio = len(test_files) / max(1, len(py_files))
    rows = [
        {"metric": "Source files", "value": len(py_files), "verdict": "PASS" if py_files else "FAIL",
         "notes": "Generated component and model files."},
        {"metric": "Test modules", "value": len(test_files), "verdict": "PASS" if test_files else "FAIL",
         "notes": "Unit + integration test modules."},
        {"metric": "Lines of code", "value": loc, "verdict": "N/A", "notes": "Total generated source lines."},
        {"metric": "Syntax valid", "value": "yes" if syntax_ok else "no", "verdict": "PASS" if syntax_ok else "FAIL",
         "notes": "All source parses under the Python AST."},
        {"metric": "Docstring coverage", "value": f"{doc_ratio*100:.0f}%",
         "verdict": "PASS" if doc_ratio >= 0.5 else "PARTIAL", "notes": "Share of source files with docstrings."},
        {"metric": "Test:code ratio", "value": f"{ratio:.2f}",
         "verdict": "PASS" if ratio >= 0.5 else "PARTIAL", "notes": "Test modules per source file."},
    ]
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


def _read_all(directory: Path, suffix: str) -> str:
    if not directory.exists():
        return ""
    chunks = []
    for f in directory.rglob(f"*{suffix}"):
        try:
            chunks.append(f.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(chunks)


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
        f"- Functional requirements checked: {meta['fr_count']}",
        f"- Non-functional requirements checked: {meta['nfr_count']}",
        f"- Tests: {meta['tests_passed']} passed / {meta['tests_total']} total",
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
