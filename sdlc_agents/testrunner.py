"""Local test execution.

Runs the generated pytest suite inside the run workspace in a subprocess and
parses a compact pass/fail summary. Everything runs on-device; no network.
If ``pytest`` is unavailable it degrades to importing and calling the test
functions directly so the flow never stalls on an edge device.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


def run_pytest(workspace: Path, subdir: str = "tests") -> Dict[str, object]:
    """Run pytest in ``workspace/subdir``; return a structured summary."""

    target = workspace / subdir
    if not target.exists():
        return {"status": "no-tests", "total": 0, "passed": 0, "failed": 0, "detail": "no tests dir"}

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # keep the confidential workspace clean
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(target), "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except FileNotFoundError:
        return _fallback_run(workspace, target)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "total": 0, "passed": 0, "failed": 0, "detail": "pytest timed out"}

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "No module named pytest" in out or "no module named pytest" in out.lower():
        return _fallback_run(workspace, target)

    passed = _grab(r"(\d+) passed", out)
    failed = _grab(r"(\d+) failed", out)
    errors = _grab(r"(\d+) error", out)
    total = passed + failed + errors
    status = "passed" if (failed == 0 and errors == 0 and passed > 0) else (
        "failed" if total > 0 else "unknown"
    )
    return {
        "status": status,
        "total": total,
        "passed": passed,
        "failed": failed + errors,
        "detail": out.strip()[-4000:],
    }


def _grab(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _fallback_run(workspace: Path, target: Path) -> Dict[str, object]:
    """Import each test module and call its ``test_*`` functions manually."""

    src = workspace / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    passed = 0
    failed = 0
    details: List[str] = []
    for path in sorted(target.rglob("test_*.py")):
        mod = _import_path(path)
        if mod is None:
            failed += 1
            details.append(f"{path.name}: import error")
            continue
        for attr in dir(mod):
            if attr.startswith("test_") and callable(getattr(mod, attr)):
                try:
                    getattr(mod, attr)()
                    passed += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    details.append(f"{path.name}::{attr}: {exc}")
    total = passed + failed
    status = "passed" if failed == 0 and passed > 0 else ("failed" if total else "no-tests")
    return {
        "status": status,
        "total": total,
        "passed": passed,
        "failed": failed,
        "detail": "\n".join(details) or "ran via built-in fallback runner",
    }


def _import_path(path: Path):
    name = "sdlc_gen_" + re.sub(r"[^A-Za-z0-9_]+", "_", str(path.stem))
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module
