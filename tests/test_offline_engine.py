import ast

from sdlc_agents.analysis import analyze
from sdlc_agents.llm import offline_engine


def _spec():
    return analyze(
        "Create, validate and store user records, then generate a report.",
        "user record json",
        "stored record and report",
        "python",
    )


def test_architecture_document_has_sections():
    doc = offline_engine.render_architecture_document(_spec())
    for heading in ("Software Architecture Document", "Component", "Non-Functional", "Traceability"):
        assert heading in doc


def test_generated_source_is_valid_python():
    spec = _spec()
    for art in offline_engine.render_source_files(spec):
        if art.path.endswith(".py"):
            ast.parse(art.content)  # raises SyntaxError on failure


def test_generated_tests_are_valid_python():
    spec = _spec()
    for art in offline_engine.render_unit_tests(spec) + offline_engine.render_integration_tests(spec):
        ast.parse(art.content)


def test_class_and_pkg_names_are_identifiers():
    spec = _spec()
    assert offline_engine.pkg_name(spec).isidentifier()
    assert offline_engine.class_name(spec).isidentifier()


def test_build_report_includes_status():
    spec = _spec()
    report = offline_engine.render_build_report(spec, {"status": "passed", "passed": 5, "failed": 0, "total": 5})
    assert "passed" in report
    assert "5" in report
