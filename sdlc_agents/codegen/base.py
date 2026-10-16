"""Shared naming helpers and the code-generator interface.

Each language generator turns a :class:`~sdlc_agents.analysis.ProjectSpec` plus a
selected :class:`~sdlc_agents.languages.TestFramework` into real, idiomatic
artifacts: source, unit tests, integration tests and a build manifest. The
generators are deterministic and dependency-free so they run fully offline.
"""

from __future__ import annotations

import keyword
import re
from typing import List

from ..analysis import ProjectSpec
from ..languages import TestFramework
from ..types import Artifact


# ---------------------------------------------------------------------------
# naming helpers (language-aware casing)
# ---------------------------------------------------------------------------


def _words(text: str) -> List[str]:
    return [w for w in re.split(r"[^A-Za-z0-9]+", text) if w]


def snake(text: str) -> str:
    ident = re.sub(r"[^a-z0-9_]+", "_", (text or "").lower()).strip("_")
    if not ident or ident[0].isdigit() or keyword.iskeyword(ident):
        ident = f"app_{ident}" if ident else "app"
    return ident


def pascal(text: str) -> str:
    camel = "".join(w[:1].upper() + w[1:] for w in _words(text)) or "App"
    if camel[0].isdigit():
        camel = "App" + camel
    return camel


def camel(text: str) -> str:
    p = pascal(text)
    return p[:1].lower() + p[1:]


def pkg_name(spec: ProjectSpec) -> str:
    return snake(spec.slug) or "app"


def core_class(spec: ProjectSpec) -> str:
    return pascal(spec.title) + "Service"


def operation_idents(spec: ProjectSpec, limit: int = 3) -> List[str]:
    """Distinct, safe operation identifiers derived from the spec."""

    reserved = {"process", "report", "validate", "record", "count", "new"}
    seen: List[str] = []
    for op in spec.operations:
        ident = snake(op)
        if ident in reserved or ident in seen:
            continue
        seen.append(ident)
    if not seen:
        seen = ["handle_request"]
    return seen[:limit]


# ---------------------------------------------------------------------------
# generator interface
# ---------------------------------------------------------------------------


class CodeGenerator:
    """Base class for a per-language, offline, deterministic generator."""

    language_id: str = "base"

    # -- artifacts ---------------------------------------------------------

    def source_files(self, spec: ProjectSpec) -> List[Artifact]:  # pragma: no cover
        raise NotImplementedError

    def unit_tests(self, spec: ProjectSpec, framework: TestFramework) -> List[Artifact]:  # pragma: no cover
        raise NotImplementedError

    def integration_tests(self, spec: ProjectSpec, framework: TestFramework) -> List[Artifact]:  # pragma: no cover
        raise NotImplementedError

    def build_manifest(self, spec: ProjectSpec, framework: TestFramework) -> List[Artifact]:
        """Build/package manifest (Cargo.toml, pom.xml, ...). Default: none."""

        return []

    # -- docs --------------------------------------------------------------

    def component_design(self, spec: ProjectSpec, framework: TestFramework) -> str:  # pragma: no cover
        raise NotImplementedError
