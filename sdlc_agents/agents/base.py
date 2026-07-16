"""Base agent: shared plumbing for LLM-or-offline artifact generation."""

from __future__ import annotations

import ast
import json
import re
from typing import List, Optional

from ..analysis import ProjectSpec
from ..llm.base import LLMBackend
from ..types import AgentResult, Artifact, RunContext


# Convention the LLM is asked to follow when emitting files.
_FILE_BLOCK = re.compile(
    r"===\s*FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<body>.*?)\n===\s*END FILE\s*===",
    re.DOTALL,
)


class BaseAgent:
    agent_id: str = "base"
    role_title: str = "Agent"

    def __init__(self, llm: Optional[LLMBackend] = None, generation=None):
        self.llm = llm
        self.generation = generation  # GenerationConfig or None

    # ---- LLM helpers -----------------------------------------------------

    def _use_llm(self) -> bool:
        return self.llm is not None

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
            lang = "python" if path.endswith(".py") else "text"
            artifacts.append(Artifact(path=path, content=body, kind="code", language=lang))
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

    # ---- interface -------------------------------------------------------

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:  # pragma: no cover
        raise NotImplementedError
