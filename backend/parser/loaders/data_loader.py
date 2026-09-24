"""Loads the static game-data tables (data/json) the parser enriches saves with.

Which tables exist is defined once in backend/common/game_tables.py. Each table
is loaded by the same routine: the DATA file (stats, icons) and the L10N file
(localized_name, description) are merged per id into one row, so consumers
never merge them by hand.

A missing or unreadable REQUIRED table raises GameDataError at construction,
which stops the app at startup with a clear message. The previous loader
swallowed every failure into a warning and carried on with empty dicts, so a
bad data sync produced a running app in which every pal was named by its raw id
and had zero stats -- and nothing failed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.common.config import config
from backend.common.game_tables import TABLES, Table
from backend.common.logging_config import get_logger
from backend.common.pal_ids import SpeciesIndex
from backend.common.breeding import BreedingIndex
from backend.common import schematics as schematics_table
from backend.common.constants import (
    CONDITION_DISPLAY_NAMES,
    CONDITION_DESCRIPTIONS,
    WORK_ICON_MAPPING,
)

logger = get_logger(__name__)


class GameDataError(RuntimeError):
    """A required game-data table is missing, unreadable or empty."""


def _read_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Unreal rich-text markup in localised strings: "<NumBlue_13>+10.0%</>",
# "<Status_Up>Immune</>". Keep the text, drop the tags.
_RICH_TEXT_TAG = re.compile(r'</?[A-Za-z0-9_]*>')


def strip_rich_text(value: Any) -> Any:
    """Drop Unreal `<Style>...</>` markup from a localised string."""
    if not isinstance(value, str) or '<' not in value:
        return value
    return re.sub(r'\s{2,}', ' ', _RICH_TEXT_TAG.sub('', value)).strip()


def load_table(table: Table, root: Path) -> Any:
    """Load one table: data rows merged with their localisation.

    Dict tables come back as {id: row} with `localized_name`/`description`
    folded into each row. List tables (map_objects) come back as the list.
    """
    data_path, l10n_path = table.data_path(root), table.l10n_path(root)
    data: Any = None
    if data_path is not None:
        if not data_path.exists():
            if table.required:
                raise GameDataError(f'required game data missing: {data_path}')
            logger.warning(f'optional game data missing: {data_path}')
        else:
            data = _read_json(data_path)

    if l10n_path is not None and l10n_path.exists():
        l10n = _read_json(l10n_path)
        if data is None:
            data = {}
        if isinstance(data, dict) and isinstance(l10n, dict):
            for key, loc in l10n.items():
                if not isinstance(loc, dict):
                    continue
                row = data.setdefault(key, {})
                if isinstance(row, dict):
                    for field in ('localized_name', 'description'):
                        if loc.get(field) is not None:
                            row[field] = strip_rich_text(loc[field])
    elif l10n_path is not None and table.required:
        raise GameDataError(f'required localisation missing: {l10n_path}')

    if data is None:
        data = [] if table.name == 'map_objects' else {}
    if table.required and not data:
        raise GameDataError(f'required game data is empty: {table.name}')
    return data


class DataLoader:
    """All static game data, loaded once at startup."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or (config.DATA_PATH / 'json')
        self.tables: Dict[str, Any] = {}
        for table in TABLES.values():
            self.tables[table.name] = load_table(table, self.root)
            n = len(self.tables[table.name])
            logger.debug(f'game data: {table.name} ({n} rows)')

        # Species ---------------------------------------------------------
        self.pals: Dict[str, Dict] = self.tables['pals']
        # Per-species pak fields save-pal lacks (data/json/pal_parameters.json), merged
        # into the species row: best_work_suitability drives the first condensing star.
        for sid, extra in ((self.tables.get('pal_parameters') or {}).get('species') or {}).items():
            if sid in self.pals and isinstance(extra, dict):
                self.pals[sid].update(extra)
        self.species = SpeciesIndex(self.pals.keys())

        # Skills ----------------------------------------------------------
        self.active_skills: Dict[str, Dict] = self.tables['active_skills']
        self.passive_skills: Dict[str, Dict] = self.tables['passive_skills']

        # Names -----------------------------------------------------------
        self.elements: Dict[str, Dict] = self.tables['elements']
        self.work_types: Dict[str, Dict] = self.tables['work_suitability']
        self.items: Dict[str, Dict] = self.tables['items']
        self._items_lower = {k.lower(): k for k in self.items}
        self.buildings: Dict[str, Dict] = self.tables['buildings']
        self.technologies: Dict[str, Dict] = self.tables['technologies']

        # Trust thresholds: sorted (required_points, rank) ----------------
        self.trust_thresholds: List[Tuple[int, int]] = sorted(
            (int(v.get('required_point', 0)), int(v.get('rank', 0)))
            for k, v in self.tables['friendship'].items()
            if k.startswith('Friendship_Rank_') and not k.endswith(('Minus1', 'Minus2'))
            and isinstance(v, dict) and v.get('rank', 0) >= 0 and v.get('required_point', 0) >= 0
        )

        # Breeding: unique combos + precomputed pair table, keyed on pals.json ids
        self.breeding = BreedingIndex(self.tables['breeding'], self.species)
        if self.breeding.unresolved:
            logger.info(f'breeding table: dropped {len(self.breeding.unresolved)} id(s) not in pals.json: '
                        + ', '.join(sorted(self.breeding.unresolved)))

        self.map_objects: List[Dict] = self.tables['map_objects']
        self.map_layers: Dict[str, Dict] = {
            k: v for k, v in (self.tables.get('map_layers') or {}).items() if not k.startswith('_')
        }
        # Wild spawner groups (data/json/spawns.json): {name: {kind, radius, points, pals}}.
        # Optional -- the map's spawn search is hidden when it is absent.
        self.spawns: Dict[str, Dict] = (self.tables.get('spawns') or {}).get('groups') or {}
        # Partner skills (data/json/partner_skills.json): {species: {name, levels[5]}}, rendered
        # per condensing level. Optional -- the modal hides the block when absent.
        self.partner_skills: Dict[str, Dict] = (self.tables.get('partner_skills') or {}).get('species') or {}
        # Schematics (data/json/schematics.json): {blueprint_id: {product, kind}} -- the item or building
        # a schematic unlocks, so containers can draw the product instead of the generic blueprint.
        # Optional -- without it schematics keep the game's own icon.
        self.schematics: Dict[str, Dict] = (self.tables.get('schematics') or {}).get('schematics') or {}
        # Activity tables (data/json/activity.json): lab research names/work, expedition names/durations,
        # recipe ids that are not the product's id. Optional -- without it ids show raw and timers hide.
        act = self.tables.get('activity') or {}
        self.activity: Dict[str, Dict] = {k: (act.get(k) or {}) for k in ('lab', 'expeditions', 'recipe_products', 'generators')}
        # Loadout tables (data/json/loadout.json): what gear and food add to a player's stats, the player's
        # base row. Optional -- without it the status screen shows the un-enhanced values only.
        lo = self.tables.get('loadout') or {}
        self.loadout: Dict[str, Dict] = {k: (lo.get(k) or {}) for k in ('gear', 'food', 'player_base')}

        self._check_coverage()
        logger.info(f'game data loaded: {len(self.pals)} pals, {len(self.items)} items, '
                    f'{len(self.map_objects)} map objects, {len(self.map_layers)} map layers, '
                    f'{len(self.spawns)} spawner groups, '
                    f'{len(self.partner_skills)} partner skills, {len(self.schematics)} schematics, '
                    f'{len(self.breeding.species)} breedable species / {self.breeding.pair_count()} pairs')

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def pal_name(self, species_id: str) -> str:
        row = self.pals.get(species_id) or {}
        return row.get('localized_name') or species_id

    def item(self, item_id: str) -> Dict:
        """Item row by id, tolerating the save's inconsistent casing."""
        row = self.items.get(item_id)
        if row is None:
            key = self._items_lower.get((item_id or '').lower())
            row = self.items.get(key) if key else None
        return row or {}

    def item_name(self, item_id: str) -> str:
        return self.item(item_id).get('localized_name') or item_id

    def schematic(self, item_id: str) -> Optional[Dict]:
        """What a schematic unlocks (product id/name/kind, its icon, the schematic's rarity), or None."""
        key = item_id if item_id in self.schematics else self._items_lower.get((item_id or '').lower())
        entry = self.schematics.get(key) if key else None
        if not entry:
            return None
        return schematics_table.resolve(entry, key, self.items, self.buildings)

    def element_name(self, element_id: str) -> str:
        return (self.elements.get(element_id) or {}).get('localized_name') or element_id

    def work_type_name(self, work_type: str) -> str:
        return (self.work_types.get(work_type) or {}).get('localized_name') or work_type

    # ------------------------------------------------------------------
    # Reference data for the UI (/api/game-data)
    # ------------------------------------------------------------------
    def reference(self) -> Dict[str, Any]:
        """Small id -> display lookups the frontend keys everything on.

        Elements and work types are sent to the UI as ids; this is the one
        place their names, icons and colours come from. Icon values are file
        stems under /img/ (lowercase; nginx is case-sensitive).
        """
        elements = {}
        for eid, row in self.elements.items():
            elements[eid] = {
                'name': row.get('localized_name') or eid,
                'color': row.get('color') or '#6b7280',
                'icon': (row.get('icon') or 'neutral').lower(),
                'icon_white': (row.get('white_icon') or 'neutral_white').lower(),
            }
        work_types = {}
        for wid, row in self.work_types.items():
            work_types[wid] = {
                'name': row.get('localized_name') or wid,
                'icon': f't_icon_research_palwork_{WORK_ICON_MAPPING[wid]}_0' if wid in WORK_ICON_MAPPING else None,
            }
        conditions = {
            cid: {'name': name, 'description': CONDITION_DESCRIPTIONS.get(cid, cid)}
            for cid, name in CONDITION_DISPLAY_NAMES.items()
        }
        return {
            'elements': elements,
            'work_types': work_types,
            'conditions': conditions,
            'map_layers': self.map_layers,
            # Keyed on species_id; the UI picks levels[rank - 1] for an owned pal.
            'partner_skills': self.partner_skills,
        }

    # ------------------------------------------------------------------
    def _check_coverage(self) -> None:
        """Log (never fail) known-quiet gaps between tables."""
        work_in_pals = {w for row in self.pals.values() if isinstance(row, dict)
                        for w in (row.get('work_suitability') or {})}
        for w in sorted(work_in_pals - set(WORK_ICON_MAPPING)):
            logger.warning(f'work type {w!r} has no icon slot in WORK_ICON_MAPPING')
        for w in sorted(work_in_pals - set(self.work_types)):
            logger.warning(f'work type {w!r} has no localized name')
        elems_in_pals = {e for row in self.pals.values() if isinstance(row, dict)
                         for e in (row.get('element_types') or [])}
        for e in sorted(elems_in_pals - set(self.elements)):
            logger.warning(f'element {e!r} has no entry in elements.json')
