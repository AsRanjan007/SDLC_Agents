"""Tests for the language registry and framework resolution."""

import pytest

from sdlc_agents import languages as L


REQUIRED = {"python", "c", "cpp", "java", "rust", "kotlin"}


def test_all_required_languages_supported():
    assert REQUIRED.issubset(set(L.LANGUAGES))
    assert set(L.LANGUAGE_ORDER) == REQUIRED


def test_default_frameworks_match_product_requirements():
    assert L.get_language("rust").default_framework.id == "cargo-test"
    assert L.get_language("java").default_framework.id == "junit5"
    assert L.get_language("kotlin").default_framework.id == "kotest"
    assert L.get_language("c").default_framework.id == "gtest"
    assert L.get_language("cpp").default_framework.id == "gtest"
    assert L.get_language("python").default_framework.id == "pytest"


def test_python_supports_pytest_and_unittest():
    assert L.get_language("python").framework_ids() == ["pytest", "unittest"]


@pytest.mark.parametrize("alias,expected", [
    ("Python", "python"), ("py", "python"), ("C++", "cpp"), ("c++", "cpp"),
    ("rs", "rust"), ("kt", "kotlin"), ("unknown-lang", "python"),
])
def test_normalize_language_aliases(alias, expected):
    assert L.normalize_language(alias) == expected


def test_resolve_framework_auto_and_invalid_fall_back_to_default():
    assert L.resolve_framework("rust", "auto").id == "cargo-test"
    assert L.resolve_framework("java", "nonexistent").id == "junit5"
    assert L.resolve_framework("kotlin", "junit5").id == "junit5"  # valid alt


def test_framework_choices_shape():
    choices = L.framework_choices("cpp")
    assert ("gtest", "GoogleTest (gtest)") in choices
    assert all(isinstance(c, tuple) and len(c) == 2 for c in choices)
