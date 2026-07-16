"""Local, confidential artifact storage.

Every run gets its own directory under ``SDLC_AGENTS_HOME/workspace/<run_id>``.
Directories are created with owner-only permissions. When artifact encryption is
enabled, file bytes are encrypted at rest (``.enc`` suffix) using a runtime
passphrase that is never written to disk.
"""

from __future__ import annotations

import datetime as _dt
import os
import stat
import uuid
from pathlib import Path
from typing import List, Optional

from ..config import AppConfig, home_dir
from ..security import crypto
from ..types import Artifact


class ArtifactStore:
    def __init__(self, config: AppConfig, run_id: Optional[str] = None, passphrase: str = ""):
        self.config = config
        self.run_id = run_id or _new_run_id()
        self.passphrase = passphrase
        self.root = home_dir() / "workspace" / self.run_id
        self.root.mkdir(parents=True, exist_ok=True)
        _harden(self.root)
        _harden(self.root.parent)

    @property
    def encrypting(self) -> bool:
        return bool(self.config.security.encrypt_artifacts and self.passphrase)

    def write(self, artifact: Artifact) -> Path:
        target = self.root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        _harden(target.parent)
        raw = artifact.data if artifact.is_binary else artifact.content.encode("utf-8")
        if self.encrypting:
            blob = crypto.encrypt(raw, self.passphrase)
            enc_path = target.with_name(target.name + ".enc")
            enc_path.write_bytes(blob)
            _lock_file(enc_path)
            return enc_path
        if artifact.is_binary:
            target.write_bytes(raw)
        else:
            target.write_text(artifact.content, encoding="utf-8")
        _lock_file(target)
        return target

    def write_all(self, artifacts: List[Artifact]) -> List[Path]:
        return [self.write(a) for a in artifacts]

    def read_bytes(self, artifact_path: str) -> bytes:
        """Read an artifact back, transparently decrypting if needed."""

        plain = self.root / artifact_path
        enc = plain.with_name(plain.name + ".enc")
        if enc.exists():
            return crypto.decrypt(enc.read_bytes(), self.passphrase)
        return plain.read_bytes()

    def relpath(self, artifact_path: str) -> Path:
        return self.root / artifact_path


def _new_run_id() -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def _harden(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        pass


def _lock_file(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
