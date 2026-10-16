"""Base agent: shared plumbing for LLM-or-offline artifact generation."""

from __future__ import annotations

import ast
import json
import re
from typing import List, Optional

from ..analysis import ProjectSpec
from ..languages import get_language, resolve_framework
from ..llm.base import LLMBackend
from ..types import AgentResult, Artifact, RunContext


# Convention the LLM is asked to follow when emitting files.
_FILE_BLOCK = re.compile(
    r"===\s*FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<body>.*?)\n===\s*END FILE\s*===",
    re.DOTALL,
)

# File-extension -> artifact language label, for parsing LLM output.
_EXT_LANG = {
    ".py": "python", ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
    ".toml": "toml", ".xml": "xml", ".kts": "kotlin", ".txt": "text",
    ".md": "markdown",
}


class BaseAgent:
    agent_id: str = "base"
    role_title: str = "Agent"

    def __init__(self, llm: Optional[LLMBackend] = None, generation=None, config=None):
        self.llm = llm
        self.config = config  # AppConfig or None
        # Prefer an explicit GenerationConfig; otherwise read it off the config.
        self.generation = generation or getattr(config, "generation", None)

    # ---- config helpers --------------------------------------------------

    def _target_language(self, spec: ProjectSpec) -> str:
        return getattr(self.config, "target_language", None) or spec.language

    def _framework(self, spec: ProjectSpec):
        fw_id = getattr(self.config, "test_framework", "auto")
        return resolve_framework(self._target_language(spec), fw_id)

    # ---- LLM helpers -----------------------------------------------------

    def _use_llm(self) -> bool:
        return self.llm is not None

    def _llm_label(self) -> str:
        """Friendly backend identifier (model/endpoint), tolerant of test doubles."""

        return getattr(self.llm, "label", None) or getattr(self.llm, "name", "llm")

    def _generate(self, system: str, prompt: str) -> str:
        """Call the LLM; on any failure return '' so callers fall back offline."""

        if not self.llm:
            return ""
        try:
            max_tokens = getattr(self.generation, "max_tokens", 3072)
            temperature = getattr(self.generation, "temperature", 0.2)
            resp = self.llm.generate(system, prompt, max_tokens=max_tokens, temperature=temperature)
            return resp.text or ""
        except Exception:
            return ""

    @staticmethod
    def _context_block(spec: ProjectSpec) -> str:
        return (
            "Project context (JSON):\n```json\n"
            + json.dumps(spec.to_context(), indent=2)
            + "\n```\n"
        )

    # ---- file-block parsing / validation ---------------------------------

    @staticmethod
    def _parse_file_blocks(text: str) -> List[Artifact]:
        artifacts: List[Artifact] = []
        for m in _FILE_BLOCK.finditer(text or ""):
            path = m.group("path").strip().strip("`").lstrip("/")
            body = m.group("body")
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            lang = _EXT_LANG.get(ext, "text")
            kind = "test" if ("test" in path.lower() or "spec" in path.lower()) else "code"
            artifacts.append(Artifact(path=path, content=body, kind=kind, language=lang))
        return artifacts

    @staticmethod
    def _python_files_valid(artifacts: List[Artifact]) -> bool:
        py = [a for a in artifacts if a.path.endswith(".py")]
        if not py:
            return False
        for a in py:
            try:
                ast.parse(a.content)
            except SyntaxError:
                return False
        return True

    def _llm_output_valid(self, spec: ProjectSpec, artifacts: List[Artifact]) -> bool:
        """Validate parsed LLM artifacts before trusting them over the scaffold.

        Python is syntax-checked via the AST. For other languages (which we
        cannot compile here) we require at least one source file in the target
        language with non-trivial content, so malformed/empty output is rejected
        and the deterministic scaffold is used instead.
        """

        if not artifacts:
            return False
        profile = get_language(self._target_language(spec))
        if profile.id == "python":
            return self._python_files_valid(artifacts)
        source = [a for a in artifacts if a.path.endswith(profile.ext) and len(a.content.strip()) > 40]
        return bool(source)

    # ---- interface -------------------------------------------------------

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:  # pragma: no cover
        raise NotImplementedError
