"""Central branding for the DevCycle AI app (name, tagline, logo assets)."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "DevCycle AI"
APP_TAGLINE = "Automating the Software Development Lifecycle through Agentic AI"
APP_SHORT_TAGLINE = "offline • edge-ready • agentic SDLC"

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

LOGO_PATH = _ASSETS / "devcycle_ai_logo.png"      # wide DevCycle AI banner
ICON_PATH = _ASSETS / "devcycle_ai_icon.png"      # square emblem (favicon / small logo)
BRAND_POSTER_PATH = _ASSETS / "devcycle_ai_brand.png"  # full brand poster


def logo() -> str | None:
    return str(LOGO_PATH) if LOGO_PATH.exists() else None


def icon() -> str | None:
    return str(ICON_PATH) if ICON_PATH.exists() else None


def poster() -> str | None:
    return str(BRAND_POSTER_PATH) if BRAND_POSTER_PATH.exists() else None


def page_icon():
    """Return a page icon: the square emblem if present, else an emoji."""

    return icon() or "♾️"
