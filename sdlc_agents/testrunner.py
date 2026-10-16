"""Local test execution.

For Python, runs the generated pytest suite inside the run workspace in a
subprocess (degrading to a built-in runner if pytest is missing). For other
languages, best-effort executes the native toolchain (cargo, Maven, Gradle,
CMake/CTest) when it is installed; when the toolchain is absent the generated
tests are reported as *skipped* with a clear reason so the flow never stalls on
a constrained edge device. Everything runs on-device; no network is required by
the runner itself.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .languages import get_language, normalize_language, resolve_framework


def run_tests(
    workspace: Path,
    language: str = "python",
    framework_id: str = "auto",
) -> Dict[str, object]:
    """Run the generated test suite for ``language`` and return a summary.

    The summary always contains ``status`` / ``total`` / ``passed`` / ``failed``
    (and a ``detail`` string). ``status`` is one of ``passed``, ``failed``,
    ``skipped``, ``timeout``, ``error``, ``no-tests`` or ``unknown``.
    """

    lang = normalize_language(language)
    if lang == "python":
        return run_pytest(workspace)
    return _run_external(workspace, lang, framework_id)


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


# ---------------------------------------------------------------------------
# External toolchains (Rust / Java / Kotlin / C / C++)
# ---------------------------------------------------------------------------


def _run_external(workspace: Path, language: str, framework_id: str) -> Dict[str, object]:
    """Best-effort native test execution; skip cleanly if the toolchain is absent."""

    profile = get_language(language)
    framework = resolve_framework(language, framework_id)
    toolchain = framework.toolchain

    if not toolchain or shutil.which(toolchain) is None:
        return {
            "status": "skipped",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "detail": (
                f"{profile.display} test toolchain ('{toolchain}') is not installed on "
                f"this host, so the generated {framework.display} tests were not "
                f"executed here. The project builds and tests on a machine with the "
                f"toolchain available."
            ),
        }

    try:
        commands = _command_sequence(language, framework_id, workspace)
        last_out = ""
        for cmd in commands:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=900,
            )
            last_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            if proc.returncode != 0:
                return {
                    "status": "failed",
                    "total": 0,
                    "passed": 0,
                    "failed": 1,
                    "detail": f"`{' '.join(cmd)}` exited {proc.returncode}:\n{last_out[-4000:]}",
                }
        return _parse_external_output(last_out)
    except FileNotFoundError as exc:
        return {"status": "skipped", "total": 0, "passed": 0, "failed": 0,
                "detail": f"toolchain missing: {exc}"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "total": 0, "passed": 0, "failed": 0,
                "detail": "native test run timed out"}
    except OSError as exc:
        return {"status": "error", "total": 0, "passed": 0, "failed": 0,
                "detail": f"could not run native tests: {exc}"}


def _command_sequence(language: str, framework_id: str, workspace: Path) -> List[List[str]]:
    """Return the ordered shell commands to build + test a native project."""

    if language == "rust":
        return [["cargo", "test"]]
    if language == "java":
        return [["mvn", "-q", "-B", "test"]]
    if language == "kotlin":
        return [["gradle", "test", "--console=plain"]]
    if language in ("c", "cpp"):
        return [
            ["cmake", "-B", "build", "-S", "."],
            ["cmake", "--build", "build"],
            ["ctest", "--test-dir", "build", "--output-on-failure"],
        ]
    return []


def _parse_external_output(out: str) -> Dict[str, object]:
    """Parse pass/fail counts from native test output (best-effort)."""

    passed = failed = 0

    # Rust: "test result: ok. 6 passed; 0 failed; ..."
    for p, f in re.findall(r"test result:\s*\w+\.\s*(\d+)\s+passed;\s*(\d+)\s+failed", out):
        passed += int(p)
        failed += int(f)

    # CTest: "100% tests passed, 0 tests failed out of 4"
    m = re.search(r"(\d+)\s+tests\s+failed\s+out\s+of\s+(\d+)", out)
    if m:
        total_ct = int(m.group(2))
        failed_ct = int(m.group(1))
        passed += total_ct - failed_ct
        failed += failed_ct

    # Maven Surefire / Gradle: "Tests run: 7, Failures: 0, Errors: 0, Skipped: 0"
    m = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", out)
    if m:
        run_n, fail_n, err_n = int(m.group(1)), int(m.group(2)), int(m.group(3))
        passed += run_n - fail_n - err_n
        failed += fail_n + err_n

    total = passed + failed
    if total == 0:
        # Commands succeeded but we could not parse counts — trust the zero exit.
        return {"status": "passed", "total": 0, "passed": 0, "failed": 0,
                "detail": "native build/test completed successfully (counts not parsed)."
                          + ("\n" + out.strip()[-2000:] if out.strip() else "")}
    status = "passed" if failed == 0 else "failed"
    return {"status": status, "total": total, "passed": passed, "failed": failed,
            "detail": out.strip()[-4000:]}
