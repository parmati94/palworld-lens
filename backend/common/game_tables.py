"""The game-data tables palworld-lens ships, in one list.

Every consumer of data/json goes through this registry:

  * backend/parser/loaders/data_loader.py  -- loads exactly these, fails fast
                                              when a required one is missing
  * scripts/datagen/sync_game_data.py      -- syncs exactly these from save-pal
  * scripts/datagen/validate.py            -- checks exactly these exist
  * tests/                                 -- loads exactly these

Adding a table = one entry here. Anything in data/json that is NOT listed is
dead weight and sync_game_data.py will say so.

Two files per table: `data/json/<name>.json` is game DATA (stats, icons) and
`data/json/l10n/en/<name>.json` is LOCALISATION (`localized_name`,
`description`) with the same keys. Some tables have only one of the two.

Pure python, no dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional

LOCALE = 'en'


@dataclass(frozen=True)
class Table:
    name: str
    data: bool = True        # data/json/<name>.json exists
    l10n: bool = True        # data/json/l10n/en/<name>.json exists
    required: bool = True    # the app refuses to start without it
    generated: bool = False  # produced by scripts/datagen, never synced from save-pal

    def data_path(self, root: Path) -> Optional[Path]:
        return root / f'{self.name}.json' if self.data else None

    def l10n_path(self, root: Path) -> Optional[Path]:
        return root / 'l10n' / LOCALE / f'{self.name}.json' if self.l10n else None

    def paths(self, root: Path) -> Iterator[Path]:
        for p in (self.data_path(root), self.l10n_path(root)):
            if p is not None:
                yield p


TABLES: Dict[str, Table] = {t.name: t for t in (
    Table('pals'),                                   # species stats, scaling, work suitability
    Table('active_skills'),                          # element, power per waza id
    Table('passive_skills'),                         # rank, stat effects
    Table('items'),                                  # icons; names for container contents
    Table('buildings'),                              # icons, type_b for container classification
    Table('technologies', data=False),               # localized names for chests etc.
    Table('elements'),                               # colour + icon per element id
    Table('work_suitability', data=False),           # localized names per work type
    Table('friendship', l10n=False),                 # trust-level thresholds
    Table('breeding', l10n=False),                   # combi ranks, unique combos, precomputed child -> parent pairs
    Table('map_objects', l10n=False, generated=True),  # static map markers (generate_map_objects.py)
    Table('map_layers', l10n=False, generated=True, required=False),  # map textures + world bounds (hand-maintained)
)}


def synced_tables() -> Iterator[Table]:
    """Tables that come from palworld-save-pal (everything not generated locally)."""
    return (t for t in TABLES.values() if not t.generated)


def expected_files(root: Path) -> set[Path]:
    """Every file the registry says should exist under data/json."""
    return {p for t in TABLES.values() for p in t.paths(root)}
