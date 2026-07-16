"""SDLC Agents - an offline, edge-friendly agentic SDLC workbench.

This package implements a small multi-agent system that turns a plain-language
instruction plus input/output expectations into a full set of software
development artifacts:

* Architect agent          -> Software Architecture Document (SAD)
* Software Developer agent -> component design, source code, unit tests,
                              integration tests and a build/validation report
* Validation Engineer agent-> functional / non-functional verification,
                              design & architecture validation and an Excel
                              validation report

Everything is designed to run **fully offline** on an edge device, including
behind a corporate proxy, with no external communication required. A local
GGUF model (via ``llama-cpp-python``) or any OpenAI-compatible local endpoint
can be configured; when none is available a deterministic offline engine keeps
the flow working end to end.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
