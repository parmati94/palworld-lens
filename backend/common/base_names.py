"""Base names: where a base is, and what the guild calls it.

The game gives every base a placeholder name and numbers them in its own UI
("Base 1", "Base 2" ...), so that is what the app showed. Two things improve on
it here:

  * a PLACE, derived: the nearest fast-travel statue on the base's map layer
    (data/json/map_objects.json). Deterministic, needs no storage, and lines
    up with how players describe a base ("the one at Kelpsea Hill").
  * a CUSTOM NAME, stored: one shared JSON file the UI writes through
    /api/base-names, keyed by the game's base id. There are no accounts --
    anyone who can log in can rename, the same trust model as the rest of the
    app. The file lives under APP_STATE_PATH; when that directory is missing
    or read-only (prod without a state volume) renaming is simply off and the
    UI hides the control.

Pure python except for the file store; the parser and the router import it.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Optional

from backend.common.map_layers import which_map

MAX_NAME_LENGTH = 40
LANDMARK_TYPES = ('fast_travel',)
_WHITESPACE = re.compile(r'\s+')


def nearest_landmark(x: Optional[float], y: Optional[float], layers: Dict[str, Dict],
                     landmarks: Iterable[Dict]) -> Optional[str]:
    """Name of the closest landmark on the same map layer as (x, y), or None."""
    if x is None or y is None:
        return None
    layer = which_map(layers, x, y) if layers else None
    best, best_d = None, math.inf
    for o in landmarks:
        if o.get('type') not in LANDMARK_TYPES or not o.get('localized_name'):
            continue
        if layer and o.get('map') and o['map'] != layer:
            continue
        d = math.hypot(float(o['x']) - x, float(o['y']) - y)
        if d < best_d:
            best, best_d = o['localized_name'], d
    return best


def clean_name(raw: Optional[str]) -> str:
    """Trim and collapse whitespace; '' means "no custom name"."""
    return _WHITESPACE.sub(' ', str(raw or '')).strip()[:MAX_NAME_LENGTH]


class BaseNameStore:
    """{base_id: custom name} in one JSON file, written atomically.

    `writable` says whether renames can be saved: the directory exists (or
    can be created) and is writable. A missing file just means no names yet.
    """

    FILENAME = 'base_names.json'

    def __init__(self, state_dir: Optional[str]):
        self.dir = Path(state_dir) if state_dir else None
        self.path = self.dir / self.FILENAME if self.dir else None
        self.names: Dict[str, str] = {}

    @property
    def writable(self) -> bool:
        if not self.dir:
            return False
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return os.access(self.dir, os.W_OK)

    def load(self) -> Dict[str, str]:
        self.names = {}
        if self.path and self.path.exists():
            try:
                with open(self.path, encoding='utf-8') as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self.names = {str(k): clean_name(v) for k, v in raw.items() if clean_name(v)}
            except (OSError, ValueError):
                self.names = {}
        return self.names

    def set(self, base_id: str, name: Optional[str], keep: Optional[Iterable[str]] = None) -> Optional[str]:
        """Store (or clear, when name is blank) and persist. Returns the stored name.

        `keep` is the set of base ids that exist right now: names for any
        other id (a base that was torn down -- the game never reuses an id)
        are dropped at the same time, so the file cannot grow stale entries.
        """
        if not self.writable:
            raise PermissionError(f'base names are not writable ({self.dir})')
        cleaned = clean_name(name)
        if cleaned:
            self.names[base_id] = cleaned
        else:
            self.names.pop(base_id, None)
        if keep is not None:
            alive = set(keep) | {base_id}
            self.names = {k: v for k, v in self.names.items() if k in alive}
        self._save()
        return cleaned or None

    def _save(self) -> None:
        assert self.path is not None
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix='.base_names.', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(dict(sorted(self.names.items())), f, ensure_ascii=False, indent=1)
                f.write('\n')
            # mkstemp creates 0600; the container runs as root, so leave the file
            # readable for whoever owns the mounted directory on the host.
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
