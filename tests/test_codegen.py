"""Tests for the per-language code generators."""

import pytest

from sdlc_agents import codegen
from sdlc_agents.analysis import analyze
from sdlc_agents.languages import LANGUAGE_ORDER, get_language


def _spec(language):
    return analyze(
        "Read a number from input. Print Even if divisible by 2. Print Odd if not.",
        "an integer",
        "Even or Odd plus a validation report",
        language,
    )


@pytest.mark.parametrize("language", list(LANGUAGE_ORDER))
def test_generates_source_tests_and_manifest(language):
    spec = _spec(language)
    arts = codegen.generate_project(spec, "auto")
    paths = [a.path for a in arts]

    # At least one source file in the language's primary extension.
    ext = get_language(language).ext
    assert any(p.endswith(ext) for p in paths), f"no {ext} source for {language}"

    # A build manifest is present.
    manifest = get_language(language).manifest_name
    assert any(p.split("/")[-1] == manifest for p in paths), f"missing {manifest}"

    # At least one test artifact.
    assert any(a.kind == "test" for a in arts), f"no tests for {language}"

    # Nothing is empty.
    assert all(a.content.strip() for a in arts if not a.is_binary)


@pytest.mark.parametrize("language", list(LANGUAGE_ORDER))
def test_component_design_mentions_language(language):
    design = codegen.component_design(_spec(language), "auto")
    assert get_language(language).display in design
    assert "Build & Test" in design


def test_flags_toggle_artifacts():
    spec = _spec("rust")
    full = codegen.generate_project(spec, "auto")
    minimal = codegen.generate_project(
        spec, "auto", unit_tests=False, integration_tests=False, build_manifest=False
    )
    assert len(minimal) < len(full)
    assert not any(a.path == "Cargo.toml" for a in minimal)


def test_python_unittest_framework_emits_testcase():
    spec = _spec("python")
    arts = codegen.generate_project(spec, "unittest")
    unit = next(a for a in arts if a.path == "tests/unit/test_core.py")
    assert "import unittest" in unit.content
    assert "unittest.TestCase" in unit.content


def test_java_framework_selection_changes_imports():
    spec = _spec("java")
    j5 = codegen.generate_project(spec, "junit5")
    j4 = codegen.generate_project(spec, "junit4")
    j5_test = next(a for a in j5 if a.kind == "test")
    j4_test = next(a for a in j4 if a.kind == "test")
    assert "org.junit.jupiter.api.Test" in j5_test.content
    assert "org.junit.Test" in j4_test.content


def test_kotlin_kotest_uses_stringspec():
    spec = _spec("kotlin")
    arts = codegen.generate_project(spec, "kotest")
    test = next(a for a in arts if a.kind == "test")
    assert "io.kotest" in test.content
    assert "StringSpec" in test.content


def test_cpp_gtest_and_catch2_differ():
    spec = _spec("cpp")
    g = next(a for a in codegen.generate_project(spec, "gtest") if a.kind == "test")
    c = next(a for a in codegen.generate_project(spec, "catch2") if a.kind == "test")
    assert "gtest/gtest.h" in g.content
    assert "catch2" in c.content.lower()
