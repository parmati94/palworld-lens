"""Breeding calculator endpoints.

Everything here is a lookup into backend/common/breeding.py (the indexed
data/json/breeding.json). Pairs are returned as species ids; the UI resolves
names and icons from /api/breeding/species, which it loads once. Matching
pairs against the pals the save actually contains happens in the UI, which
already holds every pal.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.common import pal_icons
from backend.common.auth import require_auth
from backend.common.breeding import Combo
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
