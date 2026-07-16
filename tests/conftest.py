"""Test bootstrap: isolate app state to a temporary SDLC_AGENTS_HOME."""

import os
import sys
import tempfile
from pathlib import Path

# Keep all generated state out of the developer's real home directory.
_TMP_HOME = tempfile.mkdtemp(prefix="sdlc_agents_test_")
os.environ["SDLC_AGENTS_HOME"] = _TMP_HOME

# Make the package importable when tests run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
