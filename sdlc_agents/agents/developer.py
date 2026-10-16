"""Software Developer agent.

Produces a component design, source code, unit tests, integration tests and a
build/validation report for the **configured target language and unit-test
framework**, then executes the tests with the correct toolchain (pytest for
Python, ``cargo test`` for Rust, Maven/Gradle for Java/Kotlin, CMake/CTest for
C/C++).

When an LLM is configured (e.g. a local Ollama endpoint) it is asked to author
the implementation, and this agent makes LLM mode robust:

1. The model is given the exact per-language project layout and told which build
   manifest and unit-test framework to use.
2. A missing build manifest is backfilled from the deterministic generator so
   the toolchain can always build the project.
3. The real toolchain is executed to verify the result. If the model's code does
   not build or its tests fail (and a toolchain is present), the agent falls back
   to the deterministic scaffold and re-runs, so the delivery that ships is
   always one that builds and passes. Python output is additionally AST-checked
   before it is trusted.
"""

from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path
from typing import List

from .. import codegen, engineering
from ..analysis import ProjectSpec
from ..languages import get_language
from ..testrunner import run_tests
from ..types import AgentResult, Artifact, RunContext
from .base import BaseAgent

_SYSTEM = (
    "You are a meticulous Software Developer. You implement the architecture in "
    "the requested language and unit-test framework with clean, tested, "
    "dependency-light code that builds and runs offline. Emit each file wrapped "
    "exactly as:\n=== FILE: <path> ===\n<content>\n=== END FILE ===\n"
    "Include the build manifest, the source, unit tests and integration tests, "
    "each in the exact idiomatic location for the language so the project builds "
    "and its tests run with the standard toolchain."
)

# Test statuses that mean the delivered code is not verifiably good and we should
# fall back to the deterministic scaffold (only when a toolchain actually ran).
_FALLBACK_STATUSES = {"failed", "error", "no-tests", "unknown"}


class _DevDefaults:
    generate_unit_tests = True
    generate_integration_tests = True
    include_build_manifest = True
    run_tests = True


class DeveloperAgent(BaseAgent):
    agent_id = "developer"
    role_title = "Software Developer"

    def _dev_cfg(self):
        agents = getattr(self.config, "agents", None)
        return getattr(agents, "developer", None) or _DevDefaults()

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:
        lang = self._target_language(spec)
        profile = get_language(lang)
        framework = self._framework(spec)
        dev = self._dev_cfg()

        base_design = codegen.component_design(spec, framework.id)

        # The deterministic scaffold is always available and always runnable.
        scaffold = codegen.generate_project(
            spec,
            framework.id,
            unit_tests=getattr(dev, "generate_unit_tests", True),
            integration_tests=getattr(dev, "generate_integration_tests", True),
            build_manifest=getattr(dev, "include_build_manifest", True),
        )

        chosen = scaffold
        code_source = "offline engine"
        used_llm = False

        if self._use_llm():
            prompt = (
                self._context_block(spec)
                + f"Implement the system in {profile.display} using the "
                f"{framework.display} unit-test framework. Follow this exact "
                f"project layout and build/test setup so the standard toolchain "
                f"can build and run it:\n\n{base_design}\n\n"
                "Emit the build manifest, the source code, the unit tests and the "
                "integration tests using the FILE block format."
            )
            text = self._generate(_SYSTEM, prompt)
            parsed = self._parse_file_blocks(text)
            if self._llm_output_valid(spec, parsed):
                chosen = self._ensure_runnable(parsed, spec, profile, framework)
                code_source = f"LLM ({self.llm.name})"
                used_llm = True

        # Add design-ID banners to the code and 'Covers:' links to the tests,
        # then persist so we can actually build/run the project.
        code_artifacts, design = _prepare(spec, chosen, lang)
        _write_code(ctx, code_artifacts)

        run_enabled = getattr(dev, "run_tests", True)
        test_summary = _run_or_skip(run_enabled, ctx.workspace, lang, framework.id)

        # Robustness: if the LLM's code was actually executed and did not pass,
        # fall back to the deterministic scaffold and re-verify.
        if used_llm and run_enabled and test_summary.get("status") in _FALLBACK_STATUSES:
            _clean_code(ctx.workspace, code_artifacts)
            code_source = f"LLM output failed {framework.display} verification — fell back to offline scaffold"
            code_artifacts, design = _prepare(spec, scaffold, lang)
            _write_code(ctx, code_artifacts)
            test_summary = run_tests(ctx.workspace, lang, framework.id)

        # Engineering analysis over the FINAL code.
        models = engineering.extract_code_model(code_artifacts, lang)
        findings = engineering.static_analysis(code_artifacts, lang)
        coverage = engineering.measure_coverage(ctx.workspace, lang) if run_enabled else {
            "measured": False, "note": "Coverage skipped — test execution disabled in Developer config."}

        design_doc = base_design + engineering.render_design_supplement(spec, code_artifacts, design, models)
        design_artifact = Artifact(path="docs/design/Component_Design.md", content=design_doc,
                                   kind="doc", language="markdown")

        build_report = _render_build_report(
            spec, profile.display, framework.display, code_artifacts, test_summary, code_source,
            findings, coverage, design, lang,
        )
        report_artifact = Artifact(path="docs/reports/Developer_Build_Report.md",
                                   content=build_report, kind="report", language="markdown")
        if ctx.write_artifact:
            ctx.write_artifact(design_artifact)
            ctx.write_artifact(report_artifact)

        artifacts: List[Artifact] = [design_artifact] + code_artifacts + [report_artifact]

        n_code = sum(1 for a in code_artifacts if a.kind == "code")
        n_tests = sum(1 for a in code_artifacts if a.kind == "test")
        sev = {s: sum(1 for f in findings if f.severity == s) for s in ("BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO")}
        overall_cov = (coverage.get("overall") or {}).get("pct") if coverage.get("measured") else None
        narration = (
            f"The Software Developer agent implemented {spec.title} in "
            f"{profile.display} ({code_source}), produced a class and sequence "
            f"diagram from the code with full design-ID traceability, ran the "
            f"{framework.display} suite (status {test_summary.get('status')}, "
            f"{test_summary.get('passed', 0)}/{test_summary.get('total', 0)}), "
            f"performed a SonarQube-style static analysis "
            f"({sum(sev.values())} findings) and measured code coverage"
            + (f" (overall {overall_cov}%)." if overall_cov is not None else ".")
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=(
                f"{profile.display} code + {framework.display} tests via {code_source}; "
                f"tests {test_summary.get('status', 'unknown')} "
                f"({test_summary.get('passed', 0)}/{test_summary.get('total', 0)}); "
                f"static findings {sum(sev.values())}"
                + (f"; coverage {overall_cov}%" if overall_cov is not None else "") + "."
            ),
            artifacts=artifacts,
            metrics={
                "language": profile.display,
                "test_framework": framework.display,
                "code_files": n_code,
                "test_files": n_tests,
                "design_elements": len(design.elements),
                "test_status": test_summary.get("status"),
                "tests_passed": test_summary.get("passed"),
                "tests_failed": test_summary.get("failed"),
                "tests_total": test_summary.get("total"),
                "static_findings": sum(sev.values()),
                "static_major_plus": sev["BLOCKER"] + sev["CRITICAL"] + sev["MAJOR"],
                "coverage_overall": overall_cov,
                "source": code_source,
                "_test_summary": test_summary,
            },
            narration=narration,
        )

    # ---- helpers ---------------------------------------------------------

    def _ensure_runnable(self, artifacts, spec, profile, framework) -> List[Artifact]:
        """Backfill pieces the toolchain needs but the LLM may have omitted."""

        arts = list(artifacts)
        if profile.id == "python":
            return _ensure_conftest(arts)
        manifest = profile.manifest_name
        if manifest and not any(a.path.split("/")[-1] == manifest for a in arts):
            arts += codegen.get_generator(profile.id).build_manifest(spec, framework)
        return arts


def _prepare(spec: ProjectSpec, raw: List[Artifact], lang: str):
    """Build the design model and annotate code/tests with traceability."""

    design = engineering.build_design(spec, raw)
    annotated = engineering.annotate_traceability(raw, spec, design, lang)
    return annotated, design


def _run_or_skip(run_enabled: bool, workspace, lang: str, framework_id: str):
    if run_enabled:
        return run_tests(workspace, lang, framework_id)
    return {"status": "skipped", "total": 0, "passed": 0, "failed": 0,
            "detail": "Test execution disabled in Developer configuration."}


def _write_code(ctx: RunContext, code_artifacts: List[Artifact]) -> None:
    if not ctx.write_artifact:
        return
    for art in code_artifacts:
        ctx.write_artifact(art)


def _clean_code(workspace: Path, code_artifacts: List[Artifact]) -> None:
    """Remove a previous (LLM) attempt's files before writing the fallback."""

    for art in code_artifacts:
        fp = workspace / art.path
        try:
            if fp.is_file():
                fp.unlink()
        except OSError:
            pass
    # Drop any stale CMake build tree so the fallback reconfigures cleanly.
    build_dir = workspace / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir, ignore_errors=True)


def _render_build_report(spec, language, framework, code_artifacts, test_summary,
                         code_source, findings, coverage, design, lang) -> str:
    ts = test_summary or {}
    files = "\n".join(f"- `{a.path}`" for a in code_artifacts)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detail = str(ts.get("detail", "")).strip()
    detail_block = f"\n\n```\n{detail[:1500]}\n```" if detail else ""
    head = f"""# Developer Build & Validation Report
## {spec.title}

*Generated by the Software Developer agent on {now}.*

- Target language: **{language}**
- Unit-test framework: **{framework}**
- Source of implementation: **{code_source}**
- Design elements: **{len(design.elements)}** (see the Component Design for the full traceability matrix)

## Delivered Artifacts
{files}

## Operations Implemented
{", ".join(spec.operations)}

## Local Test Execution
- Status: **{ts.get("status", "not-run")}**
- Total: {ts.get("total", "-")} | Passed: {ts.get("passed", "-")} | Failed: {ts.get("failed", "-")}{detail_block}

"""
    static = engineering.render_static_report(findings, lang)
    cov = engineering.render_coverage(coverage)
    trace = "## Traceability summary\n" + engineering.render_traceability_matrix(spec, design)
    notes = (
        "## Notes\n"
        "Tests run with the language's own toolchain (pytest, cargo, Maven, Gradle "
        "or CMake/CTest). The static-analysis pass uses an offline SonarQube-style "
        "rule set; coverage for Python is measured with a stdlib tracer, and for "
        "other languages with the standard coverage tool on a toolchain host. The "
        "Validation Engineer agent independently re-checks the delivery.\n"
    )
    return head + static + "\n" + cov + "\n" + trace + "\n" + notes


def _ensure_conftest(artifacts: List[Artifact]) -> List[Artifact]:
    if any(a.path.endswith("conftest.py") for a in artifacts):
        return artifacts
    conftest = Artifact(
        path="conftest.py",
        content=(
            "import os, sys\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))\n"
        ),
        kind="code",
        language="python",
    )
    return artifacts + [conftest]
