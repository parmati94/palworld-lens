"""Best pals for a work type -- what the server owns, and every wild species that could do it.

A join of the save's pals, the species table and the spawner levels; see
backend/common/workers.py for the ranking rules.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.common import pal_icons
from backend.common.auth import require_auth
from backend.common.breeding import generations_from, owned_genders
from backend.common.spawns import catchable_levels
from backend.common.workers import (best_owned, breedable_workers, catchable_workers, max_work_level,
                                    owned_species_counts, work_types)
from backend.parser import parser

router = APIRouter(prefix="/api/workers", tags=["workers"], dependencies=[Depends(require_auth)])


@router.get("")
async def get_workers(
    type: str = Query(..., description="work type id, e.g. EmitFlame"),
    owned_limit: int = Query(5, ge=1, le=20),
    owner: str = Query("", description="player whose pals count as breeding stock ('' = everyone)"),
):
    """Top owned pals for one work type, every wild species that can do it, what could be bred, and every player's level.

    `catchable` is the full list (best work level first, then lowest spawn
    level) so the UI can trim it to a level the reader picks without another
    request. No player-level cutoff here -- `players` carries each player's
    level so the picker can offer them as presets. `breedable` is every species
    with the job that `owner`'s pals (everyone's when blank) could breed, with
    how many breeds away it is; the `owned`/`best_owned_level` view stays
    server-wide.
    """
    data = parser.data
    if type not in work_types(data.pals):
        raise HTTPException(status_code=404, detail=f"unknown work type: {type}")

    pals = parser.get_pals()
    owned = best_owned(pals, type, limit=owned_limit)
    levels = catchable_levels(data.spawns)
    catchable = catchable_workers(data.pals, levels, type, owned_counts=owned_species_counts(pals))
    breedable = breedable_workers(data.pals, generations_from(data.breeding, owned_genders(pals, owner)), type,
                                  catchable=levels)

    def species(sid: str) -> dict:
        return {"species_id": sid, "species_name": data.pal_name(sid),
                "image_candidates": pal_icons.icon_candidates(sid)}

    return {
        "work_type": type,
        "work_name": data.work_type_name(type),
        "best_owned_level": owned[0].work_level if owned else 0,
        "max_level": max_work_level(data.pals, type),
        "owned": [{**species(o.species_id), "instance_id": o.instance_id, "name": o.name,
                   "owner": o.owner, "level": o.level, "work_level": o.work_level,
                   "base_name": o.base_name, "count": o.count} for o in owned],
        "catchable": [{**species(c.species_id), "work_level": c.work_level,
                       "spawn_level": c.spawn_level, "owned": c.owned} for c in catchable],
        "owner": owner,
        "breedable": [{**species(b.species_id), "work_level": b.work_level, "generations": b.generations,
                       "catchable": b.catchable, "spawn_level": b.spawn_level} for b in breedable],
        "players": sorted(({"name": p.nickname or p.player_name, "level": p.level}
                           for p in parser.get_players()), key=lambda p: -p["level"]),
    }
