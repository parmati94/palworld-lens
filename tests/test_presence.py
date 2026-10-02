"""backend/common/presence.py -- one last-seen timestamp per player, from the REST listing."""
import json
from datetime import datetime, timezone

from backend.common import presence
from backend.common.presence import PresenceStore

T1 = datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 1, 21, 30, tzinfo=timezone.utc)


def test_record_stamps_who_is_online_and_keeps_who_left(tmp_path):
    store = PresenceStore(str(tmp_path / 'state'))
    store.record({'a', 'b'}, at=T1)
    store.record({'a'}, at=T2)                       # b left: keeps the last time we saw them
    assert store.get('a') == '2026-10-01T21:30:00+00:00'
    assert store.get('b') == '2026-10-01T20:00:00+00:00'
    assert store.get('c') is None
    on_disk = json.loads((tmp_path / 'state' / 'presence.json').read_text())
    assert on_disk == {'a': '2026-10-01T21:30:00+00:00', 'b': '2026-10-01T20:00:00+00:00'}
    assert PresenceStore(str(tmp_path / 'state')).get('b') == '2026-10-01T20:00:00+00:00'   # survives a restart


def test_same_players_online_do_not_rewrite_the_file_every_check(tmp_path, monkeypatch):
    writes = []
    monkeypatch.setattr(presence, 'write_json_atomic', lambda path, data: writes.append(dict(data)))
    store = PresenceStore(str(tmp_path))
    store.record({'a'}, at=T1)
    store.record({'a'}, at=T2)                       # same set, inside WRITE_EVERY: memory only
    assert len(writes) == 1 and store.get('a') == '2026-10-01T21:30:00+00:00'
    store.record(set(), at=T2)                       # someone left: written straight away
    store.record(set(), at=T2)                       # nobody online and nothing changed: no write
    assert len(writes) == 2


def test_no_state_dir_keeps_stamps_in_memory(tmp_path):
    store = PresenceStore(None)
    store.record({'a'}, at=T1)
    assert store.get('a') == '2026-10-01T20:00:00+00:00'
    bad = tmp_path / 'presence-file'
    bad.write_text('not a dir')
    store = PresenceStore(str(bad))                  # unusable state path: still works in memory
    store.record({'a'}, at=T1)
    assert store.get('a') == '2026-10-01T20:00:00+00:00'
