"""Best pals for a work type: the ones the server already has, the wild ones that could do it,
and the ones that could be bred from what is owned.

Pure functions over three inputs the app already holds -- the pal list from the
save, the species table (data/json/pals.json) and the catchable-level table from
the spawner data -- so the router is a thin join and the tests need no save.

No player-level cutoff here: the catch list carries each species' lowest field
spawn level and the UI lets the reader pick "up to level N" (with the players'
levels as presets), so the same payload serves everyone on the server.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# Alpha/boss/human variants never carry work suitability we want to recommend.
_SKIP_PREFIXES = ("BOSS_", "GYM_", "RAID_", "PREDATOR_", "SUMMON_", "POLICE_")


@dataclass(frozen=True)
class OwnedWorker:
    instance_id: str
    species_id: str
    name: str              # display name (nickname if set)
    owner: Optional[str]
    level: int
    work_level: int        # effective level incl. condenser/book bonuses
    base_name: Optional[str] = None
    count: int = 1         # identical (species, owner, work level) pals folded into this row


@dataclass(frozen=True)
class CatchWorker:
    species_id: str
    work_level: int        # base level from the species table
    spawn_level: int       # lowest field spawn level
    owned: int             # how many of this species anyone on the server owns


def work_types(species: Dict[str, Dict]) -> List[str]:
    """Every work type id any species can do, sorted."""
    out = set()
    for row in species.values():
        for wt, lv in (row.get("work_suitability") or {}).items():
            if lv:
                out.add(wt)
    return sorted(out)


def max_work_level(species: Dict[str, Dict], work_type: str) -> int:
    """Highest base level any species has for `work_type` (1.0 goes to 8 for some)."""
    return max((int((r.get("work_suitability") or {}).get(work_type) or 0) for r in species.values()), default=0)


def best_owned(pals: Iterable, work_type: str, limit: int = 5) -> List[OwnedWorker]:
    """Top owned pals for `work_type`: highest effective work level, then pal level.

    `pals` are PalInfo-like objects (attribute access). Pals with no level in
    this work type are skipped. Pals of the same species, owner and work level
    fold into one row (highest pal level shown, `count` says how many) so five
    Arsox don't crowd out the next species.
    """
    best: Dict[tuple, OwnedWorker] = {}
    for p in pals:
        wl = int((getattr(p, "work_suitability", None) or {}).get(work_type) or 0)
        if wl <= 0 or not getattr(p, "species_id", None):
            continue
        row = OwnedWorker(
            instance_id=p.instance_id,
            species_id=p.species_id,
            name=getattr(p, "nickname", None) or p.name,
            owner=getattr(p, "owner_uid", None),
            level=int(p.level or 0),
            work_level=wl,
            base_name=getattr(p, "base_name", None),
        )
        key = (row.species_id, row.owner, row.work_level)
        prev = best.get(key)
        if prev is None:
            best[key] = row
        else:
            keep = row if row.level > prev.level else prev
            best[key] = OwnedWorker(**{**keep.__dict__, "count": prev.count + 1})
    rows = sorted(best.values(), key=lambda r: (-r.work_level, -r.level, r.name.lower()))
    return rows[:limit]


def catchable_workers(species: Dict[str, Dict], catchable: Dict[str, int], work_type: str,
                      owned_counts: Optional[Dict[str, int]] = None) -> List[CatchWorker]:
    """Every wild species that can do `work_type`, best work level first, then lowest spawn level.

    Only species with a field spawn (`catchable`, from spawns.catchable_levels)
    qualify. The whole list is returned; the UI trims it to "spawns at or
    under the level I'm willing to go for", which is the reader's call.
    """
    owned_counts = owned_counts or {}
    rows: List[CatchWorker] = []
    for sid, row in species.items():
        if sid.startswith(_SKIP_PREFIXES) or sid not in catchable:
            continue
        wl = int((row.get("work_suitability") or {}).get(work_type) or 0)
        if wl <= 0:
            continue
        rows.append(CatchWorker(species_id=sid, work_level=wl, spawn_level=int(catchable[sid]),
                                owned=int(owned_counts.get(sid, 0))))
    rows.sort(key=lambda r: (-r.work_level, r.spawn_level, r.species_id))
    return rows


@dataclass(frozen=True)
class BreedWorker:
    species_id: str
    work_level: int        # base level from the species table
    generations: int       # fewest breeds from the owned pals (1 = one owned pair makes it)
    catchable: bool        # also spawns in the wild (so it is in the catch list too)
    spawn_level: int = 0   # lowest field spawn level when catchable


def breedable_workers(species: Dict[str, Dict], generations: Dict[str, int], work_type: str,
                      catchable: Optional[Dict[str, int]] = None) -> List[BreedWorker]:
    """Every species that can do `work_type` and could be bred from the owned pals.

    `generations` is breeding.generations_from(): fewest breeds to each
    reachable species, 0 for ones already owned -- those are left out, since
    the point is what you do not have yet. Best work level first, then the
    shortest route, so "one breed away and better than anything owned" tops
    the list.
    """
    catchable = catchable or {}
    rows: List[BreedWorker] = []
    for sid, row in species.items():
        gens = generations.get(sid, 0)
        if gens <= 0 or sid.startswith(_SKIP_PREFIXES):
            continue
        wl = int((row.get("work_suitability") or {}).get(work_type) or 0)
        if wl <= 0:
            continue
        rows.append(BreedWorker(species_id=sid, work_level=wl, generations=gens,
                                catchable=sid in catchable, spawn_level=int(catchable.get(sid, 0))))
    rows.sort(key=lambda r: (-r.work_level, r.generations, r.species_id))
    return rows


def owned_species_counts(pals: Iterable) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in pals:
        sid = getattr(p, "species_id", None)
        if sid:
            out[sid] = out.get(sid, 0) + 1
    return out
