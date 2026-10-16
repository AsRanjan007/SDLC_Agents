"""Architect agent: produces the Software Architecture Document."""

from __future__ import annotations

from typing import List

from ..analysis import ProjectSpec
from ..llm import offline_engine
from ..types import AgentResult, Artifact, RunContext
from .base import BaseAgent

_SYSTEM = (
    "You are a seasoned Software Architect. You design clear, pragmatic "
    "architectures for offline, edge-deployed systems. You write a complete "
    "Software Architecture Document (SAD) in Markdown with sections for context, "
    "components, data flow, functional requirements, quality attributes (NFRs), "
    "decisions, risks and traceability. You ALWAYS include an 'Architecture "
    "Diagrams' section containing five Mermaid diagrams, each in its own "
    "```mermaid code block: (1) overall architecture, (2) component diagram, "
    "(3) data flow diagram, (4) sequence diagram (use `sequenceDiagram`), and "
    "(5) use case diagram. Ground every statement in the provided project "
    "context. Do not invent external network dependencies."
)

# Markers used to confirm the LLM actually produced the full diagram suite.
def _has_all_diagrams(doc: str) -> bool:
    low = doc.lower()
    return (
        doc.count("```mermaid") >= 4
        and "sequencediagram" in low
        and ("use case" in low or "usecase" in low or "use-case" in low)
    )


class ArchitectAgent(BaseAgent):
    agent_id = "architect"
    role_title = "Software Architect"

    def _arch_cfg(self):
        agents = getattr(self.config, "agents", None)
        return getattr(agents, "architect", None)

    def run(self, spec: ProjectSpec, prior: List[AgentResult], ctx: RunContext) -> AgentResult:
        arch = self._arch_cfg()
        framework = self._framework(spec)
        doc = ""
        source = "offline engine"
        want_diagrams = getattr(arch, "include_diagrams", True)
        if self._use_llm():
            prompt = (
                self._context_block(spec)
                + f"The target language is {self._target_language(spec)} and the "
                f"unit-test framework is {framework.display}. "
                + "Write the full Software Architecture Document in Markdown now. "
                "Include an 'Architecture Diagrams' section with FIVE Mermaid "
                "diagrams, each in its own ```mermaid block: overall architecture, "
                "component, data flow, sequence (sequenceDiagram) and use case."
            )
            doc = self._generate(_SYSTEM, prompt).strip()
            if len(doc) > 400 and doc.lower().count("#") >= 3:
                source = f"LLM ({self.llm.name})"
                # Ensure the diagram suite is present even if the model skipped it.
                if want_diagrams and not _has_all_diagrams(doc):
                    doc += (
                        "\n\n## Architecture Diagrams\n"
                        "*Diagram suite ensured by the Architect agent.*\n\n"
                        + offline_engine.render_diagrams(spec)
                    )
                    source += " + generated diagrams"
            else:
                doc = ""  # too thin -> fall back
        if not doc:
            doc = offline_engine.render_architecture_document(
                spec,
                framework_display=framework.display,
                detail_level=getattr(arch, "detail_level", "standard"),
                include_diagrams=want_diagrams,
                include_risks=getattr(arch, "include_risks", True),
                include_adrs=getattr(arch, "include_adrs", True),
            )

        artifact = Artifact(
            path="docs/architecture/Software_Architecture_Document.md",
            content=doc,
            kind="doc",
            language="markdown",
        )
        narration = (
            f"The Architect agent analysed the requirements for {spec.title} and "
            f"produced a Software Architecture Document. It defined "
            f"{len(spec.components)} components, mapped "
            f"{len(spec.nonfunctional_requirements)} non-functional requirements to "
            f"architectural tactics, and recorded the key design decisions and risks."
        )
        return AgentResult(
            agent_id=self.agent_id,
            role_title=self.role_title,
            summary=f"Architecture document produced via {source}.",
            artifacts=[artifact],
            metrics={
                "components": len(spec.components),
                "nfrs": len(spec.nonfunctional_requirements),
                "source": source,
            },
            narration=narration,
        )
