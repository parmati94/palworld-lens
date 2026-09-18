"""Breeding calculator endpoints.

Everything here is a lookup into backend/common/breeding.py (the indexed
data/json/breeding.json). Pairs are returned as species ids; the UI resolves
names and icons from /api/breeding/species, which it loads once. Matching
pairs against the pals the save actually contains happens in the UI, which
already holds every pal -- except /route, which needs the whole pair table
and so runs the search here from the save's pals.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.common import pal_icons
from backend.common.auth import require_auth
from backend.common.breeding import Combo, Owned, plan_route, shortcuts
from backend.common.spawns import catchable_levels
from backend.parser import parser

router = APIRouter(prefix="/api/breeding", tags=["breeding"], dependencies=[Depends(require_auth)])


def _combo(c: Combo) -> dict:
    return {
        "parent_a": c.parent_a,
        "parent_b": c.parent_b,
        "child": c.child,
        "unique": c.unique,
        "parent_a_gender": c.parent_a_gender,
        "parent_b_gender": c.parent_b_gender,
    }


def _species(sid: str) -> str:
    resolved = parser.data.species.resolve(sid or "")
    if resolved is None or not parser.data.breeding.is_breedable(resolved):
        raise HTTPException(status_code=404, detail=f"unknown or non-breedable species: {sid}")
    return resolved


@router.get("/species")
async def get_species():
    """Every breedable species with what the UI needs to show one: name, icon, elements, gender odds."""
    data = parser.data
    out = []
    for sid in data.breeding.species:
        row = data.pals.get(sid) or {}
        out.append({
            "id": sid,
            "name": data.pal_name(sid),
            "image_candidates": pal_icons.icon_candidates(sid),
            "element_types": row.get("element_types") or [],
            "rarity": row.get("rarity"),
            "male_probability": row.get("male_probability", 50),
            "ignore_combi": sid in data.breeding.ignore_combi,
        })
    out.sort(key=lambda s: s["name"].lower())
    return {"species": out, "total": len(out)}


@router.get("/child")
async def get_child(
    a: str = Query(..., description="parent A species id"),
    b: str = Query(..., description="parent B species id"),
    gender_a: Optional[str] = Query(None, pattern="^(Male|Female)$"),
    gender_b: Optional[str] = Query(None, pattern="^(Male|Female)$"),
):
    """What A + B produce. Two results only for the gender-gated pairs when no genders are given."""
    a, b = _species(a), _species(b)
    results = [_combo(c) for c in parser.data.breeding.child_of(a, b, gender_a, gender_b)]
    return {"parent_a": a, "parent_b": b, "results": results}


@router.get("/parents")
async def get_parents(child: str = Query(..., description="target child species id")):
    """Every pair that produces the child, unique combos first."""
    child = _species(child)
    pairs = [_combo(c) for c in parser.data.breeding.parents_of(child)]
    return {"child": child, "pairs": pairs, "total": len(pairs)}


@router.get("/partners")
async def get_partners(a: str = Query(...), child: str = Query(...)):
    """Pairs producing the child that include species A (A listed first)."""
    a, child = _species(a), _species(child)
    pairs = [_combo(c) for c in parser.data.breeding.partners_for(a, child)]
    return {"parent_a": a, "child": child, "pairs": pairs, "total": len(pairs)}


def _owned(owner: str) -> Owned:
    """Species -> genders owned, optionally for one player (owner_uid is the player name)."""
    owned: Owned = {}
    for pal in parser.get_pals():
        if owner and pal.owner_uid != owner:
            continue
        if pal.species_id and pal.gender in ("Male", "Female"):
            owned.setdefault(pal.species_id, set()).add(pal.gender)
    return owned


@router.get("/route")
async def get_route(
    target: str = Query(..., description="species id to breed towards"),
    owner: str = Query("", description="player name whose pals count as owned ('' = everyone)"),
):
    """Fewest breeds from the pals owned to the target species, with alternatives.

    status: owned (already have it) | breedable (one owned pair does it) |
    route (needs intermediate breeds) | unreachable. Each plan's steps come in
    dependency order, the target last; a 'bred' parent is an earlier step's
    child; need_a / need_b is the gender that parent must be (null = either).
    `exact` is false when the search timed out and the plans are the best
    found rather than proven shortest; min_generations is a hard lower bound.
    `shortcuts` lists wild-catchable species that cut the best plan down.
    """
    target = _species(target)
    owned = _owned(owner)
    route = plan_route(parser.data.breeding, owned, target)
    cuts = shortcuts(parser.data.breeding, owned, route, catchable_levels(parser.data.spawns))

    def step(s):
        return {**_combo(s.combo), "from_a": s.from_a, "from_b": s.from_b, "depth": s.depth,
                "need_a": s.need_a, "need_b": s.need_b}

    return {
        "target": route.target,
        "owner": owner,
        "owned_species": len(owned),
        "status": route.status,
        "exact": route.exact,
        "min_generations": route.min_generations,
        "breeds": route.breeds,
        "generations": route.generations,
        "plans": [{"breeds": p.breeds, "generations": p.generations,
                   "steps": [step(s) for s in p.steps],
                   "hatch": {k: sorted(v) for k, v in p.hatch().items() if v}}
                  for p in route.plans],
        # Catch one of these instead: wild species that shorten the best plan.
        "shortcuts": [{"species": c.species, "kind": c.kind, "breeds_after": c.breeds_after, "saves": c.saves,
                       "catches": c.catches, "need": c.need, "level": c.level, "partner": c.partner,
                       "partner_need": c.partner_need, "partner_level": c.partner_level, "unique": c.unique}
                      for c in cuts],
    }
