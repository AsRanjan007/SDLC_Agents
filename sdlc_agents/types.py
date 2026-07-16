"""Shared, dependency-light data types used across the app."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class Artifact:
    """A single generated file to be written into the run workspace."""

    path: str  # workspace-relative path, e.g. "src/foo/core.py"
    content: str = ""
    kind: str = "file"  # "doc" | "code" | "test" | "report" | "excel" | "audio"
    language: str = "text"
    data: Optional[bytes] = None  # set for binary artifacts (xlsx, wav)

    @property
    def is_binary(self) -> bool:
        return self.data is not None


@dataclass
class AgentResult:
    """The outcome of one agent's run."""

    agent_id: str
    role_title: str
    summary: str
    artifacts: List[Artifact] = field(default_factory=list)
    metrics: Dict[str, object] = field(default_factory=dict)
    narration: str = ""  # plain-English narration of what the agent did


@dataclass
class RunContext:
    """Per-run execution context handed to each agent."""

    run_id: str
    workspace: Path
    # Persist an artifact to the workspace and return its absolute path.
    write_artifact: Optional[Callable[[Artifact], Path]] = None
