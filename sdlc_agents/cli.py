"""Console entry point: launch the Streamlit app offline."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    app_path = Path(__file__).resolve().parent.parent / "app.py"
    try:
        from streamlit.web import cli as stcli
    except Exception:
        sys.stderr.write("Streamlit is not installed. Run: pip install -r requirements.txt\n")
        return 1
    sys.argv = ["streamlit", "run", str(app_path), *sys.argv[1:]]
    return stcli.main()


if __name__ == "__main__":
    raise SystemExit(main())
