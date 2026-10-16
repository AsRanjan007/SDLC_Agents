"""Small shared helpers (timestamps, ...).

Timestamps in generated documents must reflect a real, correct local time. The
previous code used a naive ``datetime.now()`` (no timezone), which shows the
container's clock — typically UTC — and is easy to misread as the wrong time.

``now_str`` returns a timezone-*aware* local time, labelled with the zone, and
honours an explicit zone from (in order) the ``tz`` argument, the
``SDLC_AGENTS_TZ`` environment variable (set by the orchestrator from the user's
configured timezone), or the system local zone.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional


def _zone(tz: str = ""):
    name = tz or os.environ.get("SDLC_AGENTS_TZ", "")
    if not name:
        return None
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        # Unknown zone or no tz database on the host — fall back to system local.
        return None


def local_now(tz: str = "") -> datetime:
    """Return a timezone-aware 'now' in the configured/local zone."""

    zone = _zone(tz)
    if zone is not None:
        return datetime.now(zone)
    # System local time, made timezone-aware so %Z / %z are populated.
    return datetime.now().astimezone()


def now_str(tz: str = "") -> str:
    """Formatted local timestamp, e.g. ``2026-10-16 23:35:10 IST``."""

    dt = local_now(tz)
    base = dt.strftime("%Y-%m-%d %H:%M:%S")
    label = dt.strftime("%Z") or dt.strftime("%z")
    return f"{base} {label}".strip()


def apply_timezone(tz: Optional[str]) -> None:
    """Make ``tz`` the default zone for all subsequent ``now_str`` calls.

    Stored in the environment so modules that render timestamps need no plumbing.
    An empty/falsy value clears the override (system local time is used).
    """

    if tz:
        os.environ["SDLC_AGENTS_TZ"] = tz
    else:
        os.environ.pop("SDLC_AGENTS_TZ", None)
