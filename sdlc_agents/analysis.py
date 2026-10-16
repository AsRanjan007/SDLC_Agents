"""Deterministic requirement analysis and agent planning.

This module turns free-text instructions + input/output expectations into a
structured :class:`ProjectSpec`, and derives **roles, tasks and prompts** for
each agent. It is pure-Python, dependency-free and deterministic, so it works
identically on any edge device with no model and no network.

The same :class:`ProjectSpec` is used two ways:

* the *offline engine* fills templates from it to produce real artifacts;
* the *LLM backends* embed it (as a compact JSON context block) inside their
  prompts so a real model produces grounded, on-topic output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# Verbs that commonly denote an operation/behaviour in a requirement.
_ACTION_VERBS = [
    "create", "read", "update", "delete", "add", "remove", "validate",
    "verify", "calculate", "compute", "generate", "parse", "convert",
    "transform", "send", "fetch", "store", "save", "load", "authenticate",
    "authorize", "encrypt", "decrypt", "sort", "filter", "search", "query",
    "upload", "download", "process", "analyze", "classify", "predict",
    "register", "login", "logout", "export", "import", "render", "schedule",
    "notify", "aggregate", "merge", "split", "select", "configure", "manage",
]

# Keyword -> canonical non-functional requirement.
_NFR_KEYWORDS = {
    "offline": "Operate fully offline with no external network dependency.",
    "edge": "Run on constrained edge hardware with a small resource footprint.",
    "proxy": "Function correctly inside a corporate network behind an HTTP proxy.",
    "secure": "Enforce security controls appropriate to the data handled.",
    "security": "Enforce security controls appropriate to the data handled.",
    "confidential": "Keep all generated artifacts confidential and local.",
    "privacy": "Preserve data privacy; no data leaves the device.",
    "encrypt": "Protect artifacts at rest via encryption.",
    "performance": "Meet responsiveness targets under expected load.",
    "latency": "Keep operation latency within acceptable bounds.",
    "throughput": "Sustain the required request/processing throughput.",
    "scalab": "Scale to the expected data and user volume.",
    "availab": "Remain available for the required operating window.",
    "reliab": "Behave reliably and recover gracefully from errors.",
    "usab": "Provide a clear, usable interface for the target users.",
    "portab": "Be portable across the supported target environments.",
    "maintain": "Be maintainable with clear structure and tests.",
    "accessib": "Meet accessibility expectations for all users.",
    "audit": "Provide auditable records of key actions.",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "with", "that", "which",
    "will", "should", "can", "be", "is", "are", "as", "on", "in", "into", "by",
    "from", "this", "it", "then", "so", "if", "any", "all", "such", "like",
    "provide", "want", "need", "using", "use", "based", "app", "application",
    "system", "software", "user", "users", "input", "output", "expectation",
    "expectations", "instruction", "instructions", "please", "kindly",
}


@dataclass
class ProjectSpec:
    title: str
    slug: str
    summary: str
    instruction: str
    input_expectations: str
    output_expectations: str
    language: str
    components: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    functional_requirements: List[str] = field(default_factory=list)
    nonfunctional_requirements: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_context(self) -> dict:
        """Compact, JSON-serialisable context for embedding in LLM prompts."""

        return {
            "title": self.title,
            "slug": self.slug,
            "language": self.language,
            "summary": self.summary,
            "instruction": self.instruction,
            "input_expectations": self.input_expectations,
            "output_expectations": self.output_expectations,
            "components": self.components,
            "operations": self.operations,
            "functional_requirements": self.functional_requirements,
            "nonfunctional_requirements": self.nonfunctional_requirements,
        }


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?;\n])\s+|\n+", text.strip())
    return [p.strip(" \t-*•").strip() for p in parts if p and p.strip(" \t-*•").strip()]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (slug or "sdlc_project")[:48]


def _snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "item"


def _title_from(instruction: str, output_exp: str) -> str:
    source = instruction.strip() or output_exp.strip() or "SDLC Project"
    words = [w for w in re.findall(r"[A-Za-z0-9]+", source)]
    significant = [w for w in words if w.lower() not in _STOPWORDS]
    chosen = (significant or words)[:5]
    if not chosen:
        return "SDLC Project"
    return " ".join(w.capitalize() for w in chosen)


def _extract_operations(text: str) -> List[str]:
    ops: List[str] = []
    seen = set()
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    for i, tok in enumerate(tokens):
        if tok in _ACTION_VERBS:
            obj = ""
            for nxt in tokens[i + 1 : i + 4]:
                if nxt not in _STOPWORDS and nxt not in _ACTION_VERBS and len(nxt) > 2:
                    obj = nxt
                    break
            name = f"{tok}_{obj}" if obj else tok
            if name not in seen:
                seen.add(name)
                ops.append(name)
    return ops[:12]


def _extract_keywords(text: str) -> List[str]:
    counts: dict[str, int] = {}
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text.lower()):
        if tok in _STOPWORDS or tok in _ACTION_VERBS:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:12]]


def _extract_nfrs(text: str) -> List[str]:
    found: List[str] = []
    low = text.lower()
    for key, nfr in _NFR_KEYWORDS.items():
        if key in low and nfr not in found:
            found.append(nfr)
    # Baseline NFRs always relevant to this edge/offline product.
    for baseline in (
        "Operate fully offline with no external network dependency.",
        "Keep all generated artifacts confidential and local.",
    ):
        if baseline not in found:
            found.append(baseline)
    return found


def analyze(
    instruction: str,
    input_expectations: str,
    output_expectations: str,
    language: str = "python",
) -> ProjectSpec:
    """Analyse the request into a structured :class:`ProjectSpec`."""

    instruction = (instruction or "").strip()
    input_expectations = (input_expectations or "").strip()
    output_expectations = (output_expectations or "").strip()
    corpus = "\n".join([instruction, input_expectations, output_expectations])

    title = _title_from(instruction, output_expectations)
    slug = _slugify(title)
    keywords = _extract_keywords(corpus)
    operations = _extract_operations(corpus) or ["process_request", "validate_input", "build_report"]

    # Functional requirements: instruction + explicit expectation sentences.
    fr: List[str] = []
    for s in _sentences(instruction):
        if len(s) > 4:
            fr.append(s if s.endswith((".", "!", "?")) else s + ".")
    for label, block in (("Input", input_expectations), ("Output", output_expectations)):
        for s in _sentences(block):
            fr.append(f"{label}: {s}")
    if not fr:
        fr = ["Deliver the behaviour described by the user instruction."]

    nfr = _extract_nfrs(corpus)

    # Components: derive a small architecture from operations + top keywords.
    components = _derive_components(keywords, operations)

    summary = instruction if len(instruction) <= 240 else instruction[:237] + "..."
    if not summary:
        summary = "Software system generated from the provided input/output expectations."

    return ProjectSpec(
        title=title,
        slug=slug,
        summary=summary,
        instruction=instruction,
        input_expectations=input_expectations,
        output_expectations=output_expectations,
        language=language.lower(),
        components=components,
        operations=operations,
        functional_requirements=fr[:20],
        nonfunctional_requirements=nfr,
        keywords=keywords,
    )


def _derive_components(keywords: List[str], operations: List[str]) -> List[str]:
    comps = [
        "Input/Interface Layer",
        "Core Service (business logic)",
        "Domain Model",
        "Validation & Rules Engine",
        "Persistence/Artifact Store",
        "Reporting Module",
    ]
    if any("auth" in o or "login" in o or "register" in o for o in operations):
        comps.insert(1, "Authentication & Authorization")
    if any(k in {"encrypt", "secure", "security", "confidential"} for k in keywords):
        comps.append("Security/Crypto Module")
    return comps


# ---------------------------------------------------------------------------
# Role / task / prompt planning (satisfies "generate prompts, tasks and roles")
# ---------------------------------------------------------------------------


@dataclass
class AgentPlan:
    agent_id: str
    role_title: str
    role_description: str
    tasks: List[str]
    prompt: str


def plan_agents(spec: ProjectSpec, framework_display: str | None = None) -> List[AgentPlan]:
    """Produce a role, task list and a ready-to-run prompt for each agent.

    ``framework_display`` names the selected unit-test framework so the Developer
    and Validation plans/prompts are precise about how tests are written and run.
    """

    fw = framework_display or "the language's default test framework"
    ctx_hint = (
        f'Project "{spec.title}" (language: {spec.language}, '
        f'unit tests: {fw}). Summary: {spec.summary}'
    )

    architect = AgentPlan(
        agent_id="architect",
        role_title="Software Architect",
        role_description=(
            "Owns the system's structure. Translates requirements into a "
            "Software Architecture Document (SAD): context, components, data "
            "flow, technology choices, quality attributes and risks."
        ),
        tasks=[
            "Identify system context, actors and boundaries.",
            "Decompose the system into components and define their responsibilities.",
            "Define data flow and key interfaces between components.",
            "Map non-functional requirements to architectural tactics.",
            "Record architecture decisions, trade-offs and risks.",
            "Produce the Software Architecture Document.",
        ],
        prompt=(
            f"{ctx_hint}\nAct as the Software Architect. Design the architecture "
            f"covering these components: {', '.join(spec.components)}. Address the "
            f"non-functional requirements: {'; '.join(spec.nonfunctional_requirements)}. "
            "Output a complete Software Architecture Document in Markdown."
        ),
    )

    developer = AgentPlan(
        agent_id="developer",
        role_title="Software Developer",
        role_description=(
            "Turns the architecture into working software: component design, "
            "source code, unit tests, integration tests, and a build/validation "
            "report documenting what was produced and how it was checked."
        ),
        tasks=[
            "Design each component's public interface from the SAD.",
            f"Implement the core operations: {', '.join(spec.operations)}.",
            f"Write unit tests using {fw}, covering each operation and edge cases.",
            "Write integration tests exercising the components together.",
            "Add the build manifest and run the tests, capturing the results.",
            "Produce a developer build & validation report.",
        ],
        prompt=(
            f"{ctx_hint}\nAct as the Software Developer. Implement the design in "
            f"{spec.language} using {fw}. Provide: (1) build manifest, "
            "(2) component/source code, (3) unit tests, (4) integration tests, "
            "(5) a short build report. Ensure the tests run."
        ),
    )

    validator = AgentPlan(
        agent_id="validation_engineer",
        role_title="Validation Engineer",
        role_description=(
            "Independently verifies the delivery: functional and non-functional "
            "use cases, plus design and architecture validation. Executes the "
            "tests and compiles an Excel validation report over the code and "
            "design produced by the Architect and Developer agents."
        ),
        tasks=[
            "Verify each functional requirement against the implementation.",
            "Verify each non-functional requirement and its architectural tactic.",
            "Validate the architecture: completeness, consistency, traceability.",
            "Execute unit and integration tests and record pass/fail.",
            "Assess code quality and test coverage signals.",
            "Compile the validation report as an Excel workbook.",
        ],
        prompt=(
            f"{ctx_hint}\nAct as the Validation Engineer. Verify all functional "
            f"requirements ({len(spec.functional_requirements)}) and non-functional "
            f"requirements ({len(spec.nonfunctional_requirements)}), validate the "
            "architecture and design, run the tests, and summarise findings with a "
            "PASS/FAIL verdict per item."
        ),
    )

    return [architect, developer, validator]
