"""Software Developer agent.

Produces component design, source code, unit tests and integration tests, then
executes the tests locally and writes a build/validation report. When an LLM is
configured it is asked to author the implementation; any output that does not
parse as valid Python is discarded in favour of the deterministic scaffold so
the delivery always compiles and runs.
"""

from __future__ import annotations

from typing import List

from ..analysis import ProjectSpec
from ..llm import offline_engine
from ..testrunner import run_pytest
from ..types import AgentResult, Artifact, RunContext
from .base import BaseAgent

_SYSTEM = (
    "You are a meticulous Software Developer. You implement the architecture in "
    "the requested language with clean, tested, dependency-light code that runs "
    "offline. Emit each file wrapped exactly as:\n"
    "=== FILE: <path> ===\n<content>\n=== END FILE ===\n"
    "Always include source under src/, unit tests under tests/unit/, integration "
    "tests under tests/integration/, and a conftest.py that puts src/ on sys.path."
)


class DeveloperAgent(BaseAgent):
    agent_id = "developer"
    role_title = "Software Developer"

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:
        design = offline_engine.render_component_design(spec)
        code_source = "offline engine"

        code_artifacts: List[Artifact] = []
        if self._use_llm():
            prompt = (
                self._context_block(spec)
                + f"Implement the system in {spec.language}. Provide source code, "
                "unit tests and integration tests using the FILE block format."
            )
            text = self._generate(_SYSTEM, prompt)
            parsed = self._parse_file_blocks(text)
            if parsed and self._python_files_valid(parsed):
                code_artifacts = _ensure_conftest(parsed)
                code_source = f"LLM ({self.llm.name})"

        if not code_artifacts:
            code_artifacts = (
                offline_engine.render_source_files(spec)
                + offline_engine.render_unit_tests(spec)
                + offline_engine.render_integration_tests(spec)
            )

        artifacts: List[Artifact] = [
            Artifact(
                path="docs/design/Component_Design.md",
                content=design,
                kind="doc",
                language="markdown",
            )
        ] + code_artifacts

        # Persist code + tests to disk so we can actually run them.
        if ctx.write_artifact:
            for art in artifacts:
                ctx.write_artifact(art)

        test_summary = run_pytest(ctx.workspace)

        build_report = offline_engine.render_build_report(spec, test_summary)
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
            f"The Software Developer agent designed the components and implemented "
            f"{n_code} source files with {n_tests} test modules. It then executed "
            f"the test suite locally: {test_summary.get('passed', 0)} passed, "
            f"{test_summary.get('failed', 0)} failed out of "
            f"{test_summary.get('total', 0)} tests."
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=(
                f"Code + tests produced via {code_source}; tests "
                f"{test_summary.get('status', 'unknown')} "
                f"({test_summary.get('passed', 0)}/{test_summary.get('total', 0)})."
            ),
            artifacts=artifacts,
            metrics={
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
