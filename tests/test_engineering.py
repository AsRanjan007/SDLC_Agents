"""Tests for the Developer-side engineering analysis."""

from sdlc_agents import engineering as E
from sdlc_agents.analysis import analyze
from sdlc_agents.types import Artifact


def _spec(lang="python"):
    return analyze("Build a calculator for +,-,*,/. Validate input and compute result.",
                   "two operands and an operator", "result or error", lang)


def _py_source():
    return Artifact(
        path="src/app/core.py",
        content=(
            '"""Core."""\n'
            "class CalcService:\n"
            "    def __init__(self):\n"
            "        self.audit = []\n"
            "    def validate(self, x):\n"
            "        return []\n"
            "    def process(self, x):\n"
            "        self.audit.append('process')\n"
            "        return True\n"
            "    def count(self):\n"
            "        return len(self.audit)\n"
        ),
        kind="code", language="python",
    )


def _py_test():
    return Artifact(path="tests/unit/test_core.py",
                    content="def test_ok():\n    assert True\n", kind="test", language="python")


# ---- code model + diagrams ------------------------------------------------


def test_extract_python_class_model():
    models = E.extract_code_model([_py_source()], "python")
    assert len(models) == 1
    m = models[0]
    assert m.name == "CalcService"
    assert "validate" in m.methods and "process" in m.methods and "count" in m.methods
    assert "audit" in m.fields


def test_class_and_sequence_diagrams_render():
    models = E.extract_code_model([_py_source()], "python")
    cd = E.render_class_diagram(models)
    assert "classDiagram" in cd and "CalcService" in cd and "+validate()" in cd
    sd = E.render_code_sequence(models)
    assert "sequenceDiagram" in sd and "process(input)" in sd


def test_design_patterns_mentions_layered_and_service():
    models = E.extract_code_model([_py_source()], "python")
    patterns = " ".join(E.design_patterns(models))
    assert "Layered architecture" in patterns
    assert "Service" in patterns


# ---- traceability ---------------------------------------------------------


def test_build_design_assigns_ids_and_core():
    spec = _spec()
    arts = [_py_source(), _py_test()]
    design = E.build_design(spec, arts)
    assert design.core is not None
    assert design.core.design_id.startswith("DD-")
    assert any("C" in r for r in design.core.realises)
    assert design.core.req_refs  # FRs traced to the core


def test_annotation_adds_banner_and_covers():
    spec = _spec()
    arts = [_py_source(), _py_test()]
    design = E.build_design(spec, arts)
    annotated = E.annotate_traceability(arts, spec, design, "python")
    src = next(a for a in annotated if a.kind == "code")
    tst = next(a for a in annotated if a.kind == "test")
    assert src.content.splitlines()[0].startswith("# Design: DD-")
    assert "realises" in src.content.splitlines()[0]
    assert tst.content.splitlines()[0].startswith("# Covers: DD-")


def test_rust_annotation_uses_slash_comment():
    spec = _spec("rust")
    art = Artifact(path="src/lib.rs", content="pub struct S;\nimpl S { pub fn process(&self){} }\n",
                   kind="code", language="rust")
    design = E.build_design(spec, [art])
    annotated = E.annotate_traceability([art], spec, design, "rust")
    assert annotated[0].content.splitlines()[0].startswith("// Design: DD-")


def test_traceability_matrix_links_requirements_to_tests():
    spec = _spec()
    arts = [_py_source(), _py_test()]
    design = E.build_design(spec, arts)
    matrix = E.render_traceability_matrix(spec, design)
    assert "Architecture → Design → Code" in matrix
    assert "Requirement → Design → Code → Test" in matrix
    assert "FR-1" in matrix
    assert "tests/unit/test_core.py" in matrix


# ---- static analysis ------------------------------------------------------


def test_static_analysis_flags_bare_except_and_long_line():
    bad = Artifact(
        path="src/app/bad.py",
        content="def f():\n    try:\n        pass\n    except:\n        pass\n" + "x = '" + "a" * 130 + "'\n",
        kind="code", language="python",
    )
    findings = E.static_analysis([bad], "python")
    rules = {f.rule for f in findings}
    assert "S5754" in rules  # bare except
    assert "S103" in rules   # long line
    report = E.render_static_report(findings, "python")
    assert "Static Analysis (SonarQube-style)" in report
    assert "S5754" in report


def test_static_analysis_clean_scaffold_reports_zero():
    findings = E.static_analysis([_py_source(), _py_test()], "python")
    report = E.render_static_report(findings, "python")
    assert "Summary" in report


# ---- coverage -------------------------------------------------------------


def test_render_coverage_non_python_notes_tool():
    cov = {"measured": False, "tool": "JaCoCo", "note": "requires JaCoCo"}
    out = E.render_coverage(cov)
    assert "requires JaCoCo" in out


def test_measure_coverage_non_python_is_best_effort(tmp_path):
    cov = E.measure_coverage(tmp_path, "java")
    assert cov["measured"] is False
    assert "JaCoCo" in cov["tool"]


# ---- developer integration ------------------------------------------------


def test_developer_python_flow_measures_coverage_and_traceability():
    import tempfile
    import os
    os.environ["SDLC_AGENTS_HOME"] = tempfile.mkdtemp(prefix="sdlc_eng_it_")
    from sdlc_agents.agents import Orchestrator
    from sdlc_agents.config import AppConfig

    cfg = AppConfig()
    cfg.backend = "offline"
    cfg.audio.enabled = False
    cfg.target_language = "python"
    result = Orchestrator(cfg).run(
        "Build a calculator for +,-,*,/. Validate input and compute result.",
        "two operands and an operator", "result or error",
    )
    dev = next(r for r in result.results if r.agent_id == "developer")

    # Coverage was actually measured.
    assert isinstance(dev.metrics["coverage_overall"], (int, float))
    assert dev.metrics["coverage_overall"] > 0
    assert dev.metrics["static_findings"] >= 0
    assert dev.metrics["design_elements"] >= 1

    design = next(a for a in dev.artifacts if a.path.endswith("Component_Design.md")).content
    report = next(a for a in dev.artifacts if a.path.endswith("Developer_Build_Report.md")).content
    assert "classDiagram" in design and "sequenceDiagram" in design
    assert "Requirement → Design → Code → Test" in design
    assert "Static Analysis (SonarQube-style)" in report
    assert "Code Coverage" in report

    # Code carries a design-ID banner; the unit test carries a Covers link.
    core = next(a for a in dev.artifacts if a.path.endswith("core.py"))
    assert core.content.splitlines()[0].startswith("# Design: DD-")
    unit = next(a for a in dev.artifacts if "tests/unit" in a.path)
    assert unit.content.splitlines()[0].startswith("# Covers:")
