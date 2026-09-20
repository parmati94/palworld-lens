"""Best pals for a work type -- what the server owns, and every wild species that could do it.

A join of the save's pals, the species table and the spawner levels; see
backend/common/workers.py for the ranking rules.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.common import pal_icons
from backend.common.auth import require_auth
from backend.common.spawns import catchable_levels
from backend.common.workers import best_owned, catchable_workers, max_work_level, owned_species_counts, work_types
from backend.parser import parser

router = APIRouter(prefix="/api/workers", tags=["workers"], dependencies=[Depends(require_auth)])


@router.get("")
async def get_workers(
    type: str = Query(..., description="work type id, e.g. EmitFlame"),
    owned_limit: int = Query(5, ge=1, le=20),
):
    """Top owned pals for one work type, every wild species that can do it, and every player's level.

    `catchable` is the full list (best work level first, then lowest spawn
    level) so the UI can trim it to a level the reader picks without another
    request. No player-level cutoff here -- `players` carries each player's
    level so the picker can offer them as presets.
    """
    data = parser.data
    if type not in work_types(data.pals):
        raise HTTPException(status_code=404, detail=f"unknown work type: {type}")

    pals = parser.get_pals()
    owned = best_owned(pals, type, limit=owned_limit)
    catchable = catchable_workers(data.pals, catchable_levels(data.spawns), type,
                                  owned_counts=owned_species_counts(pals))

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
        "players": sorted(({"name": p.nickname or p.player_name, "level": p.level}
                           for p in parser.get_players()), key=lambda p: -p["level"]),
    }
