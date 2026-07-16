"""Offline English narration for the agentic-flow demo.

Uses ``pyttsx3`` which drives a **local**, offline TTS engine (eSpeak/eSpeakNG
on Linux, SAPI5 on Windows, NSSpeechSynthesizer on macOS). No audio ever leaves
the device. Captions are always produced so the demo is fully understandable
even when no TTS voice is installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..config import AudioConfig
from ..types import AgentResult
from ..analysis import ProjectSpec


@dataclass
class NarrationStep:
    key: str
    title: str
    caption: str
    audio_path: Optional[str] = None  # workspace-relative path if synthesized


def tts_available() -> tuple[bool, str]:
    try:
        import pyttsx3  # noqa: F401
    except Exception:
        return False, "pyttsx3 not installed — captions only. `pip install pyttsx3` to enable voice."
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        engine.stop()
        if not voices:
            return False, "No TTS voice found (install eSpeak/eSpeak-NG) — captions only."
        return True, f"Offline TTS ready ({len(voices)} voice(s))."
    except Exception as exc:  # pragma: no cover - host dependent
        return False, f"TTS engine unavailable ({exc}) — captions only."


def build_flow_script(spec: ProjectSpec, results: List[AgentResult]) -> List[NarrationStep]:
    """Compose the ordered narration script for the whole flow."""

    steps: List[NarrationStep] = [
        NarrationStep(
            key="intro",
            title="Welcome",
            caption=(
                f"Welcome to the Dev Cycle A I demo. In this flow, three agents turn the "
                f"instruction for {spec.title} into a complete software delivery, fully "
                f"offline on this device."
            ),
        )
    ]
    for res in results:
        steps.append(
            NarrationStep(
                key=res.agent_id,
                title=res.role_title,
                caption=res.narration or res.summary,
            )
        )
    steps.append(
        NarrationStep(
            key="outro",
            title="Complete",
            caption=(
                "The flow is complete. All artifacts — architecture, design, code, tests, "
                "and the Excel validation report — are stored locally and confidentially. "
                "Thank you for watching."
            ),
        )
    )
    return steps


def synthesize_step(text: str, out_path: Path, config: AudioConfig) -> Optional[Path]:
    """Synthesize ``text`` to a WAV file. Returns the path, or ``None`` on failure."""

    try:
        import pyttsx3
    except Exception:
        return None
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        engine = pyttsx3.init()
        engine.setProperty("rate", config.rate_wpm)
        engine.setProperty("volume", max(0.0, min(1.0, config.volume)))
        if config.voice:
            for v in engine.getProperty("voices"):
                if config.voice.lower() in (v.id + " " + getattr(v, "name", "")).lower():
                    engine.setProperty("voice", v.id)
                    break
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        engine.stop()
        return out_path if out_path.exists() and out_path.stat().st_size > 0 else None
    except Exception:  # pragma: no cover - host dependent
        return None
