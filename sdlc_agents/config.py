"""Configuration management for the SDLC Agents app.

All configuration is persisted locally as JSON under ``SDLC_AGENTS_HOME``
(default: ``~/.sdlc_agents``). Nothing is ever transmitted anywhere. The only
outbound network path in the whole application is the *optional*
OpenAI-compatible LLM endpoint that the user explicitly configures (which is
expected to be a local address such as ``http://127.0.0.1:11434``).
"""

from __future__ import annotations

import dataclasses
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


def home_dir() -> Path:
    """Return the base directory for all app state (config + artifacts).

    Controlled by the ``SDLC_AGENTS_HOME`` environment variable so the whole
    application can be relocated to, e.g., an encrypted volume on an edge
    device. The directory is created with owner-only permissions.
    """

    base = Path(os.environ.get("SDLC_AGENTS_HOME", str(Path.home() / ".sdlc_agents")))
    base.mkdir(parents=True, exist_ok=True)
    _harden_permissions(base)
    return base


def _harden_permissions(path: Path) -> None:
    """Best-effort restriction of a directory to the owner (0700)."""

    try:
        os.chmod(path, stat.S_IRWXU)  # rwx------
    except (PermissionError, NotImplementedError, OSError):
        # Some filesystems (e.g. certain corporate mounts) don't support chmod.
        pass


CONFIG_PATH = lambda: home_dir() / "config.json"  # noqa: E731 - tiny helper


@dataclass
class LlamaCppConfig:
    """Settings for a local GGUF model loaded via ``llama-cpp-python``."""

    model_path: str = ""
    n_ctx: int = 4096
    n_threads: int = 4
    n_gpu_layers: int = 0
    chat_format: str = ""  # empty -> let llama.cpp auto-detect


@dataclass
class OpenAICompatConfig:
    """Settings for any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM...)."""

    base_url: str = "http://127.0.0.1:11434/v1"
    api_key: str = "not-needed"
    model: str = "llama3.2"
    verify_ssl: bool = True
    timeout_seconds: int = 120


@dataclass
class ProxyConfig:
    """Corporate proxy settings applied only to the OpenAI-compatible backend."""

    use_system_proxy: bool = True
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1,::1"


@dataclass
class GenerationConfig:
    temperature: float = 0.2
    max_tokens: int = 3072


@dataclass
class ArchitectConfig:
    """Controls what the Software Architect agent produces."""

    detail_level: str = "standard"  # "brief" | "standard" | "detailed"
    include_diagrams: bool = True
    include_risks: bool = True
    include_adrs: bool = True  # architecture decision records


@dataclass
class DeveloperConfig:
    """Controls what the Software Developer agent produces."""

    generate_unit_tests: bool = True
    generate_integration_tests: bool = True
    include_build_manifest: bool = True  # Cargo.toml / pom.xml / CMakeLists.txt ...
    run_tests: bool = True  # execute tests when a toolchain is available


@dataclass
class ValidationConfig:
    """Controls how the Validation Engineer agent verifies the delivery."""

    run_tests: bool = True
    static_security_scan: bool = True  # scan for network imports / unsafe calls
    check_coverage: bool = True
    excel_report: bool = True


@dataclass
class AgentsConfig:
    """Per-agent configuration grouped under one object."""

    architect: ArchitectConfig = field(default_factory=ArchitectConfig)
    developer: DeveloperConfig = field(default_factory=DeveloperConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)


@dataclass
class SecurityConfig:
    """Confidentiality / integrity controls for generated artifacts."""

    encrypt_artifacts: bool = False
    # The passphrase itself is NEVER stored on disk. Only a flag is persisted;
    # the passphrase is supplied at runtime and kept in-session memory only.
    offline_only: bool = True  # hard block on the network backend when True


@dataclass
class AudioConfig:
    enabled: bool = True
    voice: str = ""  # empty -> system default English voice
    rate_wpm: int = 165
    volume: float = 1.0


@dataclass
class AppConfig:
    """Top-level application configuration."""

    # backend: "offline" | "llama_cpp" | "openai_compat"
    backend: str = "offline"
    target_language: str = "python"
    # Unit-test framework id for the target language ("auto" -> language default).
    test_framework: str = "auto"
    llama_cpp: LlamaCppConfig = field(default_factory=LlamaCppConfig)
    openai_compat: OpenAICompatConfig = field(default_factory=OpenAICompatConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)

    # ---- persistence -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        def build(cfg_cls, raw):
            raw = raw or {}
            fields = {f.name for f in dataclasses.fields(cfg_cls)}
            return cfg_cls(**{k: v for k, v in raw.items() if k in fields})

        def sub(cfg_cls, key):
            return build(cfg_cls, data.get(key, {}))

        agents_raw = data.get("agents", {}) or {}
        agents = AgentsConfig(
            architect=build(ArchitectConfig, agents_raw.get("architect", {})),
            developer=build(DeveloperConfig, agents_raw.get("developer", {})),
            validation=build(ValidationConfig, agents_raw.get("validation", {})),
        )

        return cls(
            backend=data.get("backend", "offline"),
            target_language=data.get("target_language", "python"),
            test_framework=data.get("test_framework", "auto"),
            llama_cpp=sub(LlamaCppConfig, "llama_cpp"),
            openai_compat=sub(OpenAICompatConfig, "openai_compat"),
            proxy=sub(ProxyConfig, "proxy"),
            generation=sub(GenerationConfig, "generation"),
            agents=agents,
            security=sub(SecurityConfig, "security"),
            audio=sub(AudioConfig, "audio"),
        )

    def save(self, path: Path | None = None) -> Path:
        path = path or CONFIG_PATH()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # rw-------
        except OSError:
            pass
        return path


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from disk, returning defaults if none exists."""

    path = path or CONFIG_PATH()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, OSError, TypeError):
        # Corrupt config should never brick the app on an edge device.
        return AppConfig()
