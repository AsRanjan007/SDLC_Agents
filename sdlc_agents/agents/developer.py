"""Software Developer agent.

Produces a component design, source code, unit tests, integration tests and a
build/validation report for the **configured target language and unit-test
framework**, then executes the tests when a toolchain is available. When an LLM
is configured it is asked to author the implementation; output that fails the
language-appropriate validity check is discarded in favour of the deterministic
scaffold so the delivery is always coherent.
"""

from __future__ import annotations

import datetime as _dt
from typing import List

from .. import codegen
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
    "each in the idiomatic location for the language."
)


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

        design = codegen.component_design(spec, framework.id)
        code_source = "offline engine"

        code_artifacts: List[Artifact] = []
        if self._use_llm():
            prompt = (
                self._context_block(spec)
                + f"Implement the system in {profile.display} using the "
                f"{framework.display} unit-test framework. Provide the build "
                "manifest, source code, unit tests and integration tests using "
                "the FILE block format."
            )
            text = self._generate(_SYSTEM, prompt)
            parsed = self._parse_file_blocks(text)
            if self._llm_output_valid(spec, parsed):
                code_artifacts = _ensure_conftest(parsed) if profile.id == "python" else parsed
                code_source = f"LLM ({self.llm.name})"

        if not code_artifacts:
            code_artifacts = codegen.generate_project(
                spec,
                framework.id,
                unit_tests=getattr(dev, "generate_unit_tests", True),
                integration_tests=getattr(dev, "generate_integration_tests", True),
                build_manifest=getattr(dev, "include_build_manifest", True),
            )

        artifacts: List[Artifact] = [
            Artifact(
                path="docs/design/Component_Design.md",
                content=design,
                kind="doc",
                language="markdown",
            )
        ] + code_artifacts

        # Persist code + tests to disk so we can actually build/run them.
        if ctx.write_artifact:
            for art in artifacts:
                ctx.write_artifact(art)

        if getattr(dev, "run_tests", True):
            test_summary = run_tests(ctx.workspace, lang, framework.id)
        else:
            test_summary = {
                "status": "skipped", "total": 0, "passed": 0, "failed": 0,
                "detail": "Test execution disabled in Developer configuration.",
            }

        build_report = _render_build_report(
            spec, profile.display, framework.display, code_artifacts, test_summary
        )
        report_artifact = Artifact(
            path="docs/reports/Developer_Build_Report.md",
            content=build_report,
            kind="report",
            language="markdown",
        )
        artifacts.append(report_artifact)
        if ctx.write_artifact:
            ctx.write_artifact(report_artifact)

        n_code = sum(1 for a in code_artifacts if a.kind == "code")
        n_tests = sum(1 for a in code_artifacts if a.kind == "test")
        narration = (
            f"The Software Developer agent implemented {spec.title} in "
            f"{profile.display}, producing {n_code} source/build files and "
            f"{n_tests} test modules using the {framework.display} framework. It "
            f"then ran the test suite: status {test_summary.get('status')} "
            f"({test_summary.get('passed', 0)} passed / "
            f"{test_summary.get('total', 0)} total)."
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=(
                f"{profile.display} code + {framework.display} tests via {code_source}; "
                f"tests {test_summary.get('status', 'unknown')} "
                f"({test_summary.get('passed', 0)}/{test_summary.get('total', 0)})."
            ),
            artifacts=artifacts,
            metrics={
                "language": profile.display,
                "test_framework": framework.display,
                "code_files": n_code,
                "test_files": n_tests,
                "test_status": test_summary.get("status"),
                "tests_passed": test_summary.get("passed"),
                "tests_failed": test_summary.get("failed"),
                "tests_total": test_summary.get("total"),
                "source": code_source,
                "_test_summary": test_summary,
            },
            narration=narration,
        )


def _render_build_report(spec, language, framework, code_artifacts, test_summary) -> str:
    ts = test_summary or {}
    files = "\n".join(f"- `{a.path}`" for a in code_artifacts)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detail = str(ts.get("detail", "")).strip()
    detail_block = f"\n\n```\n{detail[:1500]}\n```" if detail else ""
    return f"""# Developer Build & Validation Report
## {spec.title}

*Generated by the Software Developer agent on {now}.*

- Target language: **{language}**
- Unit-test framework: **{framework}**

## Delivered Artifacts
{files}

## Operations Implemented
{", ".join(spec.operations)}

## Local Test Execution
- Status: **{ts.get("status", "not-run")}**
- Total: {ts.get("total", "-")} | Passed: {ts.get("passed", "-")} | Failed: {ts.get("failed", "-")}{detail_block}

## Notes
Code is deterministic, dependency-light and designed to run offline. The
Validation Engineer agent independently re-checks the delivery and records the
outcome in the Excel validation report.
"""


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
