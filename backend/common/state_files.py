"""App-owned state files under APP_STATE_PATH: one small JSON file per concern.

The directory may be missing or read-only (prod without a state volume); callers
check `writable_dir` and degrade (renames off, presence kept in memory only).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def writable_dir(path: Optional[Path]) -> bool:
    """The directory exists (or can be created) and is writable."""
    if not path:
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def read_json(path: Optional[Path]) -> Any:
    """The parsed file, or None when it is missing or unreadable."""
    if not path or not path.exists():
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json_atomic(path: Path, data: Any) -> None:
    """Write via a temp file in the same directory and rename it over the target."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.stem}.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write('\n')
        # mkstemp creates 0600; the container runs as root, so leave the file
        # readable for whoever owns the mounted directory on the host.
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
