"""Supported programming languages and their unit-test frameworks.

This module is the single source of truth for which languages the app can
generate for, which unit-test frameworks each language supports (and which is
the default), and small facts the code generators and validators need (file
extension, whether tests are executable on the current host, the build manifest
file name and the command used to build/run the tests).

It is pure-Python, dependency-free and deterministic so it works identically on
any edge device with no model and no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TestFramework:
    """A unit-test framework that can be selected for a language."""

    id: str
    display: str
    # Shell command (as a list template) used to execute the tests, or None when
    # execution is not wired up (the artifacts are still generated).
    run_cmd: Optional[Tuple[str, ...]] = None
    # The tool whose presence on PATH is required to run the tests.
    toolchain: str = ""


@dataclass(frozen=True)
class LanguageProfile:
    """Everything the app needs to know about a target language."""

    id: str
    display: str
    ext: str  # primary source-file extension, e.g. ".rs"
    line_comment: str  # e.g. "//" or "#"
    frameworks: Tuple[TestFramework, ...]
    # Can generated tests actually be executed by this process' interpreter?
    # Only Python runs in-process; everything else needs an external toolchain
    # that may or may not be installed on the device.
    runnable_in_process: bool = False
    manifest_name: str = ""  # Cargo.toml / pom.xml / build.gradle.kts / CMakeLists.txt
    docs_layout: str = ""  # human-readable package-layout hint for the SAD/design

    @property
    def default_framework(self) -> TestFramework:
        return self.frameworks[0]

    def framework_ids(self) -> List[str]:
        return [f.id for f in self.frameworks]

    def framework(self, framework_id: str) -> TestFramework:
        for f in self.frameworks:
            if f.id == framework_id:
                return f
        return self.default_framework


# ---------------------------------------------------------------------------
# Framework definitions
# ---------------------------------------------------------------------------

_PYTEST = TestFramework("pytest", "pytest", ("{py}", "-m", "pytest"), "pytest")
_UNITTEST = TestFramework("unittest", "unittest (stdlib)", ("{py}", "-m", "unittest", "discover"), "python")
_CARGO = TestFramework("cargo-test", "cargo test (built-in)", ("cargo", "test"), "cargo")
_JUNIT5 = TestFramework("junit5", "JUnit 5 (Jupiter)", ("mvn", "-q", "test"), "mvn")
_JUNIT4 = TestFramework("junit4", "JUnit 4", ("mvn", "-q", "test"), "mvn")
_TESTNG = TestFramework("testng", "TestNG", ("mvn", "-q", "test"), "mvn")
_KOTEST = TestFramework("kotest", "Kotest", ("gradle", "test"), "gradle")
_KT_JUNIT5 = TestFramework("junit5", "JUnit 5", ("gradle", "test"), "gradle")
_GTEST = TestFramework("gtest", "GoogleTest (gtest)", ("ctest", "--test-dir", "build"), "cmake")
_CATCH2 = TestFramework("catch2", "Catch2", ("ctest", "--test-dir", "build"), "cmake")


# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------

LANGUAGES: Dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        id="python",
        display="Python",
        ext=".py",
        line_comment="#",
        frameworks=(_PYTEST, _UNITTEST),
        runnable_in_process=True,
        manifest_name="pyproject.toml",
        docs_layout="src/<pkg>/ core.py + models.py; tests/unit/ and tests/integration/",
    ),
    "rust": LanguageProfile(
        id="rust",
        display="Rust",
        ext=".rs",
        line_comment="//",
        frameworks=(_CARGO,),
        runnable_in_process=False,
        manifest_name="Cargo.toml",
        docs_layout="Cargo.toml; src/lib.rs (with #[cfg(test)] unit tests); tests/ for integration tests",
    ),
    "java": LanguageProfile(
        id="java",
        display="Java",
        ext=".java",
        line_comment="//",
        frameworks=(_JUNIT5, _JUNIT4, _TESTNG),
        runnable_in_process=False,
        manifest_name="pom.xml",
        docs_layout="Maven layout: src/main/java/... and src/test/java/...",
    ),
    "kotlin": LanguageProfile(
        id="kotlin",
        display="Kotlin",
        ext=".kt",
        line_comment="//",
        frameworks=(_KOTEST, _KT_JUNIT5),
        runnable_in_process=False,
        manifest_name="build.gradle.kts",
        docs_layout="Gradle layout: src/main/kotlin/... and src/test/kotlin/...",
    ),
    "c": LanguageProfile(
        id="c",
        display="C",
        ext=".c",
        line_comment="//",
        frameworks=(_GTEST,),
        runnable_in_process=False,
        manifest_name="CMakeLists.txt",
        docs_layout="CMake layout: include/ headers, src/ sources, tests/ GoogleTest cases",
    ),
    "cpp": LanguageProfile(
        id="cpp",
        display="C++",
        ext=".cpp",
        line_comment="//",
        frameworks=(_GTEST, _CATCH2),
        runnable_in_process=False,
        manifest_name="CMakeLists.txt",
        docs_layout="CMake layout: include/ headers, src/ sources, tests/ GoogleTest cases",
    ),
}

# Preferred display order for the UI (matches the product's supported set).
LANGUAGE_ORDER: Tuple[str, ...] = ("python", "c", "cpp", "java", "rust", "kotlin")

# Aliases so older/other spellings still resolve to a supported profile.
_ALIASES = {
    "py": "python",
    "python3": "python",
    "c++": "cpp",
    "cxx": "cpp",
    "cplusplus": "cpp",
    "rs": "rust",
    "kt": "kotlin",
    "jvm": "java",
}


def normalize_language(language: str) -> str:
    """Return a canonical, supported language id (falls back to ``python``)."""

    key = (language or "").strip().lower()
    key = _ALIASES.get(key, key)
    return key if key in LANGUAGES else "python"


def get_language(language: str) -> LanguageProfile:
    """Return the :class:`LanguageProfile` for ``language`` (falls back to Python)."""

    return LANGUAGES[normalize_language(language)]


def resolve_framework(language: str, framework_id: str) -> TestFramework:
    """Resolve a framework for a language, honouring ``"auto"`` / unknown ids.

    ``"auto"`` (or any id not valid for the language) resolves to the language's
    default framework, so a stale selection never breaks a run.
    """

    profile = get_language(language)
    if not framework_id or framework_id == "auto":
        return profile.default_framework
    return profile.framework(framework_id)


def framework_choices(language: str) -> List[Tuple[str, str]]:
    """Return ``[(id, display), ...]`` test-framework choices for a language."""

    return [(f.id, f.display) for f in get_language(language).frameworks]
