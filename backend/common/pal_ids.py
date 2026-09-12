"""Save character_id -> species key resolution.

A save's `CharacterID` is a PascalCase species string, but it is not always a key
of pals.json:

  * Alpha / field bosses carry a `BOSS_` prefix (`BOSS_CatBat`) while their
    pals.json entry does not (`CatBat`). Humanoid NPC bosses (`BOSS_Ninja`) DO
    have their own prefixed entry, so the prefix is only stripped when the
    prefixed id is unknown.
  * Prefix casing is inconsistent (`Boss_LazyCatFish`) and so is the species
    casing (`LazyCatfish`), hence the case-insensitive pass.
  * Some spawns use a variant id the pal list doesn't carry
    (`BOSS_HerculesBeetle_Ground`); trailing tokens are dropped until a known
    species is found so the pal still gets a real name and stats.

This module is the ONLY place that logic lives. It is pure python with no
dependencies so the datagen scripts can import it without the backend's
requirements. Used by:

  * backend/parser/builders/pals.py         -- name / stats / stomach lookups
  * backend/parser/loaders/data_loader.py   -- builds the SpeciesIndex
  * backend/routers/api.py                  -- is_boss flag on map markers
  * scripts/datagen/generate_map_objects.py -- resolving boss spawns to species
  * scripts/datagen/validate.py             -- every map marker must resolve

See backend/common/pal_icons.py for the (separate) character_id -> icon rule.
"""

from __future__ import annotations

from typing import Iterable, Optional

BOSS_PREFIX = 'boss_'


def is_boss_id(character_id: str) -> bool:
    """True for `BOSS_`/`Boss_` ids (alpha pals and NPC bosses)."""
    return (character_id or '').lower().startswith(BOSS_PREFIX)


def strip_boss(character_id: str) -> str:
    """`BOSS_CatBat` -> `CatBat`; ids without the prefix are returned unchanged."""
    cid = character_id or ''
    return cid[len(BOSS_PREFIX):] if is_boss_id(cid) else cid


class SpeciesIndex:
    """The set of known species ids (pals.json keys) with tolerant lookup."""

    def __init__(self, ids: Iterable[str]):
        self.ids = set(ids)
        self._lower = {i.lower(): i for i in self.ids}

    def __contains__(self, character_id: str) -> bool:
        return character_id in self.ids

    def __len__(self) -> int:
        return len(self.ids)

    def exact(self, candidate: str) -> Optional[str]:
        """Exact, then case-insensitive, match of one candidate id."""
        if candidate in self.ids:
            return candidate
        return self._lower.get(candidate.lower())

    def resolve(self, character_id: str, trim_variants: bool = True) -> Optional[str]:
        """Resolve a save character_id to a known species id, or None.

        Order: exact id -> boss-stripped id -> (optionally) the stripped id with
        trailing `_tokens` removed one at a time. Each step is case-insensitive.
        """
        cid = (character_id or '').strip()
        if not cid:
            return None
        hit = self.exact(cid)
        if hit:
            return hit
        stripped = strip_boss(cid)
        if stripped != cid:
            hit = self.exact(stripped)
            if hit:
                return hit
        if trim_variants and '_' in stripped:
            parts = stripped.split('_')
            while len(parts) > 1:
                parts.pop()
                hit = self.exact('_'.join(parts))
                if hit:
                    return hit
        return None

    def resolve_or_raw(self, character_id: str) -> str:
        """resolve(), falling back to the boss-stripped raw id for display."""
        return self.resolve(character_id) or strip_boss((character_id or '').strip())
