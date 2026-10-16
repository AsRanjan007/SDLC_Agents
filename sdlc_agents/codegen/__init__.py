"""Per-language, offline, deterministic code generation.

``generate_project`` assembles the full set of artifacts (source, unit tests,
integration tests and build manifest) for the configured language and test
framework, honouring the Developer agent's configuration flags.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..analysis import ProjectSpec
from ..languages import TestFramework, get_language, resolve_framework
from ..types import Artifact
from .base import CodeGenerator
from .c_gen import CGenerator
from .cpp_gen import CppGenerator
from .java_gen import JavaGenerator
from .kotlin_gen import KotlinGenerator
from .python_gen import PythonGenerator
from .rust_gen import RustGenerator

_GENERATORS: Dict[str, CodeGenerator] = {
    "python": PythonGenerator(),
    "rust": RustGenerator(),
    "java": JavaGenerator(),
    "kotlin": KotlinGenerator(),
    "c": CGenerator(),
    "cpp": CppGenerator(),
}


def get_generator(language: str) -> CodeGenerator:
    """Return the generator for ``language`` (falls back to Python)."""

    return _GENERATORS[get_language(language).id]


def component_design(spec: ProjectSpec, framework_id: str = "auto") -> str:
    """Render the language-appropriate component design document."""

    gen = get_generator(spec.language)
    fw = resolve_framework(spec.language, framework_id)
    return gen.component_design(spec, fw)


def generate_project(
    spec: ProjectSpec,
    framework_id: str = "auto",
    *,
    unit_tests: bool = True,
    integration_tests: bool = True,
    build_manifest: bool = True,
) -> List[Artifact]:
    """Generate the full artifact set for a project.

    The flags map directly to the Developer agent's configuration so a run only
    produces what the user asked for.
    """

    gen = get_generator(spec.language)
    fw: TestFramework = resolve_framework(spec.language, framework_id)

    artifacts: List[Artifact] = list(gen.source_files(spec))
    if unit_tests:
        artifacts += gen.unit_tests(spec, fw)
    if integration_tests:
        artifacts += gen.integration_tests(spec, fw)
    if build_manifest:
        artifacts += gen.build_manifest(spec, fw)
    return artifacts


__all__ = [
    "CodeGenerator",
    "get_generator",
    "generate_project",
    "component_design",
]
