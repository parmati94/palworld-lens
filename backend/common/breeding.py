"""Breeding lookups: which pair of species produces which child, and back.

The game decides a child in two steps: `DT_PalCombiUnique` (a hand-made list of
special pairs, two of them gated on parent gender) takes precedence, otherwise
the child is the species whose `combi_rank` is nearest the parents' average,
with tie-break rules that are NOT a simple "closest rank" (a naive formula
disagrees with the game on ~45% of pairs). We therefore do not re-derive the
formula: palworld-save-pal ships the full precomputed pair table in
data/json/breeding.json and this module only indexes it.

Table keys are save-pal tribe ids, which mostly equal pals.json keys but not
always (`SheepBall` vs `Sheepball`), and the table lists a few unreleased
"Unidentified Pal" placeholders that pals.json does not have. Every key is
resolved through SpeciesIndex at build time so the API and UI only ever see
pals.json ids; unresolvable rows are dropped and reported once.

Pure python, no dependencies, so the datagen scripts and tests can import it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from backend.common.pal_ids import SpeciesIndex

Gender = Optional[str]          # 'Male' | 'Female' | None (no gate / unknown)
PairKey = Tuple[str, str]       # order-independent: sorted (a, b)


@dataclass(frozen=True)
class Combo:
    """One breeding outcome. Genders are only set for gender-gated unique combos."""
    parent_a: str
    parent_b: str
    child: str
    unique: bool = False
    parent_a_gender: Gender = None
    parent_b_gender: Gender = None

    def admits(self, gender_a: Gender, gender_b: Gender) -> bool:
        """True when the given parent genders satisfy this combo's gate (if any)."""
        # The gate is stated for (parent_a, parent_b); orient() first when the
        # caller's pair is the other way round. An unknown gender passes.
        return (gender_a in (None, self.parent_a_gender)) and (gender_b in (None, self.parent_b_gender))

    def oriented(self, first: str) -> "Combo":
        """The same combo restated with `first` as parent_a (gate moves with it)."""
        if self.parent_a == first or self.parent_b != first:
            return self
        return Combo(self.parent_b, self.parent_a, self.child, self.unique,
                     self.parent_b_gender, self.parent_a_gender)


def _key(a: str, b: str) -> PairKey:
    return (a, b) if a <= b else (b, a)


def _gender(raw) -> Gender:
    if not raw:
        return None
    s = str(raw).strip().capitalize()
    return s if s in ('Male', 'Female') else None


class BreedingIndex:
    """Indexes breeding.json against pals.json ids.

    species        -- sorted breedable species ids (pals.json keys)
    ignore_combi   -- species that only breed with themselves (legendaries etc.)
    unresolved     -- table ids that matched nothing in pals.json (dropped)
    """

    def __init__(self, table: Dict, species: SpeciesIndex):
        self._resolve = species.resolve
        self.unresolved: Set[str] = set()
        self.species: List[str] = []
        self.ignore_combi: Set[str] = set()
        self._by_pair: Dict[PairKey, List[Combo]] = {}   # unique combos, then formula
        self._by_child: Dict[str, List[Combo]] = {}

        info = table.get('pal_info') or {}
        for raw, row in info.items():
            sid = self._id(raw)
            if sid is None:
                continue
            self.species.append(sid)
            if (row or {}).get('ignore_combi'):
                self.ignore_combi.add(sid)
        self.species = sorted(set(self.species))
        self._known: Set[str] = set(self.species)
        known = self._known

        unique_pairs: Set[PairKey] = set()
        for row in table.get('unique_combos') or []:
            a, b, c = self._id(row.get('parent_a')), self._id(row.get('parent_b')), self._id(row.get('child'))
            if not (a and b and c) or not {a, b, c} <= known:
                continue
            # The table lists X + X = X for ignore_combi species as "unique";
            # that is just the same-species rule, not a special combo.
            special = not (a == b == c)
            combo = Combo(a, b, c, special, _gender(row.get('parent_a_gender')), _gender(row.get('parent_b_gender')))
            unique_pairs.add(_key(a, b))
            self._add(combo)

        # Formula pairs that a unique combo overrides never apply in-game
        # (DT_PalCombiUnique wins), so they are not indexed at all.
        for raw_child, pairs in (table.get('child_to_parents_formula') or {}).items():
            c = self._id(raw_child)
            if c is None or c not in known:
                continue
            for row in pairs or []:
                a, b = self._id(row.get('parent_a')), self._id(row.get('parent_b'))
                if not (a and b) or not {a, b} <= known or _key(a, b) in unique_pairs:
                    continue
                self._add(Combo(a, b, c))

        for combos in self._by_child.values():
            combos.sort(key=lambda x: (not x.unique, x.parent_a, x.parent_b))

    # ------------------------------------------------------------------
    def _id(self, raw) -> Optional[str]:
        if not raw:
            return None
        sid = self._resolve(str(raw))
        if sid is None:
            self.unresolved.add(str(raw))
        return sid

    def _add(self, combo: Combo) -> None:
        self._by_pair.setdefault(_key(combo.parent_a, combo.parent_b), []).append(combo)
        self._by_child.setdefault(combo.child, []).append(combo)

    # ------------------------------------------------------------------
    # Queries. Every species argument is resolved, so raw character ids
    # (BOSS_Foo, Foo_Oilrig) are accepted.
    # ------------------------------------------------------------------
    def is_breedable(self, species_id: str) -> bool:
        sid = self._resolve(species_id) if species_id else None
        return sid is not None and sid in self._known

    def child_of(self, parent_a: str, parent_b: str,
                 gender_a: Gender = None, gender_b: Gender = None) -> List[Combo]:
        """Outcomes for a pair, oriented as (parent_a, parent_b).

        Usually one. The gender-gated pairs return both children when no
        genders are given, and the one that applies when they are.
        """
        a, b = self._resolve(parent_a), self._resolve(parent_b)
        if a is None or b is None:
            return []
        out = []
        for combo in self._by_pair.get(_key(a, b), []):
            oriented = combo.oriented(a)
            if oriented.admits(_gender(gender_a), _gender(gender_b)):
                out.append(oriented)
        return out

    def parents_of(self, child: str) -> List[Combo]:
        """Every pair that produces `child`, unique combos first."""
        c = self._resolve(child)
        return list(self._by_child.get(c, [])) if c else []

    def partners_for(self, parent_a: str, child: str) -> List[Combo]:
        """Pairs producing `child` that include `parent_a`, oriented with it first."""
        a = self._resolve(parent_a)
        if a is None:
            return []
        return [combo.oriented(a) for combo in self.parents_of(child)
                if a in (combo.parent_a, combo.parent_b)]

    def pair_count(self) -> int:
        return sum(len(v) for v in self._by_pair.values())
