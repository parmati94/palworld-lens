"""Last seen: when each player was last on the server, from the REST player listing.

The save only knows the last LOGIN (LastOnlineDateTime is set on join). Every time
the online check gets an answer, each player in it is stamped "seen now"; once they
leave, the stamp stays at the last time we saw them. One timestamp per player,
overwritten -- no sessions, no history. Stored in presence.json under APP_STATE_PATH,
keyed like the online check (presence_key); without a writable state dir the stamps
live in memory until a restart. No REST configured = no stamps, and the UI falls
back to the last login.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

from backend.common.logging_config import get_logger
from backend.common.state_files import read_json, write_json_atomic, writable_dir

logger = get_logger(__name__)

WRITE_EVERY = 60.0   # seconds between file writes while the same players stay online


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec='seconds')


class PresenceStore:
    """{presence_key: ISO UTC last seen}, loaded once, written atomically."""

    FILENAME = 'presence.json'

    def __init__(self, state_dir: Optional[str]):
        self.dir = Path(state_dir) if state_dir else None
        self.path = self.dir / self.FILENAME if self.dir else None
        raw = read_json(self.path)
        self.seen: Dict[str, str] = {str(k): str(v) for k, v in raw.items() if v} if isinstance(raw, dict) else {}
        self._written_at = 0.0
        self._written_ids: frozenset = frozenset()

    def get(self, key: str) -> Optional[str]:
        return self.seen.get(key)

    def record(self, online_keys: Iterable[str], at: Optional[datetime] = None) -> None:
        """Stamp everyone online now. Writes when the online set changes, else at most every WRITE_EVERY."""
        keys = frozenset(k for k in online_keys if k)
        stamp = _iso(at or datetime.now(timezone.utc))
        for k in keys:
            self.seen[k] = stamp
        now = time.monotonic()
        if keys == self._written_ids and (not keys or now - self._written_at < WRITE_EVERY):
            return
        self._written_at, self._written_ids = now, keys
        if self.path and writable_dir(self.dir):
            try:
                write_json_atomic(self.path, dict(sorted(self.seen.items())))
            except OSError as e:
                logger.warning(f"presence: could not write {self.path}: {e}")


_store: Optional[PresenceStore] = None


def store() -> PresenceStore:
    global _store
    if _store is None:
        from backend.common.config import config
        _store = PresenceStore(config.APP_STATE_PATH)
    return _store
